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


def iter_selected_node_names(max_nodes=500):
    """
    Yield the name of every currently selected node, via repeated
    'selected_node <i>' TCL calls. Confirmed safe under Nuke Indie's
    per-session node budget - no Python node object is ever created,
    so this works regardless of how much of that budget other tools
    (or earlier calls) have already spent this session.
    """
    for i in range(max_nodes):
        try:
            name = _tcl('selected_node %d' % i)
        except Exception:
            break
        if not name:
            break
        yield name


def read_knob(node_name, knob_name):
    """
    Read a knob's raw string value via TCL. Returns None if it fails (the
    knob doesn't exist on this node, or the node doesn't exist).
    """
    try:
        value = _tcl('value %s' % _q('%s.%s' % (node_name, knob_name)))
        return value if value else None
    except Exception:
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

def _split_sequence_pattern(path):
    """
    Split a path's basename into (head, ext, style, padding) describing its
    frame token, if any. style is 'printf' (%04d), 'hash' (####), 'number'
    (a bare trailing number - a single specific frame, not a real sequence
    token), or None for a single non-sequence file.
    """
    path = _normalize(path)
    base = os.path.basename(path)
    root, ext = os.path.splitext(base)

    m = re.search(r'%(0?)(\d+)d', root)
    if m:
        pad = int(m.group(2))
        head = re.sub(r'%(0?\d+)d', '', root)
        return {'style': 'printf', 'head': head, 'ext': ext, 'padding': pad}

    if '#' in root:
        pad = root.count('#')
        head = root.replace('#' * pad, '')
        return {'style': 'hash', 'head': head, 'ext': ext, 'padding': pad}

    m = re.search(r'^(.*?)(\d+)$', root)
    if m:
        head, frame_str = m.group(1), m.group(2)
        return {'style': 'number', 'head': head, 'ext': ext,
                'frame': int(frame_str), 'padding': len(frame_str)}

    return {'style': None, 'head': root, 'ext': ext, 'padding': None}


def _build_sequence_value(dirpath, head, ext, padding, prefer_style):
    if prefer_style == 'hash':
        base = '%s%s%s' % (head, '#' * padding, ext)
    else:
        base = '%s%%0%dd%s' % (head, padding, ext)
    return _normalize(os.path.join(dirpath, base))


def is_missing_path(raw_value):
    """
    Direct existence check on the raw knob string - no frame substitution
    needed. For a sequence, the raw value still contains its frame token
    (e.g. '####' or '%04d'), which never matches a real file on disk, so
    this naturally flags sequences as needing a check; find_replacement()
    below does the real frame-aware matching against disk.
    """
    try:
        return not os.path.exists(_normalize(raw_value))
    except Exception:
        return True


# ------------------------------------------------------------------
# Scanning
# ------------------------------------------------------------------

def _candidate_knob_for_node(node_name):
    """
    Try each known path knob in turn (via TCL), returning
    (knob_name, raw_value) for the first one that exists and has a
    non-empty value, or (None, None) if this node has none of them.
    """
    for knob_name in KNOBS_TO_TRY:
        value = read_knob(node_name, knob_name)
        if value:
            return knob_name, value
    return None, None


def scan_selected():
    """
    Scan the currently selected nodes for missing file paths. Zero Python
    node objects touched - safe no matter how many nodes are selected or
    how much of the Nuke Indie session's node budget other plugins have
    already spent.
    Returns a list of dicts: node_name, knob_name, raw_value, basename, status.
    """
    missing = []
    for node_name in iter_selected_node_names():
        knob_name, raw_value = _candidate_knob_for_node(node_name)
        if not knob_name:
            continue
        if is_missing_path(raw_value):
            missing.append({
                'node_name': node_name,
                'knob_name': knob_name,
                'raw_value': raw_value,
                'basename': os.path.basename(_normalize(raw_value)),
                'status': 'Missing',
            })
    return missing


def scan_all_nodes():
    """
    Scan EVERY node in the script. Unlike scan_selected(), there is no
    TCL-only way to list all nodes, so this calls nuke.allNodes() and DOES
    spend Nuke Indie's per-session node budget - roughly one unit per node
    touched. Returns (missing_list, limit_hit).
    """
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
    """Walk search_root recursively ONCE; return [(filename, directory), ...]."""
    collected = []
    for root, _dirs, files in os.walk(search_root):
        for f in files:
            collected.append((f, root))
    return collected


def find_replacement(item, file_index):
    """
    Look for a match for item's basename inside file_index. Handles single
    files and frame-padded sequences (case-insensitive). Returns a new,
    properly formatted path string, or None if nothing matched.
    """
    info = _split_sequence_pattern(item['raw_value'])
    head, ext, style, padding = info['head'], info['ext'], info['style'], info['padding']

    if style is None:
        target = item['basename'].lower()
        for fname, directory in file_index:
            if fname.lower() == target:
                return _normalize(os.path.join(directory, fname))
        return None

    pattern = re.compile(
        r'^' + re.escape(head) + r'(\d+)' + re.escape(ext) + r'$', re.IGNORECASE
    )
    for fname, directory in file_index:
        m = pattern.match(fname)
        if m:
            if style in ('printf', 'hash'):
                # Genuine sequence token in the original knob (#### or
                # %04d) - rebuild the pattern, preserving padding.
                pad_to_use = padding if padding else len(m.group(1))
                return _build_sequence_value(directory, head, ext, pad_to_use, style)
            # style == 'number': the original path just happened to end in
            # digits but is a single specific frame, not a real sequence -
            # use the matched filename exactly as found on disk.
            return _normalize(os.path.join(directory, fname))
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
