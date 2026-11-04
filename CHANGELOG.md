# Changelog

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
