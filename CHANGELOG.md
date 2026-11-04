# Changelog

## 1.0.3

- **Fixed:** "Scan Selected Nodes" found nothing in 1.0.2 (the single-TCL-
  script selection loop returns an empty list in real Nuke). Back to one
  `selected_node <i>` call per index, now stopping at the first repeated
  name, which fixes the original "same node 500 times" bug without the
  regression.
- **Changed:** "Scan All Nodes" no longer uses `nuke.allNodes()` first
  (Nuke Indie limit stopped it after ~10 nodes). It now does
  `nuke.selectAll()` and reads the selection by name through TCL, then
  restores your previous selection. `nuke.allNodes()` is only a fallback.
- **Fixed:** real Nuke's TCL `selected_node` ignores the index and returns
  only ONE node as an internal handle (`node1fbea980b00`), never its real
  name - so only one node was ever scanned and its path read as empty.
  The selection is now walked by deselecting the current node until none
  is left (original selection restored), and each handle is resolved to
  the real node name via `value <handle>.name`.
- **Fixed:** Reads in ERROR were reported as present, because TCL `value`
  returns the path evaluated for the current frame. The raw value is read
  first (`knob node.file`, keeps `%04d`/`####`), and a sequence counts as
  present only if a matching file exists in its folder.
- **Changed:** nodes without a file path (Grade, Merge, Viewer...) are no
  longer listed; only nodes with a file path appear.
- **Fixed:** sequences with the frame token in the middle of the name
  (`shot.####.cryptomatte.exr`) were never matched; head/token/tail are
  now split around the token wherever it is.
- **Added:** Dropbox/OneDrive online-only files (listed but not
  downloaded) are detected via Windows file attributes and flagged as
  "Cloud only (not downloaded)" instead of "Found"; such files are also
  skipped as relink targets in the chosen folder.
- **Changed:** a single frame (`name_v001.1001.exr`) only relinks to that
  exact file, never to a different frame number.
- **Added:** the version is shown in the window title.
- **Changed:** when nothing is missing, the table lists what Nuke returned for
  each checked node (troubleshooting). Knob reads reset the TCL result
  first and try several spellings, so a failed read can't return another
  node's value.
- **Changed:** an empty scan now says why (nothing selected / N nodes
  checked, N exist on disk, N have no file path).

## 1.0.2

- **Fixed:** "Scan Selected Nodes" could report the same node hundreds of
  times (e.g. 500 "missing" rows for a single selected node). Root cause:
  `nuke.tcl('selected_node %d' % i)` called once per index from Python
  does not raise an error when `i` goes out of range in real Nuke - it
  silently returns the last valid result again, so the old per-call loop
  never stopped. Rewritten to run the whole scan loop inside one TCL
  script using `catch`, which correctly detects the real end of the
  selection.
- **Changed:** removed the "Relink Missing Files Updates..." menu entry.
  Update checking is now automatic and silent: every time the panel opens
  for the first time in a session, it checks GitHub in the background. If
  (and only if) a newer version exists, a small popup appears with
  "Update Now" / "OK". Any failure (offline, GitHub unreachable, etc.) is
  ignored completely - nothing is shown.

## 1.0.0

- Initial release, rebuilt from the DMB Nuke plugin pattern (installer,
  GitHub updater, `DMB Tools` shared menu).
- Scanning and relinking rewritten to go entirely through `nuke.tcl()`
  (`selected_node`, `value`, `knob`, `exists`) instead of `nuke.toNode()` /
  `nuke.selectedNodes()` / `nuke.createNode()`, so normal use ("Scan
  Selected Nodes" + relink) never spends Nuke Indie's per-session 10-node
  Python budget.
- "Scan All Nodes (whole script)" kept as a fallback for small scripts;
  it still uses `nuke.allNodes()` and can hit the Indie budget.
- Fixed: a single-frame file whose name happens to end in digits (e.g.
  `shot_0630.exr`, not a real `####`/`%04d` sequence) is now relinked
  using the exact matched filename instead of being rewritten into an
  invalid sequence pattern.
- Case-insensitive matching against the chosen search folder (useful on
  Windows, where case can drift between the original path and the
  relocated one).
