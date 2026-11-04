"""
DMB Relink Missing Files
by Daniel Marinho Borel (danielmborel@gmail.com)

Scans nodes for missing file paths and relinks them in bulk from a chosen
folder (searched recursively). Scanning/relinking is built TCL-first (see
nuke_integration/relink_core.py), so normal use of this tool - selecting
broken nodes and relinking them - never touches Nuke Indie's per-session
10-node Python budget, no matter how many nodes are involved.
"""

__version__ = "1.0.2"
