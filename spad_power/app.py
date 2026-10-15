from __future__ import annotations
import csv
import json
import sys
from dataclasses import asdict, fields, replace
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGroupBox, QDoubleSpinBox, QCheckBox, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog, QAbstractItemView, QSplitter,
    QScrollArea, QToolButton, QFrame, QAbstractSpinBox, QSizePolicy, QComboBox)
from spad_power import __version__
from spad_power.chart import PdeChart
from spad_power.model import Settings, Channel, calculate, evaluate_criteria, PDE_MIN_PERCENT, PDE_PEAK_MIN_PERCENT

ICON = Path(__file__).resolve().parent / 'assets' / 'icon.png'
SETTINGS_FIELDS = {f.name for f in fields(Settings)}

# key, label, unit, min, max, decimals, primary (shown large; others folded under "探头设置")
FIELDS = [
    ('frequency_khz', '重复频率', 'kHz', 0.000001, 1e6, 6, True),
    ('pulse_ns', '光脉冲高值宽度', 'ns', 0.000001, 1e12, 6, True),
    ('major_um', '椭圆完整长轴', 'μm', 0.001, 1e6, 3, True),
    ('minor_um', '椭圆完整短轴', 'μm', 0.001, 1e6, 3, True),
    ('probe_diameter_mm', '探头有效孔径直径', 'mm', 0.001, 1000, 3, False),
]
FIELD_TIPS = {
    'frequency_khz': '激光重复频率；决定占空比，也用于把计数率换算为每脉冲探测概率。',
    'pulse_ns': '实际光脉冲宽度（电调制宽度未必相同），决定占空比 D = fτ。',
    'major_um': '椭圆像元的完整长轴（不是半轴）。',
    'minor_um': '椭圆像元的完整短轴（不是半轴）。',
    'probe_diameter_mm': '功率计探头有效孔径直径，用于把功率计读数换算为功率密度；默认 S130VC 参考值 9.5 mm。',
}
# CSV export keeps this order; the on-screen table uses DISPLAY_ORDER.
COLUMNS = [
    ('wavelength_nm', '波长\n(nm)'), ('photons', '每脉冲入射光子数\n(个/脉冲)'), ('pde_percent', 'PDE\n(%)'),
    ('detection_prob', '每门光致计数概率'), ('device_avg_pw', '器件脉冲平均功率\n(pW)'),
    ('density_avg_pw_cm2', '器件脉冲平均功率密度\n(pW/cm²)'), ('measured_nw_cm2', 'CW 无衰减功率密度\n(nW/cm²)'),
    ('status', '提示'),
]
DISPLAY_ORDER = [key for key, _ in COLUMNS if key != 'status']  # status shows as a row tooltip; CSV keeps it
KEY_COLUMNS = {'photons', 'pde_percent'}
MINOR_COLUMNS = {'detection_prob', 'device_avg_pw', 'density_avg_pw_cm2', 'measured_nw_cm2'}
COLUMN_TIPS = {
    'photons': '插入该行衰减片、脉冲模式下每个脉冲平均入射到像元的光子数 = CW 无衰减功率 × 占空比 × 10^(−OD) / (f·hc/λ)。需填写 CW 实测值。',
    'pde_percent': '光子探测效率 = ln[(1 − Cd/f) / (1 − Ct/f)] / μ（门控模式，每门至多一次计数），μ 为每脉冲入射光子数；'
                   f'低于指标 {PDE_MIN_PERCENT}% 时标红。需填写门内总计数率 Ct。',
    'detection_prob': '每门由光子引起的计数概率 p = (Ct/f − Cd/f) / (1 − Cd/f)，PDE = −ln(1 − p) / μ。',
    'device_avg_pw': '插入衰减片、脉冲模式下像元面积内的周期平均功率。',
    'density_avg_pw_cm2': '插入衰减片、脉冲模式下器件处的周期平均功率密度。',
    'measured_nw_cm2': 'CW 无衰减实测值换算成的功率密度；功率计读数按探头有效孔径面积换算。',
}
MEASURED_HEADERS = {
    'nW': ('CW 无衰减读数 (nW)', '激光切到 CW 模式（与脉冲模式相同驱动条件），不加衰减片，在器件位置测得的功率计读数。'
           '按探头有效孔径面积换算为功率密度，需勾选均匀覆盖确认；用于计算每脉冲入射光子数。'),
    'nW/cm2': ('CW 无衰减密度 (nW/cm²)', '激光切到 CW 模式（与脉冲模式相同驱动条件），不加衰减片，器件位置的功率密度；'
               '用于计算每脉冲入射光子数。'),
}
CHANNEL_HEADERS = [
    ('波长 (nm)', '各波长独立计算。'),
    ('衰减片 OD', '测计数时插在器件前的外置衰减片 OD（填该波长处的实测 OD）。'),
    ('CW 无衰减实测值', ''),  # text depends on the measured unit, see update_measured_header
    ('门内总计数 Ct (cps)', '可留空。插入衰减片、脉冲模式下，SPAD 门控时间内的计数之和（次/秒，含暗计数）；填写后计算 PDE。'
                           '计数器采集时间不是 1 秒时，先除以采集时间。'),
    ('门内暗计数 Cd (cps)', '可留空（按 0 计算）。关闭光源、相同门控与偏置条件下，门控时间内的计数之和（次/秒）。'
                           '不是自由运行时整个周期的暗计数率。'),
]
ACCENT, ACCENT_HOVER, ACCENT_PRESSED = '#0f7a94', '#0d6b82', '#0a5a6d'
BG, CARD, BORDER, FIELD_BORDER = '#f3f5f9', '#ffffff', '#e2e7ef', '#d3dae4'
TEXT, MUTED = '#1f2a37', '#6b7686'
FONT_FAMILIES = ['PingFang SC', 'Microsoft YaHei UI', 'Segoe UI', 'Helvetica Neue', 'Noto Sans CJK SC']
WARN, BAD, GOOD = QColor('#b9770e'), QColor('#c0392b'), QColor('#1e8449')
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
    if '无法' in status or '缺少' in status or '超过 100%' in status:
        return WARN
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
        self.setWindowTitle(f'SPAD · 光子数与 PDE 计算  v{__version__}')
        self.setStyleSheet(STYLE)
        font = QFont(self.font())
        font.setFamilies(FONT_FAMILIES)
        self.setFont(font)
        self.resize(1440, 900)
        self.results = []
        self.inputs = {}
        self.summary = None
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel('SPAD 光子数与 PDE')
        title.setStyleSheet(f'font-size: 22px; font-weight: 700; color: {ACCENT};')
        titles.addWidget(title)
        subtitle = QLabel('测量激光 CW 功率，按占空比和衰减片 OD 算出每脉冲入射光子数，再由门内总计数和暗计数计算 PDE 并判定指标。')
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
        self.calc_action = QAction('计算', self)
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

        probe = QGroupBox('功率计换算')
        probe_box = QVBoxLayout(probe)
        unit_row = QHBoxLayout()
        unit_row.addWidget(QLabel('实测值单位'))
        self.unit_box = QComboBox()
        self.unit_box.addItem('nW（功率计读数）', 'nW')
        self.unit_box.addItem('nW/cm²（功率密度）', 'nW/cm2')
        self.unit_box.setToolTip('CW 无衰减实测值的单位。功率计读数按探头有效孔径面积换算为功率密度，需勾选均匀覆盖确认。')
        self.unit_box.currentIndexChanged.connect(self.invalidate)
        unit_row.addWidget(self.unit_box, 1)
        probe_box.addLayout(unit_row)
        self.uniform = QCheckBox('确认光斑均匀覆盖探头有效孔径，\n且探头与器件位置的辐照度相同')
        self.uniform.setObjectName('uniform')
        self.uniform.stateChanged.connect(self.invalidate)
        probe_box.addWidget(self.uniform)
        probe_box.addWidget(hint('实测值为功率计读数时，勾选后才能换算为功率密度。不适用于小光斑、明显高斯光斑或不同平面光强。'))
        self.advanced = Section('探头设置', advanced)
        probe_box.addWidget(self.advanced)
        vbox.addWidget(probe)

        self.model_help = Section('模型与适用条件', hint(
            '· 在 CW 模式下、不加衰减片测功率；假设脉冲高值功率等于 CW 功率（矩形脉冲、相同驱动），脉冲平均功率 = CW × 占空比。\n'
            '· 每脉冲入射光子数 = CW 功率 × 占空比 × 10^(−OD) / (重复频率 × 单光子能量)，按像元面积计。\n'
            '· 门控模式（SPAD 门与激光同步于 f，每门至多一次计数）：PDE = ln[(1 − Cd/f) / (1 − Ct/f)] / 光子数；'
            'Ct、Cd 为门控时间内的计数率；未修正后脉冲和串扰。\n'
            f'· 指标：各波长 PDE > {PDE_MIN_PERCENT}%，峰值 PDE ≥ {PDE_PEAK_MIN_PERCENT}%。\n'
            '· 矩形光脉冲，低值期间漏光可忽略；像元区域均匀照明。\n'
            '· 实际脉冲高值功率可能与 CW 不同（瞬态、热效应），必要时应实测核对。\n'
            '· OD 应使用对应波长的实测值；衰减片指外置滤片，不是探头内置滤片。\n'
            '· 更改频率、脉宽或驱动条件后，应重新测量 CW 功率。'))
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
        self.common_od = NumberBox('', 0, 30, 4, Channel.od)
        self.common_dark = NumberBox('cps', 0, 1e12, 1, 0)
        for label, box, callback, tip in [
                ('统一衰减片 OD', self.common_od, self.apply_common_od, '各波长使用同一片衰减片时，输入 OD 后按回车或点“应用到全部波长”。'),
                ('统一门内暗计数 Cd', self.common_dark, self.apply_common_dark, '门内暗计数与波长无关时，输入后按回车或点“应用到全部波长”。')]:
            tools.addWidget(QLabel(label))
            box.setFixedWidth(84 if box is self.common_od else 110)
            box.setToolTip(tip)
            box.lineEdit().returnPressed.connect(callback)
            tools.addWidget(box)
            apply = QPushButton('应用到全部波长')
            apply.setObjectName('soft')
            apply.setToolTip(tip)
            apply.clicked.connect(callback)
            tools.addWidget(apply)
            tools.addSpacing(16)
        tools.addStretch(1)
        for text, callback in [('＋ 添加波长', self.add_channel), ('删除选中行', self.remove_channels)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            tools.addWidget(button)
        vbox.addLayout(tools)
        vbox.addWidget(hint('统一值一键填入所有波长，个别波长可在表中单独修改。后三列可留空：填写 CW 无衰减实测值后计算每脉冲光子数，再填写门内总计数 Ct（和暗计数 Cd）即可计算 PDE。'))
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
        self.unit_box.currentIndexChanged.connect(self.update_measured_header)
        self.update_measured_header()
        vbox.addWidget(self.channels, 1)
        splitter.addWidget(group)

        results = QWidget()
        rbox = QVBoxLayout(results)
        rbox.setContentsMargins(0, 0, 0, 0)
        rbox.setSpacing(12)
        bar = QHBoxLayout()
        bar.setSpacing(12)
        self.calc_button = QPushButton('计算')
        self.calc_button.setObjectName('calc')
        self.calc_button.setToolTip(f'计算（{self.calc_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)}）')
        self.calc_button.clicked.connect(self.run)
        bar.addWidget(self.calc_button)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        bar.addWidget(self.summary, 1)
        rbox.addLayout(bar)
        card = QFrame()
        card.setObjectName('card')
        cbox = QVBoxLayout(card)
        cbox.setContentsMargins(14, 12, 14, 12)
        head = QHBoxLayout()
        title = QLabel('计算结果')
        title.setObjectName('cardTitle')
        head.addWidget(title)
        head.addStretch(1)
        self.show_minor = QCheckBox('显示次要列（光致计数概率、器件脉冲平均功率与功率密度、CW 换算功率密度）')
        self.show_minor.toggled.connect(self.update_minor_columns)
        head.addWidget(self.show_minor)
        cbox.addLayout(head)
        self.verdict = QLabel()
        self.verdict.setWordWrap(True)
        self.verdict.hide()
        cbox.addWidget(self.verdict)
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
        self.update_minor_columns(False)
        self.chart = PdeChart()
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setHandleWidth(12)
        body.setChildrenCollapsible(False)
        body.addWidget(self.output)
        body.addWidget(self.chart)
        body.setStretchFactor(1, 1)
        body.setSizes([400, 600])
        cbox.addWidget(body, 1)
        rbox.addWidget(card, 1)
        splitter.addWidget(results)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([374, 446])
        return splitter

    def show_verdict(self, verdict):
        if verdict is None:
            self.verdict.hide()
            return
        def mark(ok):  # icon + label, never colour alone
            return f'<span style="color:{(GOOD if ok else BAD).name()}"><b>{"✓ 通过" if ok else "✗ 未通过"}</b></span>'
        below = '、'.join(f'{wl:g} nm' for wl in verdict['below'])
        first = f'指标 1（各波长 PDE &gt; {PDE_MIN_PERCENT}%）：{mark(verdict["all_above"])}' + (f'（低于指标：{below}）' if below else '')
        wl, pde = verdict['peak']
        second = f'指标 2（峰值 PDE ≥ {PDE_PEAK_MIN_PERCENT}%）：{mark(verdict["peak_ok"])}（峰值 {pde:.4g}% @ {wl:g} nm）'
        missing = f'　·　{verdict["missing"]} 个波长无 PDE，未参与判定' if verdict['missing'] else ''
        self.verdict.setText(f'{first}　　{second}{missing}')
        self.verdict.show()

    def update_minor_columns(self, visible):
        for col, key in enumerate(DISPLAY_ORDER):
            if key in MINOR_COLUMNS:
                self.output.setColumnHidden(col, not visible)

    def set_summary(self, text, state):
        self.summary.setText(text)
        self.summary.setStyleSheet(f'background: {BANNER[state]}; border-radius: 10px; padding: 10px 14px; font-size: 14px;')

    def invalidate(self, *_):
        self.results = []
        if self.summary is not None:
            keys = self.calc_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            self.set_summary(f'参数已修改，旧结果已清空。请点击“计算”（{keys}）重新计算。', 'stale')
            self.output.setRowCount(0)
            self.chart.set_data([])
            self.verdict.hide()

    def add_channel(self, checked=False, values=None):
        interactive = values is None
        values = list(values or [520, f'{self.common_od.value():g}'])
        values += [''] * (len(CHANNEL_HEADERS) - len(values))  # optional columns start empty
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

    def fill_column(self, col, box):
        box.interpretText()
        text = f'{box.value():g}'
        for row in range(self.channels.rowCount()):
            if self.channels.item(row, col) is None:
                self.channels.setItem(row, col, QTableWidgetItem())
            self.channels.item(row, col).setText(text)
        self.invalidate()

    def apply_common_od(self):
        self.fill_column(1, self.common_od)

    def apply_common_dark(self):
        self.fill_column(4, self.common_dark)

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
        self.common_od.setValue(Channel.od)
        self.common_dark.setValue(0)
        self.unit_box.setCurrentIndex(self.unit_box.findData(Settings.measured_unit))
        self.channels.setRowCount(0)
        for wavelength in [375, 445, 520, 633, 730, 808]:
            self.add_channel(values=[wavelength, Channel.od])
        self.run()

    def read_settings(self):
        return Settings(**{key: w.value() for key, w in self.inputs.items()}, uniform_probe=self.uniform.isChecked(),
                        measured_unit=self.unit_box.currentData())

    def read_channels(self):
        rows = []
        for i in range(self.channels.rowCount()):
            try:
                wavelength, od, *optional = [self.channels.item(i, j).text().strip() for j in range(len(CHANNEL_HEADERS))]
                rows.append(Channel(float(wavelength), float(od), *[float(x) if x else None for x in optional]))
            except (ValueError, AttributeError):
                raise ValueError(f'第 {i + 1} 行格式错误：波长和衰减片 OD 必填数字，实测值和计数率可留空') from None
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
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            self.set_summary(f'无法计算：{exc}', 'error')
            QMessageBox.warning(self, '请检查参数', str(exc))
            return False
        self.results = results
        notes = sum(bool(r['status']) for r in results)
        self.set_summary(f'像元面积 <b>{settings.area_cm2:.7g}</b> cm²　·　占空比 <b>{settings.duty * 100:.6g}%</b>　·　'
                         f'{len(results)} 个波长' + (f'　·　{notes} 个波长有提示（鼠标悬停该行查看）' if notes else ''), 'ok')
        self.chart.set_data([(r['wavelength_nm'], r['pde_percent'], r['photons']) for r in results])
        self.show_verdict(evaluate_criteria(results))
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
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if result['status']:  # notes replace the former status column
                    item.setToolTip(result['status'])
                if key == 'pde_percent' and value is not None and not value > PDE_MIN_PERCENT:
                    item.setForeground(QBrush(BAD))
                    item.setToolTip('；'.join(filter(None, [f'低于指标 {PDE_MIN_PERCENT}%', result['status']])))
                if value is None and color is not None:
                    item.setForeground(QBrush(color))
                if key in KEY_COLUMNS:
                    item.setFont(key_font)
                    item.setBackground(key_background)
                self.output.setItem(i, j, item)
        for col, key in enumerate(DISPLAY_ORDER):
            self.output.resizeColumnToContents(col)
            if key in KEY_COLUMNS:  # give the main results room to breathe
                self.output.setColumnWidth(col, max(self.output.columnWidth(col) + 24, 150))
        return True

    def save(self):
        if not self.run():
            return
        path, _ = QFileDialog.getSaveFileName(self, '保存实验参数', 'spad-settings.json', 'JSON (*.json)')
        if path:
            try:
                Path(path).write_text(json.dumps({'version': 6, 'settings': asdict(self.read_settings()), 'channels': [asdict(c) for c in self.read_channels()]}, ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError as exc:
                QMessageBox.warning(self, '保存失败', str(exc))

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, '加载实验参数', '', 'JSON (*.json)')
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            if data['version'] not in (1, 2, 3, 4, 5, 6):
                raise ValueError('不支持的参数文件版本')
            if data['version'] < 3:  # v1/v2 stored measured values as density
                data['settings']['measured_unit'] = 'nW/cm2'
            # Older files also hold target / variable-attenuator settings and a fixed total OD (v1), no longer used.
            settings = Settings(**{k: v for k, v in data['settings'].items() if k in SETTINGS_FIELDS})
            renamed = {'measured_nw_cm2': 'measured', 'removed_od': 'od'}
            rows = [Channel(**{renamed.get(k, k): v for k, v in row.items() if k != 'fixed_od'}) for row in data['channels']]
            if data['version'] < 4:  # v1–v3 stored the unattenuated pulsed average; CW = average / duty cycle
                rows = [replace(r, measured=r.measured / settings.duty if r.measured is not None else None) for r in rows]
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
            if len({row.od for row in rows}) == 1:
                self.common_od.setValue(rows[0].od)
            self.channels.setRowCount(0)
            for row in rows:
                self.add_channel(values=[row.wavelength_nm, row.od] + ['' if v is None else v for v in (row.measured, row.light_cps, row.dark_cps)])
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
                    writer.writerow(['输入波长_nm', '衰减片_OD', f'CW无衰减实测值_{self.unit_box.currentData()}', '门内总计数_Ct_cps', '门内暗计数_Cd_cps'])
                    writer.writerows(asdict(c).values() for c in self.read_channels())
                    writer.writerow([])
                    writer.writerow([label.replace('\n', ' ') for _, label in COLUMNS])
                    writer.writerows([r[key] for key, _ in COLUMNS] for r in self.results)
                    verdict = evaluate_criteria(self.results)
                    if verdict is not None:
                        writer.writerow([])
                        writer.writerow([f'指标1_各波长PDE>{PDE_MIN_PERCENT}%', '通过' if verdict['all_above'] else '未通过',
                                         '低于指标: ' + ' '.join(f'{wl:g}nm' for wl in verdict['below'])])
                        writer.writerow([f'指标2_峰值PDE>={PDE_PEAK_MIN_PERCENT}%', '通过' if verdict['peak_ok'] else '未通过',
                                         f'峰值 {verdict["peak"][1]}% @ {verdict["peak"][0]:g}nm'])
            except OSError as exc:
                QMessageBox.warning(self, '导出失败', str(exc))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('SPAD-Power')
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(ICON)))
    app.setStyle('Fusion')
    apply_light_theme(app)
    window = Window()
    window.show()
    sys.exit(app.exec())
