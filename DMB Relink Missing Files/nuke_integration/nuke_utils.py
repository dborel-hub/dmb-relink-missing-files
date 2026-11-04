"""
Small Nuke/Qt helpers shared by the panel and the update dialog.
"""


def get_nuke_main_window():
    """Nuke's main Qt window, to parent our own windows to it."""
    try:
        from PySide2 import QtWidgets
    except ImportError:
        from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        return None

    for w in app.topLevelWidgets():
        try:
            if w.inherits('QMainWindow') and w.metaObject().className() == 'Foundry::UI::DockMainWindow':
                return w
        except Exception:
            continue

    return app.activeWindow()


def get_nuke_version():
    import nuke
    try:
        return nuke.NUKE_VERSION_STRING
    except Exception:
        return None


def is_nuke_indie():
    """Best-effort check for Nuke Indie / Non-commercial (Python node budget applies)."""
    import nuke
    try:
        env = nuke.env
        return bool(env.get('indie') or env.get('nc'))
    except Exception:
        return False
