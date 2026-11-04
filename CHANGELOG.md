# Changelog

## 1.0.1

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
