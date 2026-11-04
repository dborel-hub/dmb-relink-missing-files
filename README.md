# DMB Relink Missing Files

A Nuke panel that finds missing file paths (Read, Write, DeepRead,
DeepWrite, Vectorfield, ReadGeo2, WriteGeo, Camera2/3, AudioRead, Precomp)
and relinks them in bulk from a folder you choose (searched recursively,
including image/frame sequences in any padding style: `####` or `%04d`).

Built **TCL-first** for Nuke Indie / Non-commercial, which caps the Python
API at ~10 node objects touched per session (cumulative for the whole
running Nuke session, not per action). `nuke.toNode()`, `nuke.selectedNodes()`,
`nuke.allNodes()`, `nuke.createNode()` all spend that budget; `nuke.tcl()`
does not.

**"Scan Selected Nodes"** and the relink step both go entirely through
`nuke.tcl()` (`selected_node`, `value`, `knob`, `exists`) and never create a
single Python node object — so they never spend Nuke Indie's node budget,
no matter how many nodes you select or relink. Select the broken nodes
yourself (Nuke already marks missing Reads with a black/checkerboard
thumbnail in the Node Graph) rather than scanning the whole script.

**"Scan All Nodes (whole script)"** is the one feature without a TCL-only
path — Nuke's TCL has no "list every node" command — so it falls back to
`nuke.allNodes()` and can hit the Indie budget on a script with many nodes.
Prefer "Scan Selected Nodes".

## Install

1. Download/clone this repository.
2. Double-click `install.pyw` (needs Python 3 from python.org — tkinter
   ships with it).
3. Click **Install / Update**.
4. Restart Nuke, then open **DMB Tools > Relink Missing Files**.

## Update

- From Nuke: **DMB Tools > Relink Missing Files Updates...**
- From the installer: **Update from GitHub** (downloads only the files
  that changed).

Your settings (last folder used, window size — stored in `data/`) are
never touched by an update or by uninstalling with "keep settings".

## Uninstall

Run `install.pyw` again and click **Uninstall**.

## Author

Daniel Marinho Borel — danielmborel@gmail.com
