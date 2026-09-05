"""Shared colors and Qt stylesheets for the dashboard and the live Control Panel."""

# ---------------------------------------------------------------------------
# Colors used by custom-painted widgets (rating dots, lock buttons, etc.)
# ---------------------------------------------------------------------------

RATING_FILLED_COLOR = "#C9952A"
RATING_EMPTY_COLOR = "#333340"

LOCK_UNLOCKED_BG = "#28282E"
LOCK_UNLOCKED_FG = "#8A8896"
LOCK_LOCKED_BG = "#1A3326"
LOCK_LOCKED_FG = "#4ADE80"

PLAYER_LOCK_PENDING_COLOR = "#C9952A"
PLAYER_LOCK_USED_COLOR = "#8A8896"


# ---------------------------------------------------------------------------
# Dashboard (light theme)
# ---------------------------------------------------------------------------

DASHBOARD_STYLE = """
QMainWindow, QWidget#dashboardCentral, QWidget#dashboardScrollContent {
    background-color: #F4F3F1;
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
}

QLabel {
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
}

QPushButton {
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
}

QLabel#pageTitle {
    font-size: 26px;
    font-weight: 700;
    color: #111010;
    letter-spacing: -0.5px;
}

QLabel#sectionLabel {
    color: #6B6A68;
    font-size: 13px;
}

QPushButton#primaryButton {
    background-color: #111010;
    color: #F4F3F1;
    border: none;
    border-radius: 7px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#primaryButton:hover {
    background-color: #2A2828;
}
QPushButton#primaryButton:pressed {
    background-color: #080808;
}

QPushButton#secondaryButton {
    background-color: #FFFFFF;
    color: #111010;
    border: 1px solid #DDDBD8;
    border-radius: 7px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#secondaryButton:hover {
    background-color: #F0EFED;
    border-color: #C8C6C3;
}

QFrame#roomCard {
    background-color: #FFFFFF;
    border: 1px solid #E5E4E0;
    border-radius: 10px;
}

QLabel#cardTitle {
    font-size: 17px;
    font-weight: 700;
    color: #111010;
}

QLabel#statLabel {
    color: #6B6A68;
    font-size: 12px;
}

QLabel#statValue {
    color: #111010;
    font-weight: 700;
    font-size: 15px;
}

QPushButton#cardPrimaryButton {
    background-color: #111010;
    color: #F4F3F1;
    border: none;
    border-radius: 7px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#cardPrimaryButton:hover {
    background-color: #2A2828;
}

QPushButton#cardSecondaryButton {
    background-color: #F0EFED;
    color: #111010;
    border: 1px solid #DDDBD8;
    border-radius: 7px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#cardSecondaryButton:hover {
    background-color: #E5E4E0;
}

QPushButton#cardMenuButton {
    background-color: transparent;
    border: none;
    color: #9B9A98;
    font-size: 18px;
    font-weight: 700;
}
QPushButton#cardMenuButton:hover {
    color: #111010;
}

QFrame#newRoomCard {
    border: 2px dashed #DDDBD8;
    border-radius: 10px;
    background-color: #FAFAF8;
}

QPushButton#createRoomCardButton {
    background-color: #111010;
    color: #F4F3F1;
    border: none;
    border-radius: 7px;
    padding: 10px 24px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#createRoomCardButton:hover {
    background-color: #2A2828;
}

QComboBox {
    border: 1px solid #DDDBD8;
    border-radius: 7px;
    padding: 7px 10px;
    background-color: #FFFFFF;
    color: #111010;
    font-size: 13px;
}
QComboBox:hover {
    border-color: #C8C6C3;
}

QTableWidget {
    border: 1px solid #E5E4E0;
    gridline-color: #EEECEA;
    background-color: #FFFFFF;
    color: #111010;
    font-size: 13px;
}
QHeaderView::section {
    background-color: #F4F3F1;
    color: #6B6A68;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #E5E4E0;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.5px;
}
"""


# ---------------------------------------------------------------------------
# Control Panel (dark theme)
# ---------------------------------------------------------------------------

CONTROL_PANEL_STYLE = """
QMainWindow, QWidget {
    background-color: #0A0A0B;
    color: #F0EEE9;
    font-size: 13px;
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
}

QLabel {
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
}

QPushButton {
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
}

QWidget#topBar, QWidget#bottomBar {
    background-color: #060607;
    border: none;
}

QLabel#topBarTitle {
    font-weight: 700;
    font-size: 15px;
    color: #F0EEE9;
    letter-spacing: 0.5px;
}

QLabel#roomNameLabel {
    font-weight: 600;
    font-size: 15px;
    color: #C9952A;
    letter-spacing: 0.3px;
}

QLabel#statusBarText {
    color: #55546A;
    font-size: 12px;
}

QWidget#columnPanel {
    background-color: #131316;
    border: 1px solid #2A2A34;
    border-radius: 10px;
}

QLabel#columnHeader {
    background-color: #1A1A20;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 11px 14px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    color: #6B6A80;
}

QLabel#objectiveTitle {
    font-size: 16px;
    font-weight: 700;
    color: #F0EEE9;
    letter-spacing: -0.2px;
}

QLabel#objectiveCode, QLabel#clueTag {
    color: #55546A;
    font-size: 12px;
    letter-spacing: 0.5px;
}

QLabel#objectiveDescription {
    color: #A8A6B0;
    font-size: 13px;
    line-height: 1.5;
}

QLabel#sectionHeader {
    color: #55546A;
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

QFrame#columnSeparator {
    background-color: #1E1E26;
    border: none;
}

QFrame#sectionSeparator {
    background-color: #1A1A20;
    border: none;
}

QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    border-bottom: 1px solid #1A1A20;
    padding: 2px 0;
    border-radius: 0;
}
QListWidget::item:hover {
    background-color: #1A1A20;
}
QListWidget::item:selected {
    background-color: #1E1C18;
    border-left: 3px solid #C9952A;
}

QWidget#objectiveItemWidget,
QWidget#objectiveItemWidget QLabel,
QWidget#clueCardWidget,
QWidget#clueCardWidget QLabel {
    background-color: transparent;
}

QPushButton {
    background-color: #1C1C22;
    color: #C8C6D0;
    border: 1px solid #333340;
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 500;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #252530;
    color: #F0EEE9;
    border-color: #46455A;
}
QPushButton:pressed {
    background-color: #131318;
    border-color: #2A2A34;
    color: #A8A6B0;
}
QPushButton:disabled {
    color: #3A3A48;
    background-color: #111114;
    border-color: #1E1E26;
}
QPushButton:checked {
    background-color: #252530;
    border-color: #46455A;
    color: #F0EEE9;
}

QPushButton#primaryButton {
    background-color: #EBEBEB;
    color: #111010;
    border: none;
    font-weight: 700;
    font-size: 14px;
    padding: 12px 14px;
    border-radius: 7px;
}
QPushButton#primaryButton:hover {
    background-color: #FFFFFF;
}
QPushButton#primaryButton:pressed {
    background-color: #D0D0D0;
    border: none;
}

QPushButton#dangerButton {
    color: #F87171;
    border-color: #3D2020;
    background-color: #1C1414;
}
QPushButton#dangerButton:hover {
    background-color: #2E1818;
    color: #FCA5A5;
    border-color: #5A2A2A;
}

QPushButton#timeAddBtn {
    background-color: #0F2A1C;
    color: #4ADE80;
    border: 1px solid #1A4530;
    border-radius: 7px;
    font-weight: 700;
    font-size: 12px;
    padding: 8px 4px;
}
QPushButton#timeAddBtn:hover {
    background-color: #163824;
    color: #6EF0A0;
    border-color: #2A6044;
}
QPushButton#timeAddBtn:pressed {
    background-color: #081A10;
}

QPushButton#timeRemoveBtn {
    background-color: #2A1010;
    color: #F87171;
    border: 1px solid #3D2020;
    border-radius: 7px;
    font-weight: 700;
    font-size: 12px;
    padding: 8px 4px;
}
QPushButton#timeRemoveBtn:hover {
    background-color: #381414;
    color: #FCA5A5;
    border-color: #5A2A2A;
}
QPushButton#timeRemoveBtn:pressed {
    background-color: #1A0808;
}

QPushButton#playVideoButton {
    background-color: #18202E;
    color: #94A8C4;
    border: 1px solid #2A3448;
    font-weight: 700;
}
QPushButton#playVideoButton:hover {
    background-color: #202C3E;
    color: #B8CCEE;
}

QPushButton#sfxButton {
    background-color: #0F2A1C;
    color: #4ADE80;
    border: 1px solid #1A4530;
    font-weight: 700;
    font-size: 13px;
}
QPushButton#sfxButton:hover {
    background-color: #163824;
    color: #6EF0A0;
    border-color: #2A6044;
}
QPushButton#sfxButton:pressed {
    background-color: #081A10;
}

QPushButton#linkGroupButton {
    background-color: #231A08;
    color: #C9952A;
    border: 1px solid #3D2E10;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#linkGroupButton:hover {
    background-color: #2E2210;
    color: #E0AA40;
    border-color: #5A4418;
}
QPushButton#linkGroupButton:pressed {
    background-color: #161004;
}
QPushButton#linkGroupButton[linked="true"] {
    background-color: #0F2A1C;
    color: #4ADE80;
    border-color: #1A4530;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #060607;
    border: 1px solid #2A2A34;
    border-radius: 7px;
    padding: 8px 10px;
    color: #F0EEE9;
    selection-background-color: #333340;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #C9952A;
}

QLabel#timerLabel {
    font-size: 52px;
    font-weight: 700;
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
    color: #F0EEE9;
    letter-spacing: -1px;
}

QLabel#statBoxValue {
    font-size: 22px;
    font-weight: 700;
    color: #F0EEE9;
    letter-spacing: -0.5px;
}
QLabel#statBoxLabel {
    color: #55546A;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
}

QCheckBox {
    color: #A8A6B0;
    font-size: 12px;
    spacing: 7px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #46455A;
    border-radius: 4px;
    background-color: #060607;
}
QCheckBox::indicator:checked {
    background-color: #C9952A;
    border-color: #C9952A;
}

QPushButton#tabButton {
    background-color: transparent;
    color: #55546A;
    font-weight: 600;
    font-size: 13px;
    padding: 11px 18px;
    border-radius: 0;
    border: none;
    border-bottom: 2px solid transparent;
}
QPushButton#tabButton:hover {
    color: #A8A6B0;
    background-color: #0F0F12;
}
QPushButton#tabButton:checked {
    color: #F0EEE9;
    border-bottom: 2px solid #C9952A;
    background-color: transparent;
}

QWidget#mixerSectionCard {
    background-color: #131316;
    border: 1px solid #2A2A34;
    border-radius: 10px;
}

QLabel#mixerSectionTitle {
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #6B6A80;
    padding-bottom: 2px;
}

QWidget#audioChannelStrip {
    background-color: #1A1A20;
    border: 1px solid #2A2A34;
    border-radius: 8px;
}

QLabel#audioChannelName {
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.5px;
    color: #C8C6D0;
}

QLabel#audioChannelStatus {
    color: #55546A;
    font-size: 11px;
}

QWidget#audioChannelStrip QPushButton:checked {
    background-color: #2E1818;
    color: #F87171;
    border-color: #5A2A2A;
}

QLabel#audioMixerCaption {
    color: #55546A;
    font-size: 12px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:horizontal {
    background-color: #060607;
    height: 5px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal {
    background-color: #333340;
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #46455A;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar:vertical {
    background-color: #060607;
    width: 5px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background-color: #333340;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #46455A;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QSlider::groove:vertical {
    background-color: #1A1A20;
    border: 1px solid #2A2A34;
    width: 6px;
    border-radius: 3px;
}
QSlider::handle:vertical {
    background-color: #C9952A;
    height: 16px;
    margin: 0 -6px;
    border-radius: 8px;
}
QSlider::handle:vertical:hover {
    background-color: #E0AA40;
}
QSlider::sub-page:vertical {
    background-color: #2A2A34;
    border-radius: 3px;
}
QSlider::add-page:vertical {
    background-color: #C9952A;
    border-radius: 3px;
}

QTabWidget::pane {
    border: none;
    border-top: 1px solid #2A2A34;
    background-color: #0A0A0B;
}
QTabBar {
    background-color: #060607;
}
QTabBar::tab {
    background-color: #060607;
    color: #8A8896;
    font-weight: 600;
    font-size: 13px;
    padding: 11px 22px;
    border: none;
    border-bottom: 2px solid transparent;
    min-width: 80px;
}
QTabBar::tab:hover {
    color: #C8C6D0;
    background-color: #101014;
}
QTabBar::tab:selected {
    color: #F0EEE9;
    border-bottom: 2px solid #C9952A;
    background-color: #0A0A0B;
}

QMenu {
    background-color: #131316;
    border: 1px solid #2A2A34;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 8px 20px;
    border-radius: 5px;
    color: #C8C6D0;
}
QMenu::item:selected {
    background-color: #252530;
    color: #F0EEE9;
}
QMenu::separator {
    height: 1px;
    background-color: #2A2A34;
    margin: 4px 8px;
}

QToolTip {
    background-color: #1A1A20;
    color: #C8C6D0;
    border: 1px solid #333340;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
}
"""


# ---------------------------------------------------------------------------
# Player window (player-facing display)
# ---------------------------------------------------------------------------

PLAYER_WINDOW_STYLE = """
QWidget {
    color: #F0EEE9;
}

QWidget#playerWindowRoot {
    background-color: #000000;
}

QWidget#playerVideoPage {
    background-color: #000000;
}

QWidget#playerTimerPage,
QWidget#playerStackContainer,
QWidget#playerCenterContainer,
QWidget#playerTimerView,
QWidget#playerMessageView,
QWidget#playerClueStrip {
    background-color: transparent;
}

QLabel#playerTimer {
    font-size: 138px;
    font-weight: 700;
    font-family: "Impact", "DejaVu Sans Mono", "Consolas", monospace;
    color: #F0EEE9;
}

QLabel#playerTimerCaption {
    font-size: 32px;
    font-weight: 500;
    letter-spacing: 4px;
    color: #8A8896;
}

QLabel#playerTimerCompact {
    background-color: rgba(30, 28, 24, 230);
    color: #F0EEE9;
    font-size: 46px;
    font-weight: 700;
    font-family: "Impact", "DejaVu Sans Mono", "Consolas", monospace;
    padding: 10px 26px;
    border-radius: 14px;
}

QLabel#playerTimeUp {
    font-size: 74px;
    font-weight: 700;
    color: #F87171;
}

QLabel#playerMessage {
    background-color: rgba(19, 19, 22, 235);
    color: #F0EEE9;
    font-size: 60px;
    font-weight: 700;
    font-family: "Segoe UI Variable", "Segoe UI", "Arial", sans-serif;
    padding: 32px 44px;
    border-radius: 20px;
}
"""
