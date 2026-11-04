"""
Nuke Integration Module
Opens the window, and scans/relinks nodes - all via nuke.tcl() (Nuke Indie
safe), see relink_core.py.
"""

from .panel_registration import show_relink_missing
from .nuke_utils import get_nuke_main_window, get_nuke_version, is_nuke_indie
from . import relink_core

__all__ = [
    'show_relink_missing',
    'get_nuke_main_window',
    'get_nuke_version',
    'is_nuke_indie',
    'relink_core',
]


def check_for_updates():
    """Menu entry: DMB Tools > DMB Relink Missing Files Updates..."""
    from ..ui.update_dialog import show_update_dialog
    return show_update_dialog()


__all__.append('check_for_updates')
