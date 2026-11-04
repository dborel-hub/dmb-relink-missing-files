"""
Relink Core - scan and relink missing file paths (Nuke Indie safe)

Nuke Indie caps Python at ~10 node objects per session. Every
nuke.toNode(), nuke.selectedNodes(), nuke.allNodes(), nuke.createNode()
etc. returns a Python node object and burns that budget, cumulatively,
for the whole Nuke session - not per call.

scan_selected() and relink_all() NEVER create a Python node object.
Everything goes through nuke.tcl(), which returns plain strings (tested:
12 nodes created, 15 reads, no limit error):

    nuke.tcl('selected_node %d' % i)          # iterate selected node NAMES
    nuke.tcl('value "NodeName.file"')         # read a knob
    nuke.tcl('knob "NodeName.file" "value"')  # set a knob on an existing node
    nuke.tcl('exists NodeName')               # check a node exists

scan_all_nodes() is the one exception: Nuke's TCL has no "list every node
in the script" command, so it still calls nuke.allNodes() and CAN spend
the session's node budget on large scripts. Prefer scan_selected() -
select the broken nodes yourself (Nuke already shows missing Reads with a
black/checkerboard thumbnail in the Node Graph) rather than scanning
everything.
"""

import os
import re

from ..config import KNOBS_TO_TRY, RELINK_KNOBS
from ..log import log

FRAME_TOKEN_RE = re.compile(r'(%0?\d*d|#+)')


# ------------------------------------------------------------------
# TCL helpers (strings only - zero Python node objects, zero node budget)
# ------------------------------------------------------------------

def _tcl(cmd):
    import nuke
    return nuke.tcl(cmd)


def _q(value):
    """Quote a value as a TCL word (double quotes, special chars escaped)."""
    s = str(value)
    for ch in ('\\', '"', '[', ']', '$', '{', '}'):
        s = s.replace(ch, '\\' + ch)
    return '"%s"' % s


def _enumerate_selected(max_nodes=5000):
    """
    Return [(handle, real_name), ...] for every selected node. TCL only.

    In real Nuke, 'selected_node' ignores any index: it returns ONE node
    (the "current" one) as an internal handle like 'node1fbea980b00', and
    never the real name ('Read1'). So the whole selection is walked by
    taking the current node, deselecting it, and asking again until
    nothing is left; the original selection is restored at the end.
    'value <handle>.name' gives the real node name.
    """
    handles = []
    seen = set()
    for _ in range(max_nodes):
        _prime()
        try:
            h = (_tcl('selected_node') or '').strip()
        except Exception:
            break
        if not h or h in seen:
            break
        seen.add(h)
        handles.append(h)
        try:
            _tcl('knob %s.selected false' % h)
        except Exception:
            break

    result = []
    for h in handles:
        name = ''
        _prime()
        try:
            name = (_tcl('value %s.name' % h) or '').strip()
        except Exception:
            name = ''
        result.append((h, name or h))
        try:
            _tcl('knob %s.selected true' % h)
        except Exception:
            pass
    return result


def iter_selected_node_names(max_nodes=5000):
    """Yield the real name of every currently selected node (TCL only)."""
    for _h, name in _enumerate_selected(max_nodes):
        yield name


def _prime():
    """
    Reset the TCL interpreter result to "". In real Nuke a failing command
    can make nuke.tcl() hand back the PREVIOUS command's result instead of
    raising, which would make one node appear to have another node's path.
    """
    try:
        _tcl('set _dmb_prime ""')
    except Exception:
        pass


def read_knob(node_name, knob_name, debug=None):
    """
    Read a knob's string value via TCL. 'knob node.knob' returns the RAW
    value (keeps %04d / #### tokens); 'value node.knob' returns the value
    already evaluated for the current frame, which for a missing Read can
    be a path that exists, so the raw form is tried first. Returns None if
    the knob is missing/empty. If `debug` (a list) is given, what the
    first attempts returned is appended to it.
    """
    target = '%s.%s' % (node_name, knob_name)
    cmds = ('knob %s' % _q(target), 'value %s' % _q(target),
            'knob %s' % target, 'value %s' % target)
    for n, cmd in enumerate(cmds):
        _prime()
        try:
            value = _tcl(cmd)
        except Exception as e:
            if debug is not None and n < 2:
                debug.append('%s: ERROR %s' % (cmd.split()[0], str(e)[:50]))
            continue
        if debug is not None and n < 2:
            debug.append('%s = %r' % (cmd.split()[0], (value or '')[:80]))
        if value:
            return value
    return None


def write_knob(node_name, knob_name, value):
    """Set a knob's value via TCL on an existing node. Returns True on success."""
    try:
        _tcl('knob %s %s' % (_q('%s.%s' % (node_name, knob_name)), _q(value)))
        return True
    except Exception as e:
        log.warning('Could not set %s.%s: %s' % (node_name, knob_name, e))
        return False


def node_exists(node_name):
    try:
        return _tcl('exists %s' % _q(node_name)) == '1'
    except Exception:
        return False


def _normalize(p):
    return p.replace('\\', '/') if p else p


# ------------------------------------------------------------------
# Sequence pattern helpers - pure string/os work, no Nuke calls at all
# ------------------------------------------------------------------

# Windows file attributes of a cloud placeholder that is not downloaded
# (Dropbox / OneDrive "online-only"): RECALL_ON_DATA_ACCESS, RECALL_ON_OPEN, OFFLINE.
_CLOUD_ATTRS = 0x400000 | 0x40000 | 0x1000


def _is_cloud_only(st):
    return bool(getattr(st, 'st_file_attributes', 0) & _CLOUD_ATTRS)


def _split_sequence_pattern(path):
    """
    Split a path's basename into head / frame token / tail.
    style: 'printf' (%04d), 'hash' (####) - the token can sit ANYWHERE in the
    name, e.g. shot.####.cryptomatte.exr -, 'number' (a bare trailing frame
    number before the extension: a single specific frame), or None (plain file).
    Returns {'style', 'head', 'tail', 'padding'} (tail includes the extension).
    """
    base = os.path.basename(_normalize(path))

    m = FRAME_TOKEN_RE.search(base)
    if m:
        tok = m.group(0)
        if tok.startswith('#'):
            style, pad = 'hash', len(tok)
        else:
            digits = re.search(r'\d+', tok)
            style, pad = 'printf', (int(digits.group()) if digits else None)
        return {'style': style, 'head': base[:m.start()],
                'tail': base[m.end():], 'padding': pad}

    root, ext = os.path.splitext(base)
    m = re.search(r'^(.*?)(\d+)$', root)
    if m:
        return {'style': 'number', 'head': m.group(1), 'tail': ext,
                'padding': len(m.group(2))}

    return {'style': None, 'head': root, 'tail': ext, 'padding': None}


def _build_sequence_value(dirpath, head, tail, padding, prefer_style):
    if prefer_style == 'hash':
        base = '%s%s%s' % (head, '#' * padding, tail)
    else:
        base = '%s%%0%dd%s' % (head, padding, tail)
    return _normalize(os.path.join(dirpath, base))


def path_state(raw_value):
    """
    'ok'      - the file (or, for a %04d/#### path, at least one frame) is on
                disk and downloaded
    'cloud'   - it is listed but not downloaded (Dropbox/OneDrive online-only),
                so Nuke can't read it
    'missing' - nothing there
    """
    try:
        path = _normalize(raw_value)
        base = os.path.basename(path)
        if not FRAME_TOKEN_RE.search(base):
            if not os.path.exists(path):
                return 'missing'
            return 'cloud' if _is_cloud_only(os.stat(path)) else 'ok'

        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            return 'missing'
        parts = FRAME_TOKEN_RE.split(base)
        rx = re.compile(
            '^' + ''.join(re.escape(p) if i % 2 == 0 else r'\d+'
                          for i, p in enumerate(parts)) + '$', re.IGNORECASE)
        found = False
        with os.scandir(directory) as it:
            for entry in it:
                if rx.match(entry.name):
                    found = True
                    if not _is_cloud_only(entry.stat()):
                        return 'ok'
        return 'cloud' if found else 'missing'
    except Exception:
        return 'missing'


def is_missing_path(raw_value):
    """True unless path_state() says the file is really there and downloaded."""
    return path_state(raw_value) != 'ok'


# ------------------------------------------------------------------
# Scanning
# ------------------------------------------------------------------

def _candidate_knob_for_node(node_name, debug=None):
    """
    Try each known path knob in turn (via TCL), returning
    (knob_name, raw_value) for the first one that exists and has a
    non-empty value, or (None, None) if this node has none of them.
    """
    for knob_name in KNOBS_TO_TRY:
        value = read_knob(node_name, knob_name, debug)
        if value:
            return knob_name, value
    return None, None


last_scan_info = {'selected': 0, 'no_path_knob': 0, 'existing': 0, 'details': []}


def _scan_names(names):
    """
    Check each node NAME for a missing path (TCL only). Nodes without a
    file path (Grade, Merge, Viewer...) are just counted, never listed.
    last_scan_info['details'] holds (name, path) for nodes whose file is
    present, so an empty result can still show what was looked at.
    """
    global last_scan_info
    info = {'selected': len(names), 'no_path_knob': 0, 'existing': 0, 'details': []}
    missing = []
    for node_name in names:
        knob_name, raw_value = _candidate_knob_for_node(node_name)
        if not knob_name:
            info['no_path_knob'] += 1
            continue
        state = path_state(raw_value)
        if state != 'ok':
            missing.append({
                'node_name': node_name,
                'knob_name': knob_name,
                'raw_value': raw_value,
                'basename': os.path.basename(_normalize(raw_value)),
                'status': 'Missing' if state == 'missing' else 'Cloud only (not downloaded)',
            })
        else:
            info['existing'] += 1
            info['details'].append((node_name, raw_value))
    last_scan_info = info
    return missing


def scan_selected():
    """
    Scan the currently selected nodes for missing file paths. Zero Python
    node objects touched - safe no matter how many nodes are selected or
    how much of the Nuke Indie session's node budget other plugins have
    already spent. last_scan_info says how many nodes were selected / had
    no path knob / exist on disk, so the UI can explain an empty result.
    Returns a list of dicts: node_name, knob_name, raw_value, basename, status.
    """
    return _scan_names(list(iter_selected_node_names()))


def scan_all_nodes():
    """
    Scan EVERY node in the current Node Graph level.

    nuke.allNodes() hits Nuke Indie's node limit after ~10 nodes, so this
    first does nuke.selectAll() (selects nodes, returns no Python node
    objects) and then reads the selection by name via TCL like
    scan_selected(). The user's previous selection is restored afterwards.
    Only if that yields nothing does it fall back to nuke.allNodes().
    Returns (missing_list, limit_hit).
    """
    import nuke

    previous = list(iter_selected_node_names())
    try:
        nuke.selectAll()
        names = list(iter_selected_node_names())
    except Exception as e:
        log.warning('selectAll scan failed: %s' % e)
        names = []

    if names:
        missing = _scan_names(names)
        for n in names:
            write_knob(n, 'selected', 'false')
        for n in previous:
            write_knob(n, 'selected', 'true')
        return missing, False

    return _scan_all_nodes_python()


def _scan_all_nodes_python():
    """Old path: nuke.allNodes(). Spends Indie's node budget (limit_hit=True when reached)."""
    import nuke

    missing = []
    try:
        all_nodes = nuke.allNodes(recurseGroups=True)
    except RuntimeError:
        return missing, True

    for node in all_nodes:
        if node is None:
            return missing, True
        try:
            node_class = node.Class()
            node_name = node.name()
        except RuntimeError:
            return missing, True

        knob_name = RELINK_KNOBS.get(node_class)
        if not knob_name:
            continue
        try:
            if knob_name not in node.knobs():
                continue
            raw_value = node[knob_name].value()
        except RuntimeError:
            return missing, True

        if not raw_value:
            continue
        if is_missing_path(raw_value):
            missing.append({
                'node_name': node_name,
                'knob_name': knob_name,
                'raw_value': raw_value,
                'basename': os.path.basename(_normalize(raw_value)),
                'status': 'Missing',
            })

    return missing, False


# ------------------------------------------------------------------
# Relinking
# ------------------------------------------------------------------

def collect_files(search_root):
    """
    Walk search_root recursively ONCE; return [(filename, directory), ...].
    Cloud placeholders that aren't downloaded (Dropbox online-only) are
    skipped: relinking to them would still leave Nuke unable to read.
    """
    collected = []
    stack = [search_root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file() and not _is_cloud_only(entry.stat()):
                            collected.append((entry.name, current))
                    except OSError:
                        continue
        except OSError:
            continue
    return collected


def find_replacement(item, file_index):
    """
    Look for a match for item's path inside file_index. Handles single
    files, frame sequences with the token anywhere in the name
    (shot.####.cryptomatte.exr) and single frames, case-insensitive.
    Returns a new, properly formatted path string, or None.
    """
    info = _split_sequence_pattern(item['raw_value'])
    head, tail, style, padding = info['head'], info['tail'], info['style'], info['padding']
    exact = (head + tail).lower() if style is None else os.path.basename(
        _normalize(item['raw_value'])).lower()

    if style in (None, 'number'):
        for fname, directory in file_index:
            if fname.lower() == exact:
                return _normalize(os.path.join(directory, fname))
        # A single specific frame: only that exact file counts. Never swap in
        # a different frame number.
        return None

    pattern = re.compile(
        r'^' + re.escape(head) + r'(\d+)' + re.escape(tail) + r'$', re.IGNORECASE
    )
    for fname, directory in file_index:
        m = pattern.match(fname)
        if not m:
            continue
        pad_to_use = padding if padding else len(m.group(1))
        return _build_sequence_value(directory, head, tail, pad_to_use, style)
    return None


def relink_all(missing_items, file_index, progress_callback=None):
    """
    For each missing item, look up a match in file_index and write the new
    value via write_knob() - pure TCL, zero node budget, so relinking any
    number of items never touches Nuke Indie's per-session limit. Updates
    each item's 'status' in place. Returns True if a knob write failed.
    """
    total = len(missing_items)
    any_error = False
    for i, item in enumerate(missing_items):
        new_value = find_replacement(item, file_index)
        if new_value:
            if write_knob(item['node_name'], item['knob_name'], new_value):
                item['status'] = 'Relinked'
            else:
                item['status'] = 'Error: could not set knob'
                any_error = True
        else:
            item['status'] = 'Not Found'

        if progress_callback:
            progress_callback(i + 1, total)

    return any_error
