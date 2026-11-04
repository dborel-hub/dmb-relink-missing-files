"""
Panel Registration - open the DMB Relink Missing Files window inside Nuke.

Nuke Indie safe: opening the window touches no nodes, and the scanning /
relinking it drives (see relink_core.py) goes entirely through TCL.
"""

try:
    from PySide2 import QtWidgets, QtCore
except ImportError:
    from PySide6 import QtWidgets, QtCore

from ..log import log

_window = None


class RelinkMissingWindow(QtWidgets.QMainWindow):
    """Main window: remembers size/position on close."""

    def __init__(self, parent=None):
        super(RelinkMissingWindow, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle("DMB - Relink Missing Files")

    def closeEvent(self, event):
        panel = self.centralWidget()
        try:
            panel.config.set(
                'window_geometry',
                bytes(self.saveGeometry().toBase64()).decode('ascii')
            )
        except Exception as e:
            log.warning("Could not save window state: %s", e)
        super(RelinkMissingWindow, self).closeEvent(event)


def show_relink_missing():
    """Show the DMB Relink Missing Files window (creates it on first call)."""
    global _window

    if _window is not None:
        try:
            _window.show()
            _window.raise_()
            _window.activateWindow()
            return _window
        except RuntimeError:
            _window = None  # Qt object was destroyed

    from ..ui import RelinkMissingPanel
    from .nuke_utils import get_nuke_main_window

    nuke_main = get_nuke_main_window()

    window = RelinkMissingWindow(nuke_main)
    panel = RelinkMissingPanel()
    window.setCentralWidget(panel)

    saved = panel.config.get('window_geometry')
    restored = False
    if saved:
        try:
            restored = window.restoreGeometry(QtCore.QByteArray.fromBase64(saved.encode('ascii')))
        except Exception:
            restored = False
    if not restored:
        window.resize(820, 460)
        if nuke_main is not None:
            geo = nuke_main.geometry()
            window.move(geo.x() + (geo.width() - 820) // 2,
                        geo.y() + (geo.height() - 460) // 2)

    window.show()
    _window = window

    try:
        from ..ui.update_dialog import check_for_updates_silently
        check_for_updates_silently(nuke_main)
    except Exception as e:
        log.warning("Update check skipped: %s", e)

    return window
