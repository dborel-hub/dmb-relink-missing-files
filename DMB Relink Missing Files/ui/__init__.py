"""
DMB Relink Missing Files - main panel.

Select the broken Read/Write/Vectorfield/etc. nodes in the Node Graph
(Nuke already shows missing Reads with a black/checkerboard thumbnail),
click "Scan Selected Nodes", pick a folder, and relink everything that's
found in one click.

Nuke Indie note: "Scan Selected Nodes" and the relink step both go
entirely through nuke.tcl() (see nuke_integration/relink_core.py) and
touch ZERO Python node objects - they never spend Nuke Indie's per-session
10-node Python budget, no matter how many nodes are selected or relinked.
"Scan All Nodes (whole script)" is the one exception: there is no TCL-only
way to list every node in a script, so it falls back to nuke.allNodes()
and CAN hit that budget on a script with many nodes.
"""

try:
    from PySide2 import QtWidgets, QtGui, QtCore
except ImportError:
    from PySide6 import QtWidgets, QtGui, QtCore

from . import theme
from ..nuke_integration import relink_core
from ..config import ConfigManager


class RelinkMissingPanel(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(RelinkMissingPanel, self).__init__(parent)
        self.setObjectName("dmbRoot")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(theme.stylesheet())

        self.config = ConfigManager()
        self.missing_items = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.hint_label = QtWidgets.QLabel(
            "Select the broken Read/Write/Vectorfield nodes in the Node "
            "Graph (missing Reads show a black/checkerboard thumbnail), "
            "then click 'Scan Selected Nodes'."
        )
        self.hint_label.setObjectName("dmbDim")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.status_label = QtWidgets.QLabel(
            "Select nodes in the Node Graph, then click Scan Selected Nodes."
        )
        layout.addWidget(self.status_label)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Node', 'Current Path', 'Status'])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

        btn_row = QtWidgets.QHBoxLayout()
        self.scan_btn = QtWidgets.QPushButton('Scan Selected Nodes')
        self.scan_all_btn = QtWidgets.QPushButton('Scan All Nodes (whole script)')
        self.relink_btn = QtWidgets.QPushButton('Choose Folder && Relink All')
        btn_row.addWidget(self.scan_btn)
        btn_row.addWidget(self.scan_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.relink_btn)
        layout.addLayout(btn_row)

        self.scan_btn.clicked.connect(self.scan_selected)
        self.scan_all_btn.clicked.connect(self.scan_all)
        self.relink_btn.clicked.connect(self.choose_folder_and_relink)

        self.relink_btn.setEnabled(False)

    # ------------------------------------------------------------ scanning
    def scan_selected(self):
        self.missing_items = relink_core.scan_selected()
        self._finish_scan(limit_hit=False, selected_mode=True)

    def scan_all(self):
        self.missing_items, limit_hit = relink_core.scan_all_nodes()
        self._finish_scan(limit_hit=limit_hit, selected_mode=False)

    def _finish_scan(self, limit_hit, selected_mode):
        self._populate_table()
        count = len(self.missing_items)
        if count == 0:
            self._show_details()

        if limit_hit:
            self.status_label.setText(
                '%d missing file(s) found so far, but the Nuke Indie session '
                'node limit was reached - some nodes could not be checked. '
                'Restart Nuke, or use "Scan Selected Nodes" instead.' % count
            )
            self.relink_btn.setEnabled(count > 0)
        elif count == 0:
            info = relink_core.last_scan_info
            if info['selected'] == 0:
                self.status_label.setText(
                    'No selected node detected. Click the node(s) in the Node '
                    'Graph first, then press Scan again.'
                )
            else:
                self.status_label.setText(
                    'No missing files: %d node(s) checked, %d with a file '
                    '(all found on disk), %d without a file path (ignored).'
                    % (info['selected'], info['existing'], info['no_path_knob'])
                )
            self.relink_btn.setEnabled(False)
        else:
            self.status_label.setText('%d missing file(s) found.' % count)
            self.relink_btn.setEnabled(True)

    def _show_details(self):
        """Nothing missing: list the nodes that have a file and where it points."""
        details = relink_core.last_scan_info.get('details', [])
        self.table.setRowCount(len(details))
        for row, (name, path) in enumerate(details):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(path))
            st = QtWidgets.QTableWidgetItem('Found')
            st.setForeground(QtGui.QColor(theme.STATUS_OK))
            self.table.setItem(row, 2, st)

    def _populate_table(self):
        self.table.setRowCount(len(self.missing_items))
        for row, item in enumerate(self.missing_items):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(item['node_name']))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(item['raw_value']))
            status_item = QtWidgets.QTableWidgetItem(item['status'])
            self._colorize_status(status_item, item['status'])
            self.table.setItem(row, 2, status_item)

    def _colorize_status(self, table_item, status):
        if status == 'Relinked':
            table_item.setForeground(QtGui.QColor(theme.STATUS_OK))
        elif status.startswith('Cloud'):
            table_item.setForeground(QtGui.QColor(theme.STATUS_WARN))
        elif status == 'Not Found':
            table_item.setForeground(QtGui.QColor(theme.STATUS_BAD))
        elif status.startswith('Error'):
            table_item.setForeground(QtGui.QColor(theme.STATUS_WARN))
        else:
            table_item.setForeground(QtGui.QColor(theme.STATUS_PENDING))  # Missing

    # ------------------------------------------------------------ relink
    def choose_folder_and_relink(self):
        start_dir = self.config.get('last_search_folder', '') or ''
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select folder to search for missing files', start_dir
        )
        if not folder:
            return
        self.config.set('last_search_folder', folder)

        self.relink_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.scan_all_btn.setEnabled(False)

        self.status_label.setText('Scanning folder (this can take a while on large drives)...')
        QtWidgets.QApplication.processEvents()

        file_index = relink_core.collect_files(folder)

        def progress(done, total):
            self.status_label.setText(
                'Matching against %d files found... %d / %d' % (len(file_index), done, total)
            )
            QtWidgets.QApplication.processEvents()

        relink_core.relink_all(self.missing_items, file_index, progress_callback=progress)
        self._populate_table()

        relinked = sum(1 for i in self.missing_items if i['status'] == 'Relinked')
        not_found = sum(1 for i in self.missing_items if i['status'] == 'Not Found')

        self.status_label.setText(
            '%d relinked, %d not found. (%d files scanned in selected folder)'
            % (relinked, not_found, len(file_index))
        )

        self.relink_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)
        self.scan_all_btn.setEnabled(True)
