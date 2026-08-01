"""Main dashboard: room cards/table, the "New Room" dialog, and entry
points into the live Control Panel and the room editor.
"""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from erm import database, updater
from erm.constants import TIME_LIMIT_OPTIONS_MINUTES
from erm.control_panel import ControlPanelWindow
from erm.room_editor import RoomEditorDialog
from erm.theme import DASHBOARD_STYLE

CARD_WIDTH = 280
CARD_SPACING = 16


class _DownloadThread(QThread):
    progress = pyqtSignal(int, int)   # bytes_done, total
    finished = pyqtSignal(str)        # zip path on success
    error = pyqtSignal(str)

    def __init__(self, url: str, tag: str):
        super().__init__()
        self.url = url
        self.tag = tag
        self._zip_path = None

    def run(self):
        try:
            from pathlib import Path
            path = updater.download_update(self.url, lambda d, t: self.progress.emit(d, t))
            self._zip_path = path
            self.finished.emit(str(path))
        except Exception as exc:
            self.error.emit(str(exc))


class _UpdateDialog(QDialog):
    """Checks for updates, shows progress, and triggers the install."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("App Update")
        self.setModal(True)
        self.setFixedSize(460, 230)
        self._thread = None
        self._zip_path = None
        self._tag = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self._title_lbl = QLabel("Checking for updates…")
        self._title_lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self._title_lbl)

        self._status_lbl = QLabel(f"Current version: {updater.current_version()}")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet("color: #9090A0;")
        layout.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.hide()
        layout.addWidget(self._progress)

        layout.addStretch()

        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton("Close")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        self._action_btn = QPushButton("Download & Install")
        self._action_btn.setObjectName("primaryButton")
        self._action_btn.setEnabled(False)
        self._action_btn.clicked.connect(self._on_install)
        btn_row.addWidget(self._action_btn)
        layout.addLayout(btn_row)

        # Kick off the check immediately
        self._check()

    def _check(self):
        try:
            tag, url, name = updater.get_latest_release()
            current = updater.current_version()
            self._tag = tag
            self._url = url
            if current == "dev":
                self._title_lbl.setText("Running in dev mode")
                self._status_lbl.setText(f"Latest release: {name} ({tag})\nUpdates only apply to the packaged exe.")
            elif tag == current:
                self._title_lbl.setText("You're up to date!")
                self._status_lbl.setText(f"Version: {current}")
            else:
                self._title_lbl.setText("Update available!")
                self._status_lbl.setText(f"Current: {current}   →   Latest: {tag} ({name})")
                self._action_btn.setEnabled(True)
        except Exception as exc:
            self._title_lbl.setText("Could not check for updates")
            self._status_lbl.setText(str(exc))

    def _on_install(self):
        self._action_btn.setEnabled(False)
        self._action_btn.setText("Downloading…")
        self._progress.show()
        self._progress.setValue(0)
        self.setFixedSize(460, 260)

        self._thread = _DownloadThread(self._url, self._tag)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished.connect(self._on_downloaded)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_progress(self, done: int, total: int):
        if total > 0:
            self._progress.setValue(int(done / total * 100))
        mb = done / 1_048_576
        self._status_lbl.setText(f"Downloading… {mb:.1f} MB")

    def _on_downloaded(self, zip_path: str):
        from pathlib import Path
        self._zip_path = Path(zip_path)
        self._title_lbl.setText("Ready to install")
        self._status_lbl.setText("The app will restart automatically to apply the update.\nYour database and settings will be kept.")
        self._progress.setValue(100)
        self._action_btn.setText("Install & Restart")
        self._action_btn.clicked.disconnect()
        self._action_btn.clicked.connect(self._on_apply)
        self._action_btn.setEnabled(True)

    def _on_apply(self):
        try:
            updater.install_update(self._zip_path, self._tag)
        except Exception as exc:
            QMessageBox.critical(self, "Update failed", str(exc))
            return
        # Quit the app — the bat script will relaunch it
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def _on_error(self, msg: str):
        self._title_lbl.setText("Download failed")
        self._status_lbl.setText(msg)
        self._action_btn.setText("Download & Install")
        self._action_btn.setEnabled(True)
        self._progress.hide()


def _win_rate_text(room) -> str:
    total = room.wins + room.losses
    if total == 0:
        return "—"
    return f"{room.wins / total * 100:.0f}%"


class NewRoomDialog(QDialog):
    """"New Room" dialog: room name + time-limit dropdown."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Room")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Room Name"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Time limit"))
        self.duration_combo = QComboBox()
        for minutes in TIME_LIMIT_OPTIONS_MINUTES:
            self.duration_combo.addItem(f"{minutes} minutes", minutes)
        default_index = self.duration_combo.findData(60)
        if default_index >= 0:
            self.duration_combo.setCurrentIndex(default_index)
        layout.addWidget(self.duration_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "New Room", "Please enter a room name.")
            return
        self.accept()

    def values(self) -> tuple[str, int]:
        return self.name_edit.text().strip(), self.duration_combo.currentData()


class RoomCard(QFrame):
    """Card showing a room's name, win/loss stats and action buttons."""

    def __init__(self, room, dashboard: "MainDashboardWindow", parent=None):
        super().__init__(parent)
        self.room = room
        self.dashboard = dashboard
        self.setObjectName("roomCard")
        self.setFixedWidth(CARD_WIDTH)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        title = QLabel(self.room.name)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        header_row.addWidget(title, stretch=1)

        menu_button = QPushButton("⋯")
        menu_button.setObjectName("cardMenuButton")
        menu_button.clicked.connect(lambda: self._show_menu(menu_button))
        header_row.addWidget(menu_button)
        layout.addLayout(header_row)

        stats_row = QHBoxLayout()
        for label_text, value_text in (
            ("Win Rate", _win_rate_text(self.room)),
            ("Wins", str(self.room.wins)),
            ("Losses", str(self.room.losses)),
        ):
            stat_layout = QVBoxLayout()
            value = QLabel(value_text)
            value.setObjectName("statValue")
            label = QLabel(label_text)
            label.setObjectName("statLabel")
            stat_layout.addWidget(value)
            stat_layout.addWidget(label)
            stats_row.addLayout(stat_layout)
        layout.addLayout(stats_row)

        button_row = QHBoxLayout()
        control_button = QPushButton("Control Panel")
        control_button.setObjectName("cardPrimaryButton")
        control_button.clicked.connect(lambda: self.dashboard.open_control_panel(self.room.id))
        button_row.addWidget(control_button)

        customize_button = QPushButton("Customize")
        customize_button.setObjectName("cardSecondaryButton")
        customize_button.clicked.connect(lambda: self.dashboard.open_room_editor(self.room.id))
        button_row.addWidget(customize_button)
        layout.addLayout(button_row)

    def _show_menu(self, button: QPushButton) -> None:
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        action = menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        if action == rename_action:
            self.dashboard.rename_room(self.room.id)
        elif action == delete_action:
            self.dashboard.delete_room(self.room.id)


class NewRoomCard(QFrame):
    """Dashed-border placeholder card shown when there are no rooms yet."""

    def __init__(self, dashboard: "MainDashboardWindow", parent=None):
        super().__init__(parent)
        self.setObjectName("newRoomCard")
        self.setFixedWidth(CARD_WIDTH)
        self.setMinimumHeight(180)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("+")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 32px; color: #9CA3AF;")
        layout.addWidget(icon)

        message = QLabel("No rooms yet")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setObjectName("sectionLabel")
        layout.addWidget(message)

        button = QPushButton("Create a new room")
        button.setObjectName("createRoomCardButton")
        button.clicked.connect(dashboard.create_room)
        layout.addWidget(button)


class MainDashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Escape Room Master Console")
        self.setStyleSheet(DASHBOARD_STYLE)
        self.resize(1100, 720)

        self.active_control_panels: dict[int, ControlPanelWindow] = {}
        self._rooms_cache: list = []
        self._table_view = False

        self._build_ui()
        self.refresh_rooms()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("dashboardCentral")
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        top_row = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        top_row.addWidget(title)
        top_row.addStretch(1)

        self.view_toggle_button = QPushButton("Switch to Table View")
        self.view_toggle_button.setObjectName("secondaryButton")
        self.view_toggle_button.clicked.connect(self._toggle_view)
        top_row.addWidget(self.view_toggle_button)

        self.update_button = QPushButton("Check for Update")
        self.update_button.setObjectName("secondaryButton")
        self.update_button.clicked.connect(self._on_check_update)
        top_row.addWidget(self.update_button)

        self.create_room_button = QPushButton("Create Room")
        self.create_room_button.setObjectName("primaryButton")
        self.create_room_button.clicked.connect(self.create_room)
        top_row.addWidget(self.create_room_button)

        root.addLayout(top_row)

        self.stack = QStackedLayout()

        # --- Card grid view ---------------------------------------------
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("dashboardScrollContent")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("dashboardScrollContent")
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(CARD_SPACING)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_area.setWidget(self.scroll_content)

        # --- Table view ----------------------------------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Win Rate", "Wins", "Losses", "Actions"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        self.stack.addWidget(self.scroll_area)
        self.stack.addWidget(self.table)

        stack_container = QWidget()
        stack_container.setLayout(self.stack)
        root.addWidget(stack_container, stretch=1)

        self.setCentralWidget(central)

    # ------------------------------------------------------------------
    # Room list
    # ------------------------------------------------------------------

    def _sorted_rooms(self) -> list:
        return sorted(database.list_rooms(), key=lambda r: r.id)

    def refresh_rooms(self) -> None:
        self._rooms_cache = self._sorted_rooms()
        self._refresh_card_grid(self._rooms_cache)
        self._refresh_table(self._rooms_cache)

    def _columns_for_width(self, width: int) -> int:
        return max(1, (width + CARD_SPACING) // (CARD_WIDTH + CARD_SPACING))

    def _refresh_card_grid(self, rooms: list) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not rooms:
            self.grid_layout.addWidget(NewRoomCard(self), 0, 0)
            return

        columns = self._columns_for_width(self.scroll_area.viewport().width())
        for index, room in enumerate(rooms):
            row, col = divmod(index, columns)
            self.grid_layout.addWidget(RoomCard(room, self), row, col)

    def _refresh_table(self, rooms: list) -> None:
        self.table.setRowCount(len(rooms))
        for row, room in enumerate(rooms):
            self.table.setItem(row, 0, QTableWidgetItem(room.name))
            self.table.setItem(row, 1, QTableWidgetItem(_win_rate_text(room)))
            self.table.setItem(row, 2, QTableWidgetItem(str(room.wins)))
            self.table.setItem(row, 3, QTableWidgetItem(str(room.losses)))

            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)

            control_button = QPushButton("Control Panel")
            control_button.clicked.connect(
                lambda _checked, room_id=room.id: self.open_control_panel(room_id)
            )
            actions_layout.addWidget(control_button)

            customize_button = QPushButton("Customize")
            customize_button.clicked.connect(
                lambda _checked, room_id=room.id: self.open_room_editor(room_id)
            )
            actions_layout.addWidget(customize_button)

            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(
                lambda _checked, room_id=room.id: self.delete_room(room_id)
            )
            actions_layout.addWidget(delete_button)

            self.table.setCellWidget(row, 4, actions)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._table_view:
            self._refresh_card_grid(self._rooms_cache)

    # ------------------------------------------------------------------
    # Top bar actions
    # ------------------------------------------------------------------


    def _toggle_view(self) -> None:
        self._table_view = not self._table_view
        self.stack.setCurrentIndex(1 if self._table_view else 0)
        self.view_toggle_button.setText(
            "Switch to Card View" if self._table_view else "Switch to Table View"
        )
        if not self._table_view:
            self._refresh_card_grid(self._rooms_cache)

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _on_check_update(self) -> None:
        dlg = _UpdateDialog(self)
        dlg.exec()

    def create_room(self) -> None:
        dialog = NewRoomDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, minutes = dialog.values()
            database.create_room(name, duration_seconds=minutes * 60)
            self.refresh_rooms()

    def rename_room(self, room_id: int) -> None:
        room = database.get_room(room_id)
        if room is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Room", "Room name:", text=room.name)
        if ok and name.strip():
            database.update_room(room_id, name=name.strip())
            self.refresh_rooms()

    def delete_room(self, room_id: int) -> None:
        if room_id in self.active_control_panels:
            QMessageBox.warning(
                self, "Room In Use", "Close this room's Control Panel before deleting it."
            )
            return
        room = database.get_room(room_id)
        name = room.name if room else "this room"
        if QMessageBox.question(
            self, "Delete Room", f"Delete '{name}' and all its objectives, hints and clues?"
        ) != QMessageBox.StandardButton.Yes:
            return
        database.delete_room(room_id)
        self.refresh_rooms()

    def open_room_editor(self, room_id: int) -> None:
        dialog = RoomEditorDialog(room_id, parent=self)
        dialog.exec()
        self.refresh_rooms()

    # ------------------------------------------------------------------
    # Live sessions
    # ------------------------------------------------------------------

    def open_control_panel(self, room_id: int) -> None:
        if room_id in self.active_control_panels:
            panel = self.active_control_panels[room_id]
            panel.show()
            panel.raise_()
            panel.activateWindow()
            return

        panel = ControlPanelWindow(room_id)
        panel.back_to_dashboard.connect(lambda: self._on_control_panel_closed(room_id))
        self.active_control_panels[room_id] = panel
        self.hide()
        panel.show()

    def _on_control_panel_closed(self, room_id: int) -> None:
        panel = self.active_control_panels.pop(room_id, None)
        if panel is not None:
            panel.close()
        self.refresh_rooms()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        for panel in list(self.active_control_panels.values()):
            panel.close()
        super().closeEvent(event)
