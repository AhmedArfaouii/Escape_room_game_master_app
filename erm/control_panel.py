"""Live game-master Control Panel: objectives, clue cards, message feed,
timer and session controls, plus the player-facing display window."""

import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QGuiApplication, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QMenu,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedLayout,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from erm import audio, database, turso
from erm.paths import resolve_path, to_portable_path
from erm.constants import APP_VERSION, AUDIO_EXTENSIONS
from erm.player_window import PlayerWindow
from erm.room_editor import HintEditorDialog, RoomEditorDialog
from erm.theme import CONTROL_PANEL_STYLE
from erm.widgets.channel_strip import AudioChannelStrip
from erm.widgets.lock_button import ClueLockButton
from erm.widgets.rating import RatingDots


class _NoZoomScrollArea(QScrollArea):
    """QScrollArea that ignores Ctrl+wheel so the layout cannot be accidentally zoomed."""

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.ignore()
        else:
            super().wheelEvent(event)


class _FeedDelegate(QStyledItemDelegate):
    """Word-wrapping delegate for the message feed list."""
    _V_PAD = 10
    _SEP_ROLE = Qt.ItemDataRole.UserRole

    def sizeHint(self, option, index):
        if index.data(self._SEP_ROLE) == "separator":
            return QSize(option.rect.width() if option.rect.isValid() else 200, 22)
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        viewport = self.parent().viewport() if self.parent() else None
        width = (viewport.width() - 8) if viewport else 200
        fm = QFontMetrics(option.font)
        rect = fm.boundingRect(
            0, 0, max(1, width), 10_000, Qt.TextFlag.TextWordWrap, text
        )
        return QSize(width, rect.height() + self._V_PAD * 2)

    def paint(self, painter, option, index):
        if index.data(self._SEP_ROLE) == "separator":
            painter.save()
            rect = option.rect
            mid_y = rect.center().y()
            label = " on screen "
            fm = painter.fontMetrics()
            label_w = fm.horizontalAdvance(label)
            cx = rect.center().x()
            pen = QPen(QColor("#3D5AFE"))
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawLine(rect.left() + 8, mid_y, cx - label_w // 2 - 2, mid_y)
            painter.drawLine(cx + label_w // 2 + 2, mid_y, rect.right() - 8, mid_y)
            painter.setPen(QColor("#5470FF"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
            painter.restore()
            return
        super().paint(painter, option, index)


def _format_time(seconds: int) -> str:
    seconds = max(0, seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class _BookingPickerDialog(QDialog):
    """Let the operator select the current group from Turso bookings."""

    def __init__(self, bookings: list[dict], error: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Current Group")
        self.setModal(True)
        self.setFixedSize(500, 360)
        self.selected: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        header = QLabel("Select the group for this session (used for the leaderboard):")
        header.setWordWrap(True)
        layout.addWidget(header)

        self._list = QListWidget()
        if error:
            err_item = QListWidgetItem(f"Error: {error}")
            err_item.setForeground(QColor("#FF8A8A"))
            self._list.addItem(err_item)
        elif bookings:
            for b in bookings:
                start = (b.get("startTime") or "")[:16].replace("T", " ")
                label = (
                    f"{b.get('customerName', '?')}  —  "
                    f"{b.get('partySize', '?')} players  |  {start}"
                )
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, b)
                self._list.addItem(item)
            self._list.setCurrentRow(0)
        else:
            self._list.addItem(QListWidgetItem("No confirmed bookings found for today"))
        layout.addWidget(self._list, stretch=1)

        btn_row = QHBoxLayout()
        skip_btn = QPushButton("Skip (no leaderboard)")
        skip_btn.clicked.connect(self.reject)
        btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        confirm_btn = QPushButton("Confirm selection")
        confirm_btn.setObjectName("primaryButton")
        confirm_btn.setEnabled(bool(bookings) and not error)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def _on_confirm(self) -> None:
        item = self._list.currentItem()
        if item:
            self.selected = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


class _TursoSetupDialog(QDialog):
    """Prompts the operator to enter Turso credentials for booking sync."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Booking Website")
        self.setModal(True)
        self.setFixedSize(520, 300)
        self.setStyleSheet(CONTROL_PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Booking Website Credentials")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #E0E0E0;")
        layout.addWidget(title)

        info = QLabel(
            "Get these from your Turso dashboard (turso.tech):\n"
            "  1. Open your database  →  copy the URL\n"
            "  2. Go to Tokens  →  create or copy your auth token"
        )
        info.setStyleSheet("color: #9090A0; font-size: 12px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(4)

        url_label = QLabel("Database URL")
        url_label.setStyleSheet("color: #C0C0D0; font-size: 12px;")
        layout.addWidget(url_label)
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("libsql://your-db-name.turso.io")
        self._url_edit.setText(os.environ.get("TURSO_DATABASE_URL", ""))
        layout.addWidget(self._url_edit)

        token_label = QLabel("Auth Token")
        token_label.setStyleSheet("color: #C0C0D0; font-size: 12px;")
        layout.addWidget(token_label)
        self._token_edit = QLineEdit()
        self._token_edit.setPlaceholderText("eyJh...")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.setText(os.environ.get("TURSO_AUTH_TOKEN", ""))
        layout.addWidget(self._token_edit)

        layout.addStretch()

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        save_btn = QPushButton("Save & Connect")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _save(self) -> None:
        url = self._url_edit.text().strip()
        token = self._token_edit.text().strip()
        if not url or not token:
            QMessageBox.warning(self, "Missing fields", "Both Database URL and Auth Token are required.")
            return

        # Apply immediately so the app can use them right away
        os.environ["TURSO_DATABASE_URL"] = url
        os.environ["TURSO_AUTH_TOKEN"] = token

        # Persist to .env next to exe (or next to main.py in dev mode)
        import sys
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
        env_path = base / ".env"
        lines = []
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                k = line.split("=", 1)[0].strip()
                if k not in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"):
                    lines.append(line)
        lines.append(f"TURSO_DATABASE_URL={url}")
        lines.append(f"TURSO_AUTH_TOKEN={token}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.accept()


class _GameOverDialog(QDialog):
    """Modal summary shown when the game ends (win or time-up)."""

    ADD_TIME = 2  # custom done() code returned when operator adds extra time

    def __init__(self, won: bool, room_name: str, session, room_duration: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game Over")
        self.setModal(True)
        self.extra_seconds = 0
        self.setStyleSheet(self.parent().styleSheet() if self.parent() else "")

        if won:
            self.setFixedSize(420, 310)
            self._build_win(room_name, session, room_duration)
        else:
            self.setFixedSize(420, 370)
            self._build_loss(room_name, session, room_duration)

    # ------------------------------------------------------------------ win
    def _build_win(self, room_name: str, session, room_duration: int) -> None:
        escape_sec = max(0, room_duration - session.remaining_seconds)
        accent = "#F5C518"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(0)

        hl = QLabel("ESCAPED!")
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.setStyleSheet(
            f"font-size: 40px; font-weight: bold; color: {accent}; "
            "background: transparent; letter-spacing: 2px;"
        )
        layout.addWidget(hl)

        room_lbl = QLabel(room_name)
        room_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        room_lbl.setStyleSheet("color: #8899AA; font-size: 13px; background: transparent;")
        layout.addWidget(room_lbl)

        time_lbl = QLabel(f"Escaped in  {_format_time(escape_sec)}")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_lbl.setStyleSheet(
            f"color: {accent}; font-size: 24px; font-weight: bold; "
            "background: transparent; margin-top: 10px;"
        )
        layout.addWidget(time_lbl)

        layout.addSpacing(14)

        card = QWidget()
        card.setObjectName("columnPanel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)
        for label, value, color in [
            ("Time remaining", _format_time(session.remaining_seconds), "#CCDDEE"),
            ("Hints used",     str(session.messages_sent),              "#CCDDEE"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #8899AA; background: transparent; font-size: 13px;")
            val = QLabel(value)
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val.setStyleSheet(f"color: {color}; font-weight: bold; background: transparent; font-size: 13px;")
            row.addWidget(lbl); row.addStretch(); row.addWidget(val)
            card_layout.addLayout(row)
        layout.addWidget(card)

        layout.addSpacing(16)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    # ----------------------------------------------------------------- loss
    def _build_loss(self, room_name: str, session, room_duration: int) -> None:
        accent = "#FF3B3B"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(0)

        hl = QLabel("TIME'S UP")
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.setStyleSheet(
            f"font-size: 40px; font-weight: bold; color: {accent}; "
            "background: transparent; letter-spacing: 2px;"
        )
        layout.addWidget(hl)

        room_lbl = QLabel(room_name)
        room_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        room_lbl.setStyleSheet("color: #8899AA; font-size: 13px; background: transparent;")
        layout.addWidget(room_lbl)

        sub_lbl = QLabel("The team ran out of time.")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setStyleSheet(
            f"color: {accent}; font-size: 14px; background: transparent; margin-top: 4px;"
        )
        layout.addWidget(sub_lbl)

        layout.addSpacing(14)

        card = QWidget()
        card.setObjectName("columnPanel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)
        for label, value, color in [
            ("Time limit",  _format_time(room_duration),     "#CCDDEE"),
            ("Hints used",  str(session.messages_sent),      "#CCDDEE"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #8899AA; background: transparent; font-size: 13px;")
            val = QLabel(value)
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val.setStyleSheet(f"color: {color}; font-weight: bold; background: transparent; font-size: 13px;")
            row.addWidget(lbl); row.addStretch(); row.addWidget(val)
            card_layout.addLayout(row)
        layout.addWidget(card)

        layout.addSpacing(14)

        # Add-time row
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self._extra_spin = QSpinBox()
        self._extra_spin.setRange(1, 30)
        self._extra_spin.setValue(5)
        self._extra_spin.setSuffix(" min")
        self._extra_spin.setFixedWidth(86)
        add_row.addWidget(self._extra_spin)
        add_btn = QPushButton("Add Time & Continue")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._on_add_time)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        layout.addSpacing(8)
        end_btn = QPushButton("End Game")
        end_btn.clicked.connect(self.reject)
        layout.addWidget(end_btn)

    def _on_add_time(self) -> None:
        self.extra_seconds = self._extra_spin.value() * 60
        self.done(self.ADD_TIME)


class ControlPanelWindow(QMainWindow):
    """Live session window for the game master."""

    back_to_dashboard = pyqtSignal()

    def __init__(self, room_id: int, parent=None):
        super().__init__(parent)
        self.room_id = room_id
        self.setStyleSheet(CONTROL_PANEL_STYLE)
        self.resize(1400, 800)

        self.player_window: Optional[PlayerWindow] = None
        self.objectives: list = []
        self.clue_buttons: list[ClueLockButton] = []
        self.audio_settings = database.get_audio_settings(room_id)
        self.video_strips: dict[str, AudioChannelStrip] = {}
        self._current_video_path: Optional[str] = None
        self._video_finished_callback: Optional[Callable[[], None]] = None
        self._feed_separator: Optional[QListWidgetItem] = None
        self._current_booking: Optional[dict] = None

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_tick)

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(500)
        self._preview_timer.timeout.connect(self._update_player_preview)
        self._preview_timer.start()

        self._build_ui()
        self.refresh_all()
        # Auto-reset any completed session so the timer always opens at full duration
        session = database.get_session(room_id)
        if session.status == "completed":
            self._start_fresh_session(status="idle")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_top_bar())

        main_area = QWidget()
        main_layout = QHBoxLayout(main_area)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        self.page_stack = QStackedLayout()
        self.page_stack.addWidget(self._build_session_page())
        self.page_stack.addWidget(self._build_audio_mixer_page())
        page_container = QWidget()
        page_container.setLayout(self.page_stack)
        main_layout.addWidget(page_container, stretch=1)

        main_layout.addWidget(self._build_separator())
        main_layout.addWidget(self._build_controls_column())
        root.addWidget(main_area, stretch=1)

        root.addWidget(self._build_bottom_bar())

        self.setCentralWidget(central)
        self.control_panel_tab.setChecked(True)

        for btn in self.findChildren(QPushButton):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_session_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._build_objectives_column(), stretch=1)
        layout.addWidget(self._build_separator())
        layout.addWidget(self._build_detail_column(), stretch=2)
        layout.addWidget(self._build_separator())
        layout.addWidget(self._build_feed_column(), stretch=2)
        return page

    def _build_separator(self) -> QFrame:
        line = QFrame()
        line.setObjectName("columnSeparator")
        line.setFrameShape(QFrame.Shape.NoFrame)
        line.setFixedWidth(2)
        return line

    def _build_section_separator(self) -> QFrame:
        line = QFrame()
        line.setObjectName("sectionSeparator")
        line.setFrameShape(QFrame.Shape.NoFrame)
        line.setFixedHeight(2)
        return line

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)

        self.control_panel_tab = QPushButton("Control Panel")
        self.control_panel_tab.setObjectName("tabButton")
        self.control_panel_tab.setCheckable(True)
        self.tab_group.addButton(self.control_panel_tab, 0)
        layout.addWidget(self.control_panel_tab)

        self.audio_mixer_tab = QPushButton("Audio Mixer")
        self.audio_mixer_tab.setObjectName("tabButton")
        self.audio_mixer_tab.setCheckable(True)
        self.tab_group.addButton(self.audio_mixer_tab, 1)
        layout.addWidget(self.audio_mixer_tab)

        self.tab_group.idClicked.connect(self._on_tab_clicked)

        layout.addStretch(1)
        self.room_name_label = QLabel("")
        self.room_name_label.setObjectName("roomNameLabel")
        layout.addWidget(self.room_name_label)
        layout.addStretch(1)

        self.edit_room_button = QPushButton("Room Setup")
        self.edit_room_button.clicked.connect(self._open_room_editor)
        layout.addWidget(self.edit_room_button)

        self.link_group_button = QPushButton("Link Group")
        self.link_group_button.setObjectName("linkGroupButton")
        self.link_group_button.clicked.connect(self._on_link_group)
        layout.addWidget(self.link_group_button)

        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.setCheckable(True)
        self.fullscreen_button.toggled.connect(self._toggle_fullscreen)
        layout.addWidget(self.fullscreen_button)

        return bar

    def _build_objectives_column(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("columnPanel")
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Objectives")
        header.setObjectName("columnHeader")
        layout.addWidget(header)

        self.objectives_list = QListWidget()
        self.objectives_list.currentItemChanged.connect(lambda *_: self._refresh_detail())
        self.objectives_list.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.objectives_list)

        add_obj_btn = QPushButton("+ Add Objective")
        add_obj_btn.clicked.connect(self._on_quick_add_objective)
        layout.addWidget(add_obj_btn)

        return panel

    def _build_detail_column(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("columnPanel")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(520)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Objective")
        header.setObjectName("columnHeader")
        layout.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)

        self.complete_button = QPushButton("Mark Complete")
        self.complete_button.setObjectName("primaryButton")
        self.complete_button.clicked.connect(self._toggle_objective_complete)
        content_layout.addWidget(self.complete_button)

        self.detail_title_label = QLabel("")
        self.detail_title_label.setObjectName("objectiveTitle")
        self.detail_title_label.setWordWrap(True)
        content_layout.addWidget(self.detail_title_label)

        self.detail_code_label = QLabel("")
        self.detail_code_label.setObjectName("objectiveCode")
        content_layout.addWidget(self.detail_code_label)

        self.detail_description_label = QLabel("")
        self.detail_description_label.setObjectName("objectiveDescription")
        self.detail_description_label.setWordWrap(True)
        content_layout.addWidget(self.detail_description_label)

        content_layout.addSpacing(8)
        content_layout.addWidget(self._build_section_separator())
        content_layout.addSpacing(4)

        clues_header = QLabel("Clues")
        clues_header.setObjectName("sectionHeader")
        content_layout.addWidget(clues_header)
        self.clues_detail_list = QListWidget()
        self.clues_detail_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.clues_detail_list.model().rowsMoved.connect(self._on_hints_reordered)
        self.clues_detail_list.itemClicked.connect(self._on_clue_card_clicked)
        self.clues_detail_list.itemDoubleClicked.connect(self._on_clue_card_double_clicked)
        self.clues_detail_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.clues_detail_list.customContextMenuRequested.connect(self._on_clue_context_menu)
        self.clues_detail_list.setCursor(Qt.CursorShape.PointingHandCursor)
        content_layout.addWidget(self.clues_detail_list, stretch=1)

        self.add_clue_btn = QPushButton("+ Add Clue")
        self.add_clue_btn.clicked.connect(self._on_quick_add_clue)
        content_layout.addWidget(self.add_clue_btn)

        layout.addWidget(content, stretch=1)
        return panel

    def _build_feed_column(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("columnPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Message Feed")
        header.setObjectName("columnHeader")
        layout.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)

        self.feed_list = QListWidget()
        self.feed_list.setWordWrap(True)
        self.feed_list.setSpacing(4)
        self.feed_list.setItemDelegate(_FeedDelegate(self.feed_list))
        content_layout.addWidget(self.feed_list, stretch=1)

        clear_button = QPushButton("Clear player window")
        clear_button.clicked.connect(self._on_clear_player_window)
        content_layout.addWidget(clear_button)

        send_row = QHBoxLayout()
        self.message_edit = QLineEdit()
        self.message_edit.setPlaceholderText("Type a message to send to players...")
        self.message_edit.returnPressed.connect(self._on_send_message)
        send_row.addWidget(self.message_edit, stretch=1)

        alert_button = QPushButton("Alert Tone")
        alert_button.clicked.connect(self._play_alert_sound)
        send_row.addWidget(alert_button)

        send_button = QPushButton("Send")
        send_button.setObjectName("primaryButton")
        send_button.clicked.connect(self._on_send_message)
        send_row.addWidget(send_button)

        content_layout.addLayout(send_row)

        sfx_row = QHBoxLayout()
        sfx_row.setSpacing(6)
        self._sfx_buttons: list[QPushButton] = []
        for n in (1, 2, 3):
            btn = QPushButton(f"SFX {n}")
            btn.setObjectName("sfxButton")
            btn.clicked.connect(lambda _, i=n: self._on_play_sfx(i))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, i=n, b=btn: self._on_sfx_context_menu(i, b))
            self._sfx_buttons.append(btn)
            sfx_row.addWidget(btn)
        content_layout.addLayout(sfx_row)

        layout.addWidget(content, stretch=1)
        return panel

    def _build_audio_mixer_page(self) -> QWidget:
        _STRIP_H = 295  # height reserved for one row of channel strips

        panel = QWidget()
        panel.setObjectName("columnPanel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QLabel("Audio Mixer")
        header.setObjectName("columnHeader")
        outer.addWidget(header)

        # Vertically scrollable wrapper so all three sections are reachable
        page_scroll = _NoZoomScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        page_content = QWidget()
        page_layout = QVBoxLayout(page_content)
        page_layout.setContentsMargins(16, 16, 16, 16)
        page_layout.setSpacing(16)
        page_scroll.setWidget(page_content)

        # ── Audio ──────────────────────────────────────────────────────────
        audio_card, audio_row = self._make_mixer_card("Audio", _STRIP_H)
        self.audio_strips: dict[str, AudioChannelStrip] = {}
        for channel, label, show_preview in (
            ("alert", "Alert", True),
            ("game_music", "Game Music", True),
            ("success", "Success", True),
            ("fail", "Fail", True),
            ("video", "Video", False),
            ("master", "Master", False),
        ):
            strip = AudioChannelStrip(label, show_preview=show_preview)
            strip.volume_changed.connect(
                lambda value, ch=channel: self._on_audio_volume_changed(ch, value)
            )
            strip.mute_toggled.connect(
                lambda checked, ch=channel: self._on_audio_mute_toggled(ch, checked)
            )
            strip.preview_clicked.connect(lambda ch=channel: self._on_audio_preview(ch))
            self.audio_strips[channel] = strip
            audio_row.addWidget(strip)
        audio_row.addStretch(1)
        page_layout.addWidget(audio_card)

        # ── SFX / Jumpscares ───────────────────────────────────────────────
        sfx_card, sfx_row = self._make_mixer_card("SFX / Jumpscares", _STRIP_H)
        self.sfx_strips: dict[str, AudioChannelStrip] = {}
        for n in (1, 2, 3):
            key = f"sfx{n}"
            strip = AudioChannelStrip(f"SFX {n}", show_preview=True)
            strip.volume_changed.connect(
                lambda value, k=key: self._on_audio_volume_changed(k, value)
            )
            strip.mute_toggled.connect(
                lambda checked, k=key: self._on_audio_mute_toggled(k, checked)
            )
            strip.preview_clicked.connect(lambda k=key: self._on_sfx_preview(k))
            self.sfx_strips[key] = strip
            sfx_row.addWidget(strip)
        sfx_row.addStretch(1)
        page_layout.addWidget(sfx_card)

        # ── Videos ────────────────────────────────────────────────────────
        videos_card = QWidget()
        videos_card.setObjectName("mixerSectionCard")
        videos_card_layout = QVBoxLayout(videos_card)
        videos_card_layout.setContentsMargins(12, 10, 12, 12)
        videos_card_layout.setSpacing(8)

        videos_title = QLabel("Videos")
        videos_title.setObjectName("mixerSectionTitle")
        videos_card_layout.addWidget(videos_title)

        self.video_strips_container = QWidget()
        self.video_strips_layout = QHBoxLayout(self.video_strips_container)
        self.video_strips_layout.setContentsMargins(4, 4, 4, 4)
        self.video_strips_layout.setSpacing(16)
        self.video_strips_layout.addStretch(1)

        self.video_strips_scroll = _NoZoomScrollArea()
        self.video_strips_scroll.setWidgetResizable(True)
        self.video_strips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.video_strips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video_strips_scroll.setFixedHeight(_STRIP_H)
        self.video_strips_scroll.setWidget(self.video_strips_container)
        videos_card_layout.addWidget(self.video_strips_scroll)

        self.no_videos_label = QLabel("No videos configured for this room yet.")
        self.no_videos_label.setObjectName("audioMixerCaption")
        videos_card_layout.addWidget(self.no_videos_label)

        page_layout.addWidget(videos_card)
        page_layout.addStretch(1)

        outer.addWidget(page_scroll, stretch=1)
        return panel

    def _make_mixer_card(self, title: str, strip_height: int) -> tuple[QWidget, QHBoxLayout]:
        """Return a styled section card and the inner QHBoxLayout for adding strips to."""
        card = QWidget()
        card.setObjectName("mixerSectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 12)
        card_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("mixerSectionTitle")
        card_layout.addWidget(title_label)

        scroll = _NoZoomScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(strip_height)

        inner = QWidget()
        inner_layout = QHBoxLayout(inner)
        inner_layout.setContentsMargins(4, 4, 4, 4)
        inner_layout.setSpacing(16)
        scroll.setWidget(inner)

        card_layout.addWidget(scroll)
        return card, inner_layout

    def _build_controls_column(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("columnPanel")
        panel.setFixedWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Controls")
        header.setObjectName("columnHeader")
        layout.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        self.complete_game_button = QPushButton("Complete game")
        self.complete_game_button.setObjectName("primaryButton")
        self.complete_game_button.clicked.connect(self._on_complete_game)
        content_layout.addWidget(self.complete_game_button)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(6)
        self.puzzles_stat = self._build_stat_box("Puzzles")
        self.messages_stat = self._build_stat_box("Messages")
        self.time_adjusted_stat = self._build_stat_box("Time Adj.")
        for box, _ in (self.puzzles_stat, self.messages_stat, self.time_adjusted_stat):
            stats_row.addWidget(box)
        content_layout.addLayout(stats_row)

        content_layout.addWidget(self._build_section_separator())

        self.open_player_button = QPushButton("Open player window")
        self.open_player_button.clicked.connect(self._on_open_player_window)
        content_layout.addWidget(self.open_player_button)

        self.briefing_video_en_button = QPushButton("▶ Briefing Video (English)")
        self.briefing_video_en_button.setObjectName("playVideoButton")
        self.briefing_video_en_button.clicked.connect(self._on_play_briefing_video_en)
        content_layout.addWidget(self.briefing_video_en_button)

        self.briefing_video_fr_button = QPushButton("▶ Briefing Video (French)")
        self.briefing_video_fr_button.setObjectName("playVideoButton")
        self.briefing_video_fr_button.clicked.connect(self._on_play_briefing_video_fr)
        content_layout.addWidget(self.briefing_video_fr_button)

        content_layout.addWidget(self._build_section_separator())

        self.timer_label = QLabel("00:00")
        self.timer_label.setObjectName("timerLabel")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.timer_label)

        content_layout.addWidget(self._build_time_adjuster())

        self.start_pause_button = QPushButton("Start game")
        self.start_pause_button.setObjectName("primaryButton")
        self.start_pause_button.clicked.connect(self._on_start_pause)
        content_layout.addWidget(self.start_pause_button)

        self.reset_button = QPushButton("Reset game")
        self.reset_button.setObjectName("dangerButton")
        self.reset_button.clicked.connect(self._on_reset_game)
        content_layout.addWidget(self.reset_button)

        content_layout.addWidget(self._build_section_separator())

        clue_tracker_header = QLabel("Clues")
        clue_tracker_header.setObjectName("sectionHeader")
        content_layout.addWidget(clue_tracker_header)
        self.clue_buttons_layout = QHBoxLayout()
        self.clue_buttons_layout.setSpacing(8)
        self.clue_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clue_buttons_container = QWidget()
        clue_buttons_container.setLayout(self.clue_buttons_layout)
        content_layout.addWidget(clue_buttons_container)

        self.hide_clue_icons_checkbox = QCheckBox("Hide clue icons on player window")
        self.hide_clue_icons_checkbox.toggled.connect(self._on_hide_clue_icons_toggled)
        content_layout.addWidget(self.hide_clue_icons_checkbox)

        content_layout.addWidget(self._build_section_separator())

        preview_header = QLabel("Player Screen")
        preview_header.setObjectName("sectionHeader")
        content_layout.addWidget(preview_header)

        self.player_preview_label = QLabel("Player window not open")
        self.player_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.player_preview_label.setStyleSheet(
            "background-color: #0D1019; border: 1px solid #2E3648; border-radius: 4px; color: #5A6178; font-size: 11px;"
        )
        self.player_preview_label.setMinimumHeight(130)
        content_layout.addWidget(self.player_preview_label)

        content_layout.addStretch(1)

        controls_scroll = _NoZoomScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        controls_scroll.setWidget(content)
        layout.addWidget(controls_scroll, stretch=1)
        return panel

    def _build_time_adjuster(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        def _make_row(specs: list[tuple[str, int, str]]) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(5)
            for label, delta, obj_name in specs:
                btn = QPushButton(label)
                btn.setObjectName(obj_name)
                btn.clicked.connect(lambda _, d=delta: self._apply_time_delta(d))
                row.addWidget(btn)
            return row

        layout.addLayout(_make_row([
            ("−5 min", -300, "timeRemoveBtn"),
            ("−1 min", -60,  "timeRemoveBtn"),
            ("+1 min",  60,  "timeAddBtn"),
            ("+5 min",  300, "timeAddBtn"),
        ]))
        layout.addLayout(_make_row([
            ("−30 sec", -30, "timeRemoveBtn"),
            ("−10 sec", -10, "timeRemoveBtn"),
            ("+10 sec",  10, "timeAddBtn"),
            ("+30 sec",  30, "timeAddBtn"),
        ]))
        return widget

    def _build_stat_box(self, label_text: str) -> tuple[QWidget, QLabel]:
        box = QFrame()
        box.setObjectName("columnPanel")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        value_label = QLabel("0")
        value_label.setObjectName("statBoxValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        caption = QLabel(label_text)
        caption.setObjectName("statBoxLabel")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setWordWrap(True)
        layout.addWidget(caption)
        return box, value_label

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("bottomBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)

        exit_button = QPushButton("Exit to Dashboard")
        exit_button.clicked.connect(self.back_to_dashboard.emit)
        layout.addWidget(exit_button)

        layout.addStretch(1)

        self.bottom_room_label = QLabel("")
        self.bottom_room_label.setObjectName("statusBarText")
        layout.addWidget(self.bottom_room_label)

        layout.addSpacing(20)

        self.bottom_stats_label = QLabel("")
        self.bottom_stats_label.setObjectName("statusBarText")
        layout.addWidget(self.bottom_stats_label)

        layout.addStretch(1)

        version_label = QLabel(f"VERSION {APP_VERSION}")
        version_label.setObjectName("statusBarText")
        layout.addWidget(version_label)

        return bar

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        room = database.get_room(self.room_id)
        if room is None:
            return
        self.room = room
        self.audio_settings = database.get_audio_settings(self.room_id)
        self.room_name_label.setText(room.name)
        self._refresh_objectives()
        self._refresh_clue_buttons()
        self._refresh_session_display()
        self._refresh_stats()
        self._refresh_briefing_buttons()
        self._refresh_audio_mixer()
        self._refresh_video_strips()
        self._apply_audio_settings()
        if self.player_window is not None:
            self.player_window.set_background_image(resolve_path(self.room.background_image_path))
        self._update_bottom_bar()

    def _refresh_briefing_buttons(self) -> None:
        self._refresh_briefing_button(self.briefing_video_en_button, self.room.intro_video_path)
        self._refresh_briefing_button(self.briefing_video_fr_button, self.room.intro_video_path_fr)

    def _refresh_briefing_button(self, button: QPushButton, path: Optional[str]) -> None:
        button.setEnabled(bool(path))
        if path:
            button.setToolTip(f"Plays: {Path(path).name}\n{path}")
        else:
            button.setToolTip(
                "No briefing video set. Add one via Edit Objectives & Clues > Videos."
            )

    def _update_bottom_bar(self) -> None:
        room = self.room
        self.bottom_room_label.setText(room.name)
        total = room.wins + room.losses
        rate = (room.wins / total * 100) if total else 0.0
        self.bottom_stats_label.setText(
            f"Success Rate: {rate:.0f}%   Wins: {room.wins}   Losses: {room.losses}"
        )

    def _refresh_stats(self) -> None:
        objectives = database.list_objectives(self.room_id)
        done = sum(1 for o in objectives if o.completed)
        total = len(objectives)
        self._set_stat(self.puzzles_stat, f"{done}/{total}")
        session = database.get_session(self.room_id)
        self._set_stat(self.messages_stat, str(session.messages_sent))
        adjusted_minutes = session.time_adjusted_seconds // 60
        sign = "+" if adjusted_minutes > 0 else ""
        self._set_stat(self.time_adjusted_stat, f"{sign}{adjusted_minutes}")

    def _set_stat(self, stat: tuple[QWidget, QLabel], value: str) -> None:
        stat[1].setText(value)

    def _refresh_session_display(self) -> None:
        session = database.get_session(self.room_id)
        self.timer_label.setText(_format_time(session.remaining_seconds))
        if self.player_window is not None:
            self.player_window.set_time(session.remaining_seconds)
            if session.status == "running":
                self.player_window.play_music()
            else:
                self.player_window.pause_music()
        if session.status == "running":
            self.start_pause_button.setText("Pause game")
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.start_pause_button.setText("Start game")
            if self.timer.isActive():
                self.timer.stop()

    # ------------------------------------------------------------------
    # Objectives column
    # ------------------------------------------------------------------

    def _refresh_objectives(self, select_id: Optional[int] = None) -> None:
        if select_id is None:
            current = self.objectives_list.currentItem()
            if current is not None:
                select_id = current.data(Qt.ItemDataRole.UserRole)
        self.objectives_list.clear()
        self.objectives = database.list_objectives(self.room_id)
        if not self.objectives:
            placeholder = QListWidgetItem("No objectives yet.\nUse + Add Objective below.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.objectives_list.addItem(placeholder)
            self._refresh_detail()
            return
        selected_item = None
        for objective in self.objectives:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, objective.id)
            self.objectives_list.addItem(item)
            widget = self._build_objective_item_widget(objective)
            item.setSizeHint(widget.sizeHint())
            self.objectives_list.setItemWidget(item, widget)
            if objective.id == select_id:
                selected_item = item
        if selected_item is None and self.objectives_list.count() > 0:
            selected_item = self.objectives_list.item(0)
        if selected_item is not None:
            self.objectives_list.setCurrentItem(selected_item)
        else:
            self._refresh_detail()

    def _build_objective_item_widget(self, objective) -> QWidget:
        widget = QWidget()
        widget.setObjectName("objectiveItemWidget")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 6, 8, 6)
        icon = QLabel("✓" if objective.completed else "○")
        layout.addWidget(icon)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        title_label = QLabel(objective.title)
        title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        title_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        if objective.code:
            code_label = QLabel(f"CODE: {objective.code}")
            code_label.setObjectName("objectiveCode")
            text_layout.addWidget(code_label)
        layout.addLayout(text_layout, 1)
        return widget

    def _selected_objective(self):
        item = self.objectives_list.currentItem()
        if item is None:
            return None
        objective_id = item.data(Qt.ItemDataRole.UserRole)
        return next((o for o in self.objectives if o.id == objective_id), None)

    # ------------------------------------------------------------------
    # Objective detail column
    # ------------------------------------------------------------------

    def _refresh_detail(self, *_args) -> None:
        objective = self._selected_objective()
        if objective is None:
            self.complete_button.setEnabled(False)
            self.complete_button.setText("Mark Complete")
            self.detail_title_label.setText("")
            self.detail_code_label.setText("")
            self.detail_description_label.setText("")
            self.clues_detail_list.clear()
            return
        self.complete_button.setEnabled(True)
        self.complete_button.setText(
            "Mark Incomplete" if objective.completed else "Mark Complete"
        )
        self.detail_title_label.setText(objective.title)
        self.detail_code_label.setText(f"CODE: {objective.code}" if objective.code else "")
        self.detail_description_label.setText(objective.description or "")
        self._refresh_clue_cards(objective)

    def _refresh_clue_cards(self, objective) -> None:
        self.clues_detail_list.blockSignals(True)
        self.clues_detail_list.clear()
        for hint in database.list_hints(objective.id):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, hint.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, hint.text)
            widget = self._build_clue_card_widget(hint, objective)
            item.setSizeHint(widget.sizeHint())
            self.clues_detail_list.addItem(item)
            self.clues_detail_list.setItemWidget(item, widget)
        self.clues_detail_list.blockSignals(False)

    def _build_clue_card_widget(self, hint, objective) -> QWidget:
        widget = QWidget()
        widget.setObjectName("clueCardWidget")
        widget.setToolTip("Click to send clue • Double-click to edit")
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 6, 8, 6)

        top_row = QHBoxLayout()
        text_label = QLabel(hint.text)
        text_label.setWordWrap(True)
        top_row.addWidget(text_label, stretch=1)
        if hint.video_path:
            play_button = QPushButton("▶")
            play_button.setObjectName("playVideoButton")
            play_button.setFixedWidth(32)
            play_button.clicked.connect(lambda _, path=hint.video_path: self._play_video(path))
            top_row.addWidget(play_button)
        layout.addLayout(top_row)

        bottom_row = QHBoxLayout()
        tag_label = QLabel(objective.title)
        tag_label.setObjectName("clueTag")
        bottom_row.addWidget(tag_label)
        bottom_row.addStretch(1)
        bottom_row.addWidget(RatingDots(hint.rating))
        layout.addLayout(bottom_row)

        return widget

    def _on_hints_reordered(self, *_args) -> None:
        objective = self._selected_objective()
        if objective is None:
            return
        ordered_ids = [
            self.clues_detail_list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.clues_detail_list.count())
        ]
        database.reorder_hints(objective.id, ordered_ids)

    def _on_clue_card_clicked(self, item: QListWidgetItem) -> None:
        text = item.data(Qt.ItemDataRole.UserRole + 1)
        if not text:
            return
        self.message_edit.setText(text)
        self.message_edit.setFocus()
        self.message_edit.selectAll()

    def _on_clue_card_double_clicked(self, item: QListWidgetItem) -> None:
        hint_id = item.data(Qt.ItemDataRole.UserRole)
        if hint_id is None:
            return
        self._edit_clue_by_id(hint_id)

    def _on_clue_context_menu(self, pos) -> None:
        item = self.clues_detail_list.itemAt(pos)
        if item is None:
            return
        hint_id = item.data(Qt.ItemDataRole.UserRole)
        if hint_id is None:
            return
        menu = QMenu(self)
        edit_action = menu.addAction("Edit Clue")
        delete_action = menu.addAction("Delete Clue")
        action = menu.exec(self.clues_detail_list.mapToGlobal(pos))
        if action == edit_action:
            self._edit_clue_by_id(hint_id)
        elif action == delete_action:
            self._delete_clue_by_id(hint_id)

    def _edit_clue_by_id(self, hint_id: int) -> None:
        objective = self._selected_objective()
        if objective is None:
            return
        hints = database.list_hints(objective.id)
        hint = next((h for h in hints if h.id == hint_id), None)
        if hint is None:
            return
        dialog = HintEditorDialog(
            parent=self,
            text=hint.text,
            rating=hint.rating,
            video_path=hint.video_path,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            text, rating, video_path = dialog.values()
            if text:
                database.update_hint(hint_id, text=text, rating=rating, video_path=video_path)
                self._refresh_detail()
                self._refresh_clue_buttons()

    def _delete_clue_by_id(self, hint_id: int) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete Clue",
            "Delete this clue permanently?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            database.delete_hint(hint_id)
            self._refresh_detail()
            self._refresh_clue_buttons()

    def _toggle_objective_complete(self) -> None:
        objective = self._selected_objective()
        if objective is None:
            return
        new_state = not objective.completed
        database.set_objective_progress(self.room_id, objective.id, new_state)
        if new_state and objective.checkpoint_video_path:
            self._play_video(objective.checkpoint_video_path)
        self._refresh_objectives(select_id=objective.id)
        self._refresh_stats()

    # ------------------------------------------------------------------
    # Message feed
    # ------------------------------------------------------------------

    def _remove_feed_separator(self) -> None:
        if self._feed_separator is not None:
            row = self.feed_list.row(self._feed_separator)
            if row >= 0:
                self.feed_list.takeItem(row)
            self._feed_separator = None

    def _on_send_message(self) -> None:
        text = self.message_edit.text().strip()
        if not text:
            return
        self._remove_feed_separator()
        sep = QListWidgetItem()
        sep.setData(Qt.ItemDataRole.UserRole, "separator")
        sep.setFlags(Qt.ItemFlag.NoItemFlags)
        self.feed_list.addItem(sep)
        self._feed_separator = sep
        timestamp = datetime.now().strftime("%H:%M")
        self.feed_list.addItem(f"[{timestamp}] {text}")
        self.feed_list.scrollToBottom()
        self.message_edit.clear()
        new_count = database.increment_session_messages(self.room_id)
        self._set_stat(self.messages_stat, str(new_count))
        self._play_alert_sound()
        if self.player_window is not None:
            self.player_window.show_message(text)

    def _on_clear_player_window(self) -> None:
        self._remove_feed_separator()
        if self.player_window is not None:
            self.player_window.clear_message()

    # ------------------------------------------------------------------
    # Player window
    # ------------------------------------------------------------------

    def _ensure_player_window(self) -> PlayerWindow:
        if self.player_window is None:
            self.player_window = PlayerWindow(room_name=self.room.name)
            self.player_window.video_finished.connect(self._on_video_finished)
            self.player_window.set_clue_icons_hidden(self.hide_clue_icons_checkbox.isChecked())
            self._sync_player_clue_states()
            session = database.get_session(self.room_id)
            self.player_window.set_time(session.remaining_seconds)
            self.player_window.set_background_image(resolve_path(self.room.background_image_path))
            self._apply_audio_settings()
            if session.status == "running":
                self.player_window.play_music()
        self.player_window.show()
        self.player_window.raise_()
        return self.player_window

    def _send_to_secondary_screen(self) -> None:
        """Move the player window to the secondary monitor and fullscreen it.
        Called every time the game master clicks 'Open Player Window' so the
        window is always restored to the correct screen even if it was
        accidentally moved or un-fullscreened."""
        secondary = self._secondary_screen()
        if secondary is None:
            return
        player = self._ensure_player_window()
        if player.isFullScreen():
            player.showNormal()
        player.move(secondary.geometry().topLeft())
        player.showFullScreen()

    def _secondary_screen(self):
        """Return a screen other than the one this control panel is on."""
        current_screen = self.screen()
        for screen in QGuiApplication.screens():
            if screen is not current_screen:
                return screen
        return None

    def _play_video(self, path: str, on_finished: Optional[Callable[[], None]] = None) -> None:
        path = resolve_path(path) or path
        player = self._ensure_player_window()
        self._current_video_path = path
        self._video_finished_callback = on_finished
        if Path(path).suffix.lower() in AUDIO_EXTENSIONS:
            player.play_audio(path)
        else:
            player.play_video(path)
        self._apply_video_volume()

    def _on_video_finished(self) -> None:
        callback = self._video_finished_callback
        self._video_finished_callback = None
        if callback is not None:
            callback()

    def _update_player_preview(self) -> None:
        if self.player_window is None or not self.player_window.isVisible():
            self.player_preview_label.setText("Player window not open")
            self.player_preview_label.setPixmap(QPixmap())
            return
        # grabWindow captures GPU-rendered content (e.g. video frames) that
        # widget.grab() misses because video uses a hardware overlay.
        try:
            screen = self.player_window.screen() or QGuiApplication.primaryScreen()
            px = screen.grabWindow(int(self.player_window.winId()))
        except Exception:
            px = self.player_window.grab()
        if px.isNull():
            return
        scaled = px.scaled(
            self.player_preview_label.width(),
            self.player_preview_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.player_preview_label.setText("")
        self.player_preview_label.setPixmap(scaled)

    def _on_open_player_window(self) -> None:
        self._send_to_secondary_screen()
        self._ensure_player_window()

    def _on_toggle_player_fullscreen(self) -> None:
        self._ensure_player_window().toggle_fullscreen()

    def _on_play_briefing_video_en(self) -> None:
        if self.room.intro_video_path:
            self._play_video(self.room.intro_video_path, on_finished=self._auto_start_after_briefing)

    def _on_play_briefing_video_fr(self) -> None:
        if self.room.intro_video_path_fr:
            self._play_video(self.room.intro_video_path_fr, on_finished=self._auto_start_after_briefing)

    def _auto_start_after_briefing(self) -> None:
        if database.get_session(self.room_id).status == "idle":
            self._on_start_pause()

    # ------------------------------------------------------------------
    # Audio mixer
    # ------------------------------------------------------------------

    def _on_tab_clicked(self, button_id: int) -> None:
        self.page_stack.setCurrentIndex(button_id)

    def _refresh_audio_mixer(self) -> None:
        settings = self.audio_settings
        for channel, strip in self.audio_strips.items():
            strip.set_volume(getattr(settings, f"{channel}_volume"))
            strip.set_muted(getattr(settings, f"{channel}_muted"))
        for channel in ("alert", "game_music", "success", "fail"):
            path = getattr(settings, f"{channel}_path")
            self.audio_strips[channel].set_status("Ready to Play" if path else "No Status")
        self.audio_strips["video"].set_status("No Status")
        self.audio_strips["master"].set_status("Master")
        for n in (1, 2, 3):
            key = f"sfx{n}"
            strip = self.sfx_strips[key]
            strip.set_volume(getattr(settings, f"{key}_volume"))
            strip.set_muted(getattr(settings, f"{key}_muted"))
            name = getattr(settings, f"{key}_name")
            path = getattr(settings, f"{key}_path")
            strip.set_name(name)
            strip.set_status("Ready to Play" if path else "No file")
            self._sfx_buttons[n - 1].setText(name)

    def _apply_audio_settings(self) -> None:
        if self.player_window is None:
            return
        settings = self.audio_settings
        self.player_window.set_music(resolve_path(settings.game_music_path))
        music_volume = audio.effective_volume(
            settings.game_music_volume,
            settings.game_music_muted,
            settings.master_volume,
            settings.master_muted,
        )
        self.player_window.set_music_volume(music_volume)
        self._apply_video_volume()

    def _on_audio_volume_changed(self, channel: str, value: int) -> None:
        database.update_audio_settings(self.room_id, **{f"{channel}_volume": value})
        self.audio_settings = database.get_audio_settings(self.room_id)
        self._apply_audio_settings()

    def _on_audio_mute_toggled(self, channel: str, checked: bool) -> None:
        database.update_audio_settings(self.room_id, **{f"{channel}_muted": checked})
        self.audio_settings = database.get_audio_settings(self.room_id)
        self._apply_audio_settings()

    def _on_audio_preview(self, channel: str) -> None:
        settings = self.audio_settings
        if channel == "alert":
            self._play_alert_sound()
        elif channel == "success":
            self._play_success_sound()
        elif channel == "fail":
            self._play_fail_sound()
        elif channel == "game_music" and settings.game_music_path:
            volume = audio.effective_volume(
                settings.game_music_volume,
                settings.game_music_muted,
                settings.master_volume,
                settings.master_muted,
            )
            audio.play_file(resolve_path(settings.game_music_path), volume)

    def _play_alert_sound(self) -> None:
        settings = self.audio_settings
        volume = audio.effective_volume(
            settings.alert_volume, settings.alert_muted, settings.master_volume, settings.master_muted
        )
        audio.play_alert(resolve_path(settings.alert_path), volume)

    def _play_success_sound(self) -> None:
        settings = self.audio_settings
        volume = audio.effective_volume(
            settings.success_volume,
            settings.success_muted,
            settings.master_volume,
            settings.master_muted,
        )
        audio.play_success(resolve_path(settings.success_path), volume)

    def _play_fail_sound(self) -> None:
        settings = self.audio_settings
        volume = audio.effective_volume(
            settings.fail_volume, settings.fail_muted, settings.master_volume, settings.master_muted
        )
        if settings.fail_path:
            audio.play_fail(resolve_path(settings.fail_path), volume)
        else:
            audio.play_alert(None, volume)

    def _on_play_sfx(self, n: int) -> None:
        settings = self.audio_settings
        path = resolve_path(getattr(settings, f"sfx{n}_path"))
        if not path:
            return
        # SFX uses only its own channel volume — not reduced by master — so
        # jumpscares always punch through at full intensity regardless of mix level.
        sfx_vol = getattr(settings, f"sfx{n}_volume")
        sfx_muted = getattr(settings, f"sfx{n}_muted")
        volume = 0.0 if sfx_muted else (sfx_vol / 100.0)
        pw = self.player_window
        if pw is not None:
            pw.duck_music()
        audio.play_sfx(path, volume, on_finished=pw.unduck_music if pw is not None else None)

    def _on_sfx_preview(self, key: str) -> None:
        n = int(key[-1])
        self._on_play_sfx(n)

    def _on_sfx_context_menu(self, n: int, btn: QPushButton) -> None:
        menu = QMenu(self)
        rename_action = menu.addAction("Rename...")
        browse_action = menu.addAction("Browse audio file...")
        clear_action = menu.addAction("Clear audio file")
        action = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if action == rename_action:
            name, ok = QInputDialog.getText(
                self, "Rename SFX", "Button label:", text=getattr(self.audio_settings, f"sfx{n}_name")
            )
            if ok and name.strip():
                database.update_audio_settings(self.room_id, **{f"sfx{n}_name": name.strip()})
                self.audio_settings = database.get_audio_settings(self.room_id)
                self._refresh_audio_mixer()
        elif action == browse_action:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Audio File", "",
                "Audio Files (*.mp3 *.wav *.ogg *.flac *.aac *.m4a);;All Files (*)"
            )
            if path:
                database.update_audio_settings(self.room_id, **{f"sfx{n}_path": to_portable_path(path)})
                self.audio_settings = database.get_audio_settings(self.room_id)
                self._refresh_audio_mixer()
        elif action == clear_action:
            database.update_audio_settings(self.room_id, **{f"sfx{n}_path": None})
            self.audio_settings = database.get_audio_settings(self.room_id)
            self._refresh_audio_mixer()

    # ------------------------------------------------------------------
    # Per-video volume sub-mixer
    # ------------------------------------------------------------------

    @staticmethod
    def _shorten(text: str, max_len: int = 14) -> str:
        return text if len(text) <= max_len else text[:max_len - 1] + "…"

    def _list_room_videos(self) -> list[tuple[str, str]]:
        videos: list[tuple[str, str]] = []
        room = self.room
        if room.intro_video_path:
            videos.append(("Briefing EN", room.intro_video_path))
        if room.intro_video_path_fr:
            videos.append(("Briefing FR", room.intro_video_path_fr))
        if room.ending_video_path:
            videos.append(("Ending", room.ending_video_path))
        for objective in database.list_objectives(self.room_id):
            if objective.checkpoint_video_path:
                videos.append((self._shorten(objective.title), objective.checkpoint_video_path))
            for hint in database.list_hints(objective.id):
                if hint.video_path:
                    videos.append((self._shorten(hint.text), hint.video_path))
        return videos

    def _refresh_video_strips(self) -> None:
        while self.video_strips_layout.count() > 1:
            item = self.video_strips_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.video_strips = {}

        videos = self._list_room_videos()
        for label, path in videos:
            strip = AudioChannelStrip(label, show_preview=True)
            volume, muted = database.get_video_volume(self.room_id, path)
            strip.set_volume(volume)
            strip.set_muted(muted)
            strip.set_status(Path(path).name)
            strip.volume_changed.connect(
                lambda value, p=path: self._on_video_volume_changed(p, value)
            )
            strip.mute_toggled.connect(
                lambda checked, p=path: self._on_video_mute_toggled(p, checked)
            )
            strip.preview_clicked.connect(lambda p=path: self._on_video_preview(p))
            self.video_strips[path] = strip
            self.video_strips_layout.insertWidget(self.video_strips_layout.count() - 1, strip)

        self.video_strips_scroll.setVisible(bool(videos))
        self.no_videos_label.setVisible(not videos)

    def _on_video_volume_changed(self, path: str, value: int) -> None:
        database.update_video_volume(self.room_id, path, volume=value)
        self._apply_video_volume()

    def _on_video_mute_toggled(self, path: str, checked: bool) -> None:
        database.update_video_volume(self.room_id, path, muted=checked)
        self._apply_video_volume()

    def _on_video_preview(self, path: str) -> None:
        volume, muted = database.get_video_volume(self.room_id, path)
        settings = self.audio_settings
        effective = audio.effective_video_volume(
            volume, muted,
            settings.video_volume, settings.video_muted,
            settings.master_volume, settings.master_muted,
        )
        audio.play_file(path, effective)

    def _apply_video_volume(self) -> None:
        if self.player_window is None or self._current_video_path is None:
            return
        volume, muted = database.get_video_volume(self.room_id, self._current_video_path)
        settings = self.audio_settings
        effective = audio.effective_video_volume(
            volume, muted,
            settings.video_volume, settings.video_muted,
            settings.master_volume, settings.master_muted,
        )
        self.player_window.set_video_volume(effective)

    # ------------------------------------------------------------------
    # Clue tracker
    # ------------------------------------------------------------------

    def _refresh_clue_buttons(self) -> None:
        room = database.get_room(self.room_id)
        count = room.clue_count if room else 3

        # Only rebuild when the count changes — preserves checked state mid-session
        if len(self.clue_buttons) == count:
            self._sync_player_clue_states()
            return

        while self.clue_buttons_layout.count():
            item = self.clue_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.clue_buttons = []

        for i in range(count):
            button = ClueLockButton(number=i + 1)
            button.toggled.connect(self._sync_player_clue_states)
            self.clue_buttons_layout.addWidget(button)
            self.clue_buttons.append(button)

        self._sync_player_clue_states()

    def _reset_clue_buttons(self) -> None:
        """Uncheck all clue buttons — called at session start/reset."""
        for btn in self.clue_buttons:
            btn.setChecked(False)

    def _sync_player_clue_states(self) -> None:
        if self.player_window is not None:
            self.player_window.set_clue_states([btn.isChecked() for btn in self.clue_buttons])

    def _on_hide_clue_icons_toggled(self, checked: bool) -> None:
        if self.player_window is not None:
            self.player_window.set_clue_icons_hidden(checked)

    # ------------------------------------------------------------------
    # Timer / session lifecycle
    # ------------------------------------------------------------------

    def _apply_time_delta(self, delta_seconds: int) -> None:
        session = database.adjust_session_time(self.room_id, delta_seconds)
        self.timer_label.setText(_format_time(session.remaining_seconds))
        if self.player_window is not None:
            self.player_window.set_time(session.remaining_seconds)
        self._refresh_stats()

    def _on_tick(self) -> None:
        session = database.get_session(self.room_id)
        remaining = max(0, session.remaining_seconds - 1)
        new_elapsed = session.elapsed_seconds + 1
        if remaining <= 0:
            self.timer.stop()
            database.record_result(self.room_id, won=False)
            database.save_session(self.room_id, "completed", 0, elapsed_seconds=new_elapsed)
            if self.player_window is not None:
                self.player_window.show_time_up()
                self.player_window.show_auto_message("GAME OVER", color="#FF3B3B")
            self._play_fail_sound()
            self.refresh_all()
            room = database.get_room(self.room_id)
            turso.push_success_rate(room.slug, room.wins, room.wins + room.losses)
            session = database.get_session(self.room_id)
            dlg = _GameOverDialog(False, self.room.name, session, self.room.duration_seconds, self)
            if dlg.exec() == _GameOverDialog.ADD_TIME:
                self._add_extra_time(dlg.extra_seconds)
            else:
                self._start_fresh_session(status="idle")
        else:
            database.save_session(self.room_id, "running", remaining, elapsed_seconds=new_elapsed)
            self.timer_label.setText(_format_time(remaining))
            if self.player_window is not None:
                self.player_window.set_time(remaining)

    def _start_fresh_session(self, status: str = "running") -> None:
        database.start_session(self.room_id, status=status)
        self.feed_list.clear()
        self._reset_clue_buttons()
        if status == "running":
            self._ensure_player_window()
        if self.player_window is not None:
            self.player_window.clear_message()
            self.player_window.show_timer()
        self.refresh_all()

    def _on_start_pause(self) -> None:
        session = database.get_session(self.room_id)
        if session.status == "running":
            self.timer.stop()
            database.save_session(self.room_id, "paused", session.remaining_seconds)
            self.refresh_all()
        elif session.status in ("idle", "completed"):
            self._start_fresh_session()
        else:
            database.save_session(self.room_id, "running", session.remaining_seconds)
            self._ensure_player_window()
            self.refresh_all()

    def _on_complete_game(self) -> None:
        self.timer.stop()
        session = database.get_session(self.room_id)
        database.record_result(self.room_id, won=True)
        database.save_session(self.room_id, "completed", session.remaining_seconds)
        self._play_success_sound()
        player = self._ensure_player_window()
        player.show_auto_message("YOU ESCAPED!", color="#F5C518")
        if self.room.ending_video_path:
            self._play_video(self.room.ending_video_path)
        self.refresh_all()
        room = database.get_room(self.room_id)
        session = database.get_session(self.room_id)
        turso.push_success_rate(room.slug, room.wins, room.wins + room.losses)
        if room.slug and self._current_booking:
            turso.insert_leaderboard_entry(
                room.slug,
                self._current_booking.get("customerName", "Unknown"),
                int(self._current_booking.get("partySize") or 0),
                max(0, room.duration_seconds - session.remaining_seconds),
            )
        _GameOverDialog(True, self.room.name, session, self.room.duration_seconds, self).exec()
        self._start_fresh_session(status="idle")

    def _on_reset_game(self) -> None:
        if (
            QMessageBox.question(
                self, "Reset Game", "Reset the timer and all progress for this room?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.timer.stop()
        self._current_booking = None
        self._refresh_link_group_button()
        self._start_fresh_session(status="idle")

    def _add_extra_time(self, extra_seconds: int) -> None:
        """Undo the time-up loss and resume the game with extra_seconds added."""
        database.undo_loss(self.room_id)
        database.save_session(self.room_id, "running", extra_seconds)
        if self.player_window is not None:
            self.player_window.show_timer()
            self.player_window.clear_message()
        self.timer.start()
        self.refresh_all()

    # ------------------------------------------------------------------
    # Room editor
    # ------------------------------------------------------------------

    def _on_quick_add_objective(self) -> None:
        title, ok = QInputDialog.getText(self, "Add Objective", "Objective title:")
        if ok and title.strip():
            new_id = database.add_objective(self.room_id, title.strip())
            self._refresh_objectives(select_id=new_id)
            self._refresh_stats()

    def _on_quick_add_clue(self) -> None:
        objective = self._selected_objective()
        if objective is None:
            QMessageBox.information(self, "No Objective Selected", "Select an objective first.")
            return
        dialog = HintEditorDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            text, rating, video_path = dialog.values()
            if text:
                database.add_hint(objective.id, text, rating=rating, video_path=video_path)
                self._refresh_detail()
                self._refresh_clue_buttons()

    def _open_room_editor(self) -> None:
        dialog = RoomEditorDialog(self.room_id, parent=self)
        dialog.exec()
        self.refresh_all()

    def _on_link_group(self) -> None:
        if not self.room.slug:
            QMessageBox.information(
                self,
                "No slug configured",
                "Set a website slug for this room in Edit Objectives & Clues first.",
            )
            return

        # If credentials are missing, let the operator enter them first
        if not os.environ.get("TURSO_DATABASE_URL") or not os.environ.get("TURSO_AUTH_TOKEN"):
            setup = _TursoSetupDialog(self)
            if setup.exec() != QDialog.DialogCode.Accepted:
                return  # user cancelled

        bookings, error = turso.fetch_bookings(self.room.slug)
        dlg = _BookingPickerDialog(bookings, error, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
            self._current_booking = dlg.selected
            self._refresh_link_group_button()

    def _refresh_link_group_button(self) -> None:
        if self._current_booking:
            name = self._current_booking.get("customerName", "Group")
            size = self._current_booking.get("partySize", "?")
            self.link_group_button.setText(f"Group: {name} ({size})")
            self.link_group_button.setProperty("linked", "true")
        else:
            self.link_group_button.setText("Link Group")
            self.link_group_button.setProperty("linked", "false")
        self.link_group_button.style().unpolish(self.link_group_button)
        self.link_group_button.style().polish(self.link_group_button)

    # ------------------------------------------------------------------
    # Window chrome
    # ------------------------------------------------------------------

    def _toggle_fullscreen(self, checked: bool) -> None:
        if checked:
            self.showFullScreen()
            self.fullscreen_button.setText("Exit Fullscreen")
        else:
            self.showNormal()
            self.fullscreen_button.setText("Fullscreen")

    def closeEvent(self, event) -> None:
        if self.timer.isActive():
            self.timer.stop()
            session = database.get_session(self.room_id)
            database.save_session(self.room_id, "paused", session.remaining_seconds)
        if self.player_window is not None:
            self.player_window.close()
        super().closeEvent(event)
