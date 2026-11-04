"""
Dark theme shared by the main panel and the update dialog.
"""

BG = "#2b2b2b"
BG_FIELD = "#232323"
BG_HEADER = "#333333"
FG = "#dddddd"
FG_DIM = "#999999"
BORDER = "#3a3a3a"
BORDER_HOVER = "#4a4a4a"
ACCENT = "#4a6fa5"

STATUS_OK = "#7CD97C"
STATUS_BAD = "#E06C6C"
STATUS_WARN = "#E0A96C"
STATUS_PENDING = "#E0C96C"


def stylesheet():
    return f"""
    QWidget#dmbRoot {{ background-color: {BG}; color: {FG}; }}
    QDialog {{ background-color: {BG}; color: {FG}; }}
    QTableWidget {{
        background-color: {BG_FIELD}; color: {FG}; gridline-color: {BORDER};
        selection-background-color: {ACCENT}; border: 1px solid {BORDER};
    }}
    QHeaderView::section {{
        background-color: {BG_HEADER}; color: {FG}; padding: 4px; border: 1px solid {BORDER};
    }}
    QPushButton {{
        background-color: #3a3a3a; color: {FG}; border: 1px solid {BORDER_HOVER};
        padding: 6px 12px; border-radius: 3px;
    }}
    QPushButton:hover {{ background-color: {BORDER_HOVER}; }}
    QPushButton:disabled {{ color: #777777; }}
    QLabel {{ color: {FG}; }}
    QLabel#dmbDim {{ color: {FG_DIM}; }}
    QLabel#dmbTitle {{ font-weight: bold; font-size: 13px; }}
    QListWidget {{ background-color: {BG_FIELD}; color: {FG}; border: 1px solid {BORDER}; }}
    QProgressBar {{ background-color: {BG_FIELD}; border: none; }}
    QProgressBar::chunk {{ background-color: {ACCENT}; }}
    """
