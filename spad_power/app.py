from __future__ import annotations
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QKeySequence, QPalette
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGroupBox, QDoubleSpinBox, QCheckBox, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog, QAbstractItemView, QSplitter,
    QScrollArea, QToolButton, QFrame, QAbstractSpinBox, QSizePolicy, QComboBox)
from spad_power.model import Settings, Channel, calculate, recommend_fixed_od

# key, label, unit, min, max, decimals, primary (shown large; others folded under "探头与滤片设置")
FIELDS = [
    ('frequency_khz', '重复频率', 'kHz', 0.000001, 1e6, 6, True),
    ('pulse_ns', '光脉冲高值宽度', 'ns', 0.000001, 1e12, 6, True),
    ('photons', '平均入射光子数 / 脉冲', '', 0.000001, 1e9, 6, True),
    ('major_um', '椭圆完整长轴', 'μm', 0.001, 1e6, 3, True),
    ('minor_um', '椭圆完整短轴', 'μm', 0.001, 1e6, 3, True),
    ('probe_diameter_mm', '探头有效孔径直径', 'mm', 0.001, 1000, 3, False),
    ('probe_min_nw', '探头参考测量下限', 'nW', 0.000001, 1e9, 6, False),
    ('variable_min', '可变 OD 下限', '', 0, 30, 4, False),
    ('variable_max', '可变 OD 上限', '', 0, 30, 4, False),
]
FIELD_TIPS = {
    'frequency_khz': '激光重复频率，用于平均功率换算。',
    'pulse_ns': '实际光脉冲宽度（电调制宽度未必相同）。决定占空比，CW 校准读数和所需 OD 都随之变化。',
    'photons': '每个脉冲平均入射的光子数（统计均值，不是探测计数）。',
    'major_um': '椭圆像元的完整长轴（不是半轴）。',
    'minor_um': '椭圆像元的完整短轴（不是半轴）。',
    'probe_diameter_mm': '功率计探头有效孔径直径；默认 S130VC 参考值 9.5 mm。',
    'probe_min_nw': '低于此值时提示读数偏低；不代表测量精度保证。',
    'variable_min': '可变衰减可调范围下限，用于判断滤片能否覆盖。',
    'variable_max': '可变衰减可调范围上限，用于判断滤片能否覆盖。',
}
# CSV export keeps this order; the on-screen table uses DISPLAY_ORDER.
COLUMNS = [
    ('wavelength_nm', '波长\n(nm)'), ('device_avg_pw', '器件脉冲平均功率\n(pW)'),
    ('density_avg_pw_cm2', '目标脉冲平均功率密度\n(pW/cm²)'),
    ('density_cw_nw_cm2', 'CW 插衰减片功率密度\n(nW/cm²)'),
    ('calibration_nw_cm2', 'CW 不插衰减片功率密度\n(nW/cm²)'),
    ('probe_nw', 'CW 不插衰减片探头读数\n(nW)'), ('total_od', '所需总 OD'),
    ('variable_od', '所需可变 OD'), ('transmission', '所需总透过率\n(0～1)'),
    ('measured_nw_cm2', 'CW 无衰减功率密度\n(nW/cm²)'), ('status', '提示'),
]
DISPLAY_ORDER = ['wavelength_nm', 'density_avg_pw_cm2', 'probe_nw', 'calibration_nw_cm2', 'total_od',
    'variable_od', 'device_avg_pw', 'density_cw_nw_cm2', 'transmission', 'measured_nw_cm2', 'status']
KEY_COLUMNS = {'density_avg_pw_cm2', 'probe_nw'}
MINOR_COLUMNS = {'device_avg_pw', 'density_cw_nw_cm2', 'transmission', 'measured_nw_cm2'}
COLUMN_TIPS = {
    'density_avg_pw_cm2': '脉冲模式、插入衰减片后器件处应达到的周期平均功率密度（每脉冲 μ 个入射光子）。',
    'probe_nw': 'CW 模式、取出衰减片时探头应读到的功率（校准时调到此读数，再插回衰减片并切到脉冲模式）；需勾选均匀覆盖确认。',
    'calibration_nw_cm2': 'CW 模式、取出衰减片时器件处的功率密度 = 目标 / 占空比 × 10^(衰减片 OD)。',
    'total_od': 'CW 无衰减功率密度 × 占空比衰减到目标所需的总 OD；需填写 CW 实测值。',
    'variable_od': '总 OD − 衰减片 OD，即衰减片之外还需可变衰减承担的部分，与可变 OD 上下限比较。',
    'device_avg_pw': '脉冲模式下像元面积内的周期平均功率。',
    'density_cw_nw_cm2': 'CW 模式、插入衰减片时器件处的功率密度 = 目标 / 占空比（即脉冲高值期间的功率密度）。',
    'transmission': '总透过率 = 10^(−总 OD)。',
    'measured_nw_cm2': 'CW 无衰减实测值换算成的功率密度；功率计读数按探头有效孔径面积换算。',
}
MEASURED_HEADERS = {
    'nW': ('CW 无衰减功率计读数 (nW，可空)', '可留空。激光切到 CW 模式（与脉冲模式相同驱动条件），不加任何衰减片（含可变衰减），'
           '在器件位置测得的功率计读数。按探头有效孔径面积换算为功率密度，需勾选均匀覆盖确认；用于计算所需总 OD 和推荐固定 OD。'),
    'nW/cm2': ('CW 无衰减功率密度 (nW/cm²，可空)', '可留空。激光切到 CW 模式（与脉冲模式相同驱动条件），不加任何衰减片（含可变衰减），'
               '器件位置的功率密度；用于计算所需总 OD 和推荐固定 OD。'),
}
CHANNEL_HEADERS = [
    ('波长 (nm)', '各波长独立计算。'),
    ('衰减片 OD（校准时移除）', '脉冲模式下插入后器件处满足单光子入射目标的外置衰减片 OD；CW 校准时取出，正式测量时插回（填该波长处的实测 OD）。'),
    ('CW 无衰减实测值', ''),  # text depends on the measured unit, see update_measured_header
]
ACCENT, ACCENT_HOVER, ACCENT_PRESSED = '#0f7a94', '#0d6b82', '#0a5a6d'
BG, CARD, BORDER, FIELD_BORDER = '#f3f5f9', '#ffffff', '#e2e7ef', '#d3dae4'
TEXT, MUTED = '#1f2a37', '#6b7686'
FONT_FAMILIES = ['PingFang SC', 'Microsoft YaHei UI', 'Segoe UI', 'Helvetica Neue', 'Noto Sans CJK SC']
BAD, WARN, GOOD = QColor('#c0392b'), QColor('#b9770e'), QColor('#1e8449')
BANNER = {
    'ok': 'rgba(15, 122, 148, 0.09); border: 1px solid rgba(15, 122, 148, 0.30)',
    'stale': 'rgba(230, 160, 30, 0.14); border: 1px solid rgba(200, 130, 20, 0.55)',
    'error': 'rgba(192, 57, 43, 0.10); border: 1px solid rgba(192, 57, 43, 0.55)',
}
STYLE = f'''
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget {{ font-size: 13px; color: {TEXT}; }}
QScrollArea, QWidget#settings {{ background: transparent; }}
QGroupBox {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px;
    margin-top: 0; padding: 42px 14px 12px 14px; font-size: 15px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: padding; subcontrol-position: top left; left: 16px; top: 14px; }}
QGroupBox QWidget {{ font-size: 13px; font-weight: 400; }}
QWidget#primary QLabel {{ font-size: 15px; min-height: 45px; }}
QWidget#advanced QLabel {{ min-height: 32px; }}
QWidget#primary QDoubleSpinBox {{ font-size: 18px; font-weight: 500; min-height: 30px; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox#uniform {{ font-size: 14px; }}
QLabel#hint {{ color: {MUTED}; font-size: 12px; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 13px; }}
QDoubleSpinBox {{ background: #ffffff; border: 1px solid {FIELD_BORDER}; border-radius: 7px;
    padding: 4px 10px; min-height: 22px; selection-background-color: {ACCENT}; selection-color: white; }}
QDoubleSpinBox:hover, QComboBox:hover {{ border-color: #b7c2d0; }}
QComboBox {{ background: #ffffff; border: 1px solid {FIELD_BORDER}; border-radius: 7px; padding: 5px 10px; min-height: 20px; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: #ffffff; border: 1px solid {BORDER}; selection-background-color: rgba(15, 122, 148, 0.16); selection-color: {TEXT}; }}
QDoubleSpinBox::up-button {{ subcontrol-origin: border; width: 0; border: none; }}
QDoubleSpinBox::down-button {{ subcontrol-origin: border; width: 0; border: none; }}
QDoubleSpinBox:focus {{ border: 2px solid {ACCENT}; padding: 3px 9px; }}
QTableWidget QLineEdit {{ border: 2px solid {ACCENT}; padding: 0 4px; background: #ffffff; }}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#cardTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#adviceOd {{ font-size: 26px; font-weight: 700; color: {ACCENT}; }}
QToolButton#section {{ border: none; background: transparent; color: {ACCENT}; font-weight: 600; padding: 4px 0; }}
QPushButton {{ background: #ffffff; border: 1px solid {FIELD_BORDER}; border-radius: 8px;
    padding: 6px 16px; min-height: 20px; font-weight: 500; }}
QPushButton:hover {{ background: #f0f4f8; border-color: #b7c2d0; }}
QPushButton:pressed {{ background: #e4eaf1; }}
QPushButton#ghost {{ background: transparent; border: none; color: #4a5565; padding: 6px 12px; }}
QPushButton#ghost:hover {{ background: #e6ebf2; color: {TEXT}; }}
QPushButton#soft {{ background: rgba(15, 122, 148, 0.10); color: {ACCENT}; border: 1px solid rgba(15, 122, 148, 0.35); font-weight: 600; }}
QPushButton#soft:hover {{ background: rgba(15, 122, 148, 0.18); }}
QPushButton#calc {{ background: {ACCENT}; color: white; border: none; border-radius: 10px;
    font-size: 17px; font-weight: 700; min-height: 48px; padding: 0 32px; }}
QPushButton#calc:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#calc:pressed {{ background: {ACCENT_PRESSED}; }}
QTableWidget {{ background: #ffffff; border: 1px solid {BORDER}; border-radius: 8px; font-size: 14px;
    alternate-background-color: #f8fafc; selection-background-color: rgba(15, 122, 148, 0.16); selection-color: {TEXT}; }}
QHeaderView {{ background: #f6f8fb; border: none; }}
QHeaderView::section {{ background: #f6f8fb; color: #4a5565; border: none; border-bottom: 1px solid {BORDER};
    padding: 6px 8px; font-weight: 600; font-size: 13px; }}
QHeaderView::section:vertical {{ border-bottom: none; color: {MUTED}; font-weight: 400; padding: 0 8px; }}
QTableCornerButton::section {{ background: #f6f8fb; border: none; border-bottom: 1px solid {BORDER}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: #c9d1dc; border-radius: 3px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: #aab5c3; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QSplitter::handle {{ background: transparent; }}
QToolTip {{ background: {TEXT}; color: white; border: none; padding: 6px 8px; }}
'''


def light_palette():
    # The style sheet assumes a light theme; without this, a dark system palette leaks into
    # palette-drawn parts such as check box indicators (dark box with a dark check mark).
    palette = QPalette()
    role = QPalette.ColorRole
    for key, color in [(role.Window, BG), (role.WindowText, TEXT), (role.Base, '#ffffff'), (role.AlternateBase, '#f8fafc'),
                       (role.Text, TEXT), (role.Button, '#ffffff'), (role.ButtonText, TEXT), (role.BrightText, '#ffffff'),
                       (role.ToolTipBase, TEXT), (role.ToolTipText, '#ffffff'), (role.PlaceholderText, MUTED),
                       (role.Highlight, ACCENT), (role.HighlightedText, '#ffffff'), (role.Link, ACCENT),
                       (role.Light, '#ffffff'), (role.Midlight, '#eef1f5'), (role.Mid, FIELD_BORDER),
                       (role.Dark, '#9aa5b4'), (role.Shadow, MUTED)]:
        palette.setColor(key, QColor(color))
    return palette


def apply_light_theme(app):
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(light_palette())


def status_color(status: str):
    if '不足' in status or '超出' in status:
        return BAD
    if '低于' in status or '无法换算' in status:
        return WARN
    if '可覆盖' in status:
        return GOOD
    return None


class NumberBox(QDoubleSpinBox):
    """Spin box without trailing zeros that ignores the mouse wheel unless focused."""

    def __init__(self, unit, low, high, decimals, value):
        super().__init__()
        self.setRange(low, high)
        self.setDecimals(decimals)
        self.setValue(value)
        if unit:
            self.setSuffix(f' {unit}')
        self.setKeyboardTracking(False)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)

    def minimumSizeHint(self):
        # The default hint fits the maximum value (e.g. 1e12) and makes the settings panel too wide.
        hint = super().minimumSizeHint()
        return QSize(min(hint.width(), 90), hint.height())

    def textFromValue(self, value):
        text = super().textFromValue(value)
        point = self.locale().decimalPoint()
        return text.rstrip('0').rstrip(point) if point in text else text

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class Section(QWidget):
    """Collapsible block: a toggle header above content that is hidden when collapsed."""

    def __init__(self, title, content: QWidget, expanded=False):
        super().__init__()
        self.toggle = QToolButton(text=title, checkable=True, checked=expanded)
        self.toggle.setObjectName('section')
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.toggled.connect(self.set_expanded)
        self.content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(content)
        self.set_expanded(expanded)

    def set_expanded(self, expanded):
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.content.setVisible(expanded)

    def is_expanded(self):
        return self.toggle.isChecked()


def hint(text):
    label = QLabel(text)
    label.setObjectName('hint')
    label.setWordWrap(True)
    return label


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SPAD · 目标光功率计算')
        self.setStyleSheet(STYLE)
        font = QFont(self.font())
        font.setFamilies(FONT_FAMILIES)
        self.setFont(font)
        self.resize(1440, 900)
        self.results = []
        self.inputs = {}
        self.summary = None
        self.advice = None
        self.recommendation = None
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel('SPAD 目标光功率')
        title.setStyleSheet(f'font-size: 22px; font-weight: 700; color: {ACCENT};')
        titles.addWidget(title)
        subtitle = QLabel('测量激光 CW 功率，按占空比和衰减片换算，使每个脉冲平均入射设定数目的光子。')
        subtitle.setObjectName('subtitle')
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        self.build_actions(header)
        layout.addLayout(header)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)
        splitter.addWidget(self.build_settings_panel())
        splitter.addWidget(self.build_work_panel())
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 1060])
        self.reset()

    def build_actions(self, bar):
        self.calc_action = QAction('计算目标', self)
        self.calc_action.setShortcuts([QKeySequence('Ctrl+Return'), QKeySequence('Ctrl+Enter')])
        self.calc_action.triggered.connect(self.run)
        self.addAction(self.calc_action)
        for text, keys, callback in [('保存参数', QKeySequence.StandardKey.Save, self.save),
                                     ('加载参数', QKeySequence.StandardKey.Open, self.load),
                                     ('导出 CSV', QKeySequence('Ctrl+E'), self.export)]:
            action = QAction(text, self)
            action.setShortcut(keys)
            action.triggered.connect(callback)
            self.addAction(action)
            bar.addWidget(self.header_button(text, f'{text}（{action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)}）', callback))
        bar.addWidget(self.header_button('恢复默认', '将全部参数和波长表恢复为默认值', self.confirm_reset))

    def header_button(self, text, tip, callback):
        button = QPushButton(text)
        button.setObjectName('ghost')
        button.setToolTip(tip)
        button.clicked.connect(callback)
        return button

    def build_settings_panel(self):
        panel = QWidget()
        panel.setObjectName('settings')
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(0, 0, 4, 0)
        vbox.setSpacing(12)
        defaults = Settings()
        primary = QGroupBox('实验参数')
        primary.setObjectName('primary')
        primary_form = QFormLayout(primary)
        primary_form.setVerticalSpacing(12)
        primary_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        advanced = QWidget()
        advanced.setObjectName('advanced')
        advanced_form = QFormLayout(advanced)
        advanced_form.setContentsMargins(4, 0, 0, 4)
        advanced_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for key, label, unit, low, high, decimals, is_primary in FIELDS:
            spin = NumberBox(unit, low, high, decimals, getattr(defaults, key))
            spin.setToolTip(FIELD_TIPS[key])
            spin.valueChanged.connect(self.invalidate)
            self.inputs[key] = spin
            (primary_form if is_primary else advanced_form).addRow(label, spin)
        vbox.addWidget(primary)

        probe = QGroupBox('CW 校准读数')
        probe_box = QVBoxLayout(probe)
        self.uniform = QCheckBox('确认光斑均匀覆盖探头有效孔径，\n且探头与器件位置的辐照度相同')
        self.uniform.setObjectName('uniform')
        self.uniform.stateChanged.connect(self.invalidate)
        probe_box.addWidget(self.uniform)
        probe_box.addWidget(hint('勾选后才输出 CW 校准读数，并可把功率计读数换算为功率密度。不适用于小光斑、明显高斯光斑或不同平面光强。'))
        self.advanced = Section('探头与可变 OD 设置', advanced)
        probe_box.addWidget(self.advanced)
        vbox.addWidget(probe)

        self.model_help = Section('模型与适用条件', hint(
            '· 在 CW 模式下测功率；假设脉冲高值功率等于 CW 功率（矩形脉冲、相同驱动），脉冲平均功率 = CW × 占空比。\n'
            '· 矩形光脉冲，低值期间漏光可忽略；像元区域均匀照明。\n'
            '· 光子数是入射统计均值，不涉及 PDE、暗计数、死时间或计数率。\n'
            '· 校准：CW 模式下取出衰减片，用可变衰减调到“CW 不插衰减片探头读数”；再插回衰减片、切到脉冲模式即达到目标。\n'
            '· 实际脉冲高值功率可能与 CW 不同（瞬态、热效应），必要时应实测核对。\n'
            '· OD 应使用对应波长的实测值；衰减片指外置滤片，不是探头内置滤片。\n'
            '· 探头默认参考 S130VC：9.5 mm、0.5 nW；实际下限随量程、背景和校准条件变化。\n'
            '· 更改频率、脉宽或驱动条件后，应重新测量用于计算衰减量的光强。'))
        self.model_help.setContentsMargins(6, 0, 0, 0)
        vbox.addWidget(self.model_help)
        vbox.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(360)
        return scroll

    def build_work_panel(self):
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        group = QGroupBox('逐波长参数')
        vbox = QVBoxLayout(group)
        vbox.setSpacing(8)
        tools = QHBoxLayout()
        tools.addWidget(QLabel('统一衰减片 OD'))
        self.common_od = NumberBox('', 0, 30, 4, Channel.removed_od)
        self.common_od.setFixedWidth(84)
        self.common_od.setToolTip('滤光片在这些波长范围内不更换时，输入 OD 后按回车或点“应用到全部波长”。')
        self.common_od.lineEdit().returnPressed.connect(self.apply_common_od)
        tools.addWidget(self.common_od)
        apply = QPushButton('应用到全部波长')
        apply.setObjectName('soft')
        apply.setToolTip(self.common_od.toolTip())
        apply.clicked.connect(self.apply_common_od)
        tools.addWidget(apply)
        tools.addSpacing(16)
        tools.addWidget(QLabel('实测值单位'))
        self.unit_box = QComboBox()
        self.unit_box.addItem('nW（功率计读数）', 'nW')
        self.unit_box.addItem('nW/cm²（功率密度）', 'nW/cm2')
        self.unit_box.setToolTip('CW 无衰减实测值的单位。功率计读数按探头有效孔径面积换算为功率密度，需勾选均匀覆盖确认。')
        self.unit_box.currentIndexChanged.connect(self.update_measured_header)
        self.unit_box.currentIndexChanged.connect(self.invalidate)
        tools.addWidget(self.unit_box)
        tools.addStretch(1)
        for text, callback in [('＋ 添加波长', self.add_channel), ('删除选中行', self.remove_channels)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            tools.addWidget(button)
        vbox.addLayout(tools)
        vbox.addWidget(hint('统一 OD 一键填入所有波长，个别波长可在表中单独修改。填写 CW 无衰减实测值后，计算时会推荐各波长共用的整数固定 OD。'))
        self.channels = QTableWidget(0, len(CHANNEL_HEADERS))
        self.channels.setHorizontalHeaderLabels([text for text, _ in CHANNEL_HEADERS])
        for col, (_, tip) in enumerate(CHANNEL_HEADERS):
            self.channels.horizontalHeaderItem(col).setToolTip(tip)
        self.channels.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.channels.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.channels.verticalHeader().setDefaultSectionSize(32)
        self.channels.setShowGrid(False)
        self.channels.setAlternatingRowColors(True)
        self.channels.itemChanged.connect(self.invalidate)
        self.update_measured_header()
        vbox.addWidget(self.channels, 1)
        splitter.addWidget(group)

        results = QWidget()
        rbox = QVBoxLayout(results)
        rbox.setContentsMargins(0, 0, 0, 0)
        rbox.setSpacing(12)
        bar = QHBoxLayout()
        bar.setSpacing(12)
        self.calc_button = QPushButton('计算目标')
        self.calc_button.setObjectName('calc')
        self.calc_button.setToolTip(f'计算（{self.calc_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)}）')
        self.calc_button.clicked.connect(self.run)
        bar.addWidget(self.calc_button)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        bar.addWidget(self.summary, 1)
        rbox.addLayout(bar)
        self.advice = QFrame()
        self.advice.setObjectName('advice')
        abox = QHBoxLayout(self.advice)
        abox.setContentsMargins(16, 10, 14, 10)
        abox.setSpacing(16)
        od_box = QVBoxLayout()
        od_box.setSpacing(0)
        od_box.addWidget(hint('推荐固定 OD'))
        self.advice_od = QLabel()
        self.advice_od.setObjectName('adviceOd')
        od_box.addWidget(self.advice_od)
        abox.addLayout(od_box)
        self.advice_text = QLabel()
        self.advice_text.setWordWrap(True)
        abox.addWidget(self.advice_text, 1)
        self.adopt = QPushButton('采用推荐 OD')
        self.adopt.setObjectName('soft')
        self.adopt.setToolTip('将推荐值填入“统一衰减片 OD”，应用到全部波长并重新计算')
        self.adopt.clicked.connect(self.adopt_recommendation)
        abox.addWidget(self.adopt)
        self.advice.hide()
        rbox.addWidget(self.advice)
        card = QFrame()
        card.setObjectName('card')
        cbox = QVBoxLayout(card)
        cbox.setContentsMargins(14, 12, 14, 12)
        head = QHBoxLayout()
        title = QLabel('计算结果')
        title.setObjectName('cardTitle')
        head.addWidget(title)
        head.addStretch(1)
        self.show_minor = QCheckBox('显示次要列（器件平均功率、CW 插衰减片功率密度、透过率、CW 换算功率密度）')
        self.show_minor.toggled.connect(self.update_minor_columns)
        head.addWidget(self.show_minor)
        cbox.addLayout(head)
        self.output = QTableWidget(0, len(DISPLAY_ORDER))
        labels = dict(COLUMNS)
        for col, key in enumerate(DISPLAY_ORDER):
            item = QTableWidgetItem(labels[key])
            item.setToolTip(COLUMN_TIPS.get(key, ''))
            if key in KEY_COLUMNS:
                item.setForeground(QBrush(QColor(ACCENT)))
            self.output.setHorizontalHeaderItem(col, item)
        self.output.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.output.setAlternatingRowColors(True)
        self.output.verticalHeader().setVisible(False)
        self.output.verticalHeader().setDefaultSectionSize(38)
        self.output.setShowGrid(False)
        self.output.horizontalHeader().setStretchLastSection(True)
        self.update_minor_columns(False)
        cbox.addWidget(self.output, 1)
        rbox.addWidget(card, 1)
        splitter.addWidget(results)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([392, 428])
        return splitter

    def update_minor_columns(self, visible):
        for col, key in enumerate(DISPLAY_ORDER):
            if key in MINOR_COLUMNS:
                self.output.setColumnHidden(col, not visible)

    def set_summary(self, text, state):
        self.summary.setText(text)
        self.summary.setStyleSheet(f'background: {BANNER[state]}; border-radius: 10px; padding: 10px 14px; font-size: 14px;')

    def invalidate(self, *_):
        self.results = []
        self.recommendation = None
        if self.advice is not None:
            self.advice.hide()
        if self.summary is not None:
            keys = self.calc_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            self.set_summary(f'参数已修改，旧结果已清空。请点击“计算目标”（{keys}）重新计算。', 'stale')
            self.output.setRowCount(0)

    def add_channel(self, checked=False, values=None):
        interactive = values is None
        values = values or [520, f'{self.common_od.value():g}', '']
        row = self.channels.rowCount()
        self.channels.insertRow(row)
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.channels.setItem(row, col, item)
        self.invalidate()
        if interactive:
            self.channels.setCurrentCell(row, 0)
            self.channels.editItem(self.channels.item(row, 0))

    def update_measured_header(self, *_):
        text, tip = MEASURED_HEADERS[self.unit_box.currentData()]
        item = self.channels.horizontalHeaderItem(2)
        item.setText(text)
        item.setToolTip(tip)

    def show_advice(self, row_count, has_measured):
        rec = self.recommendation
        if rec is None:
            if has_measured:  # readings were entered but none could be converted
                self.advice_od.setText('—')
                self.advice_text.setText('已填写 CW 功率计读数，但未勾选“确认光斑均匀覆盖探头有效孔径”，无法换算为功率密度，暂不推荐固定 OD。')
                self.adopt.hide()
                self.advice.setStyleSheet('QFrame#advice { background: rgba(230, 160, 30, 0.10); border: 1px solid rgba(200, 130, 20, 0.55); border-radius: 12px; }')
                self.advice.show()
            return
        self.adopt.show()
        self.advice_od.setText(f'OD {rec["recommended_od"]:g}')
        lines = [] if rec['feasible'] else [f'<b style="color:{BAD.name()}">无法用单一整数固定 OD 让所有波长落在可变 OD 范围内，以下为最接近的整数折中值。</b>']
        lines += rec['messages']
        lines.append('采用后各波长所需可变 OD：' + ' · '.join(f'{wl:g} nm <b>{v:.3g}</b>' for wl, v in rec['variable']))
        if len(rec['totals']) < row_count:
            lines.append(f'未填写 CW 实测值的 {row_count - len(rec["totals"])} 个波长未参与推荐。')
        self.advice_text.setText('<br>'.join(lines))
        self.adopt.setText('采用推荐 OD' if rec['feasible'] else '采用折中 OD')
        tint = '30, 132, 73' if rec['feasible'] else '192, 57, 43'
        self.advice.setStyleSheet(f'QFrame#advice {{ background: rgba({tint}, 0.06); border: 1px solid rgba({tint}, 0.45); border-radius: 12px; }}')
        self.advice.show()

    def adopt_recommendation(self):
        if self.recommendation is None:
            return
        self.common_od.setValue(self.recommendation['recommended_od'])
        self.apply_common_od()
        self.run()

    def apply_common_od(self):
        self.common_od.interpretText()
        text = f'{self.common_od.value():g}'
        for row in range(self.channels.rowCount()):
            if self.channels.item(row, 1) is None:
                self.channels.setItem(row, 1, QTableWidgetItem())
            self.channels.item(row, 1).setText(text)
        self.invalidate()

    def remove_channels(self):
        for row in sorted({i.row() for i in self.channels.selectedIndexes()}, reverse=True):
            self.channels.removeRow(row)
        self.invalidate()

    def confirm_reset(self):
        answer = QMessageBox.question(self, '恢复默认', '将全部参数和波长表恢复为默认值，当前输入会丢失。是否继续？')
        if answer == QMessageBox.StandardButton.Yes:
            self.reset()

    def reset(self):
        for key, widget in self.inputs.items():
            widget.setValue(getattr(Settings(), key))
        self.uniform.setChecked(False)
        self.common_od.setValue(Channel.removed_od)
        self.unit_box.setCurrentIndex(self.unit_box.findData(Settings.measured_unit))
        self.channels.setRowCount(0)
        for wavelength in [375, 445, 520, 633, 730, 808]:
            self.add_channel(values=[wavelength, Channel.removed_od, ''])
        self.run()

    def read_settings(self):
        return Settings(**{key: w.value() for key, w in self.inputs.items()}, uniform_probe=self.uniform.isChecked(),
                        measured_unit=self.unit_box.currentData())

    def read_channels(self):
        rows = []
        for i in range(self.channels.rowCount()):
            try:
                wavelength, od, measured = [self.channels.item(i, j).text().strip() for j in range(3)]
                rows.append(Channel(float(wavelength), float(od), float(measured) if measured else None))
            except (ValueError, AttributeError):
                raise ValueError(f'第 {i + 1} 行格式错误：波长和衰减片 OD 必填数字，实测值可留空') from None
        if not rows:
            raise ValueError('至少需要一个波长')
        return rows

    def commit_edits(self):
        # Moving focus finishes any spin box or table cell still being edited (e.g. when using a shortcut).
        if self.isVisible():
            self.calc_button.setFocus()

    def run(self):
        self.commit_edits()
        self.invalidate()
        try:
            settings = self.read_settings()
            rows = self.read_channels()
            results = [calculate(settings, channel) for channel in rows]
            recommendation = recommend_fixed_od(settings, rows)
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            self.set_summary(f'无法计算：{exc}', 'error')
            QMessageBox.warning(self, '请检查参数', str(exc))
            return False
        self.results = results
        self.recommendation = recommendation
        self.show_advice(len(rows), any(row.measured is not None for row in rows))
        self.set_summary(f'像元面积 <b>{settings.area_cm2:.7g}</b> cm²　·　占空比 <b>{settings.duty * 100:.6g}%</b>　·　'
                         f'{len(results)} 个波长', 'ok')
        self.output.setRowCount(len(results))
        key_font = QFont(self.output.font())
        key_font.setBold(True)
        key_font.setPixelSize(16)
        key_background = QBrush(QColor(15, 122, 148, 24))
        for i, result in enumerate(results):
            color = status_color(result['status'])
            for j, key in enumerate(DISPLAY_ORDER):
                value = result[key]
                text = '—' if value is None else f'{value:.7g}' if isinstance(value, (int, float)) else value
                item = QTableWidgetItem(text)
                if key == 'status':
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    if color is not None:
                        item.setForeground(QBrush(color))
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if key in KEY_COLUMNS:
                    item.setFont(key_font)
                    item.setBackground(key_background)
                if key == 'probe_nw' and '低于' in result['status']:
                    item.setForeground(QBrush(WARN))
                if key in ('total_od', 'variable_od') and value is not None and color is not None:
                    item.setForeground(QBrush(color))
                self.output.setItem(i, j, item)
        self.output.resizeColumnsToContents()
        return True

    def save(self):
        if not self.run():
            return
        path, _ = QFileDialog.getSaveFileName(self, '保存实验参数', 'spad-settings.json', 'JSON (*.json)')
        if path:
            try:
                Path(path).write_text(json.dumps({'version': 4, 'settings': asdict(self.read_settings()), 'channels': [asdict(c) for c in self.read_channels()]}, ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError as exc:
                QMessageBox.warning(self, '保存失败', str(exc))

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, '加载实验参数', '', 'JSON (*.json)')
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            if data['version'] not in (1, 2, 3, 4):
                raise ValueError('不支持的参数文件版本')
            if data['version'] < 3:
                # v1/v2 stored measured values as density (and v1 a separate fixed total OD, no longer used).
                data['settings']['measured_unit'] = 'nW/cm2'
                data['channels'] = [{('measured' if k == 'measured_nw_cm2' else k): v for k, v in row.items() if k != 'fixed_od'}
                                    for row in data['channels']]
            settings = Settings(**data['settings'])
            rows = [Channel(**row) for row in data['channels']]
            if data['version'] < 4:  # v1–v3 stored the unattenuated pulsed average; CW = average / duty cycle
                rows = [Channel(r.wavelength_nm, r.removed_od, r.measured / settings.duty if r.measured is not None else None) for r in rows]
            if not rows or type(settings.uniform_probe) is not bool:
                raise ValueError('参数文件内容不完整')
            for row in rows:
                calculate(settings, row)
            for key, _, _, low, high, _, _ in FIELDS:
                if not low <= getattr(settings, key) <= high:
                    raise ValueError(f'{key} 超出界面支持范围')
            for key, widget in self.inputs.items():
                widget.setValue(getattr(settings, key))
            self.uniform.setChecked(settings.uniform_probe)
            self.unit_box.setCurrentIndex(self.unit_box.findData(settings.measured_unit))
            if len({row.removed_od for row in rows}) == 1:
                self.common_od.setValue(rows[0].removed_od)
            self.channels.setRowCount(0)
            for row in rows:
                self.add_channel(values=[row.wavelength_nm, row.removed_od, row.measured if row.measured is not None else ''])
            self.run()
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, ZeroDivisionError) as exc:
            QMessageBox.warning(self, '加载失败', str(exc))

    def export(self):
        if not self.run():
            return
        path, _ = QFileDialog.getSaveFileName(self, '导出计算结果', 'spad-results.csv', 'CSV (*.csv)')
        if path:
            try:
                with open(path, 'w', encoding='utf-8-sig', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(['参数', '值'])
                    writer.writerows(asdict(self.read_settings()).items())
                    writer.writerow([])
                    writer.writerow(['输入波长_nm', '衰减片_OD', f'CW无衰减实测值_{self.unit_box.currentData()}'])
                    writer.writerows(asdict(c).values() for c in self.read_channels())
                    writer.writerow([])
                    writer.writerow([label.replace('\n', ' ') for _, label in COLUMNS])
                    writer.writerows([r[key] for key, _ in COLUMNS] for r in self.results)
                    if self.recommendation is not None:
                        rec = self.recommendation
                        writer.writerow([])
                        writer.writerow(['推荐固定_OD', rec['recommended_od'], '可行' if rec['feasible'] else '不可行（折中值）'])
                        writer.writerows([[message] for message in rec['messages']])
            except OSError as exc:
                QMessageBox.warning(self, '导出失败', str(exc))


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    apply_light_theme(app)
    window = Window()
    window.show()
    sys.exit(app.exec())
