"""PDE vs wavelength line chart drawn with QPainter (no extra Qt modules needed)."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

SERIES = QColor('#0b84a5')  # validated: lightness band, chroma floor and 3:1 contrast on white
GRID, AXIS, TEXT, MUTED = QColor('#eef1f5'), QColor('#d3dae4'), QColor('#1f2a37'), QColor('#6b7686')
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 52, 24, 34, 44


def nice_step(span, target_ticks=5):
    raw = span / max(target_ticks, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    return next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)


def ticks(low, high, step):
    first = math.ceil(low / step - 1e-9) * step
    count = int(math.floor((high - first) / step + 1e-9)) + 1
    return [round(first + i * step, 10) for i in range(max(count, 0))]


class PdeChart(QWidget):
    def __init__(self):
        super().__init__()
        self.points = []  # (wavelength_nm, pde_percent, photons) sorted by wavelength
        self.hover = None
        self.setMouseTracking(True)
        self.setMinimumSize(320, 220)

    def set_data(self, points):
        self.points = sorted((wl, pde, photons) for wl, pde, photons in points if pde is not None)
        self.hover = None
        self.update()

    def ranges(self):
        wavelengths = [p[0] for p in self.points]
        low, high = min(wavelengths), max(wavelengths)
        pad = max((high - low) * 0.06, 10) if high > low else 50
        x_step = nice_step(high - low + 2 * pad)
        y_top = max(max(p[1] for p in self.points) * 1.15, 1)
        y_step = nice_step(y_top)
        return (low - pad, high + pad, x_step), (0, math.ceil(y_top / y_step) * y_step, y_step)

    def plot_rect(self):
        return QRectF(MARGIN_LEFT, MARGIN_TOP, self.width() - MARGIN_LEFT - MARGIN_RIGHT,
                      self.height() - MARGIN_TOP - MARGIN_BOTTOM)

    def mapper(self):
        (x0, x1, _), (y0, y1, _) = self.ranges()
        rect = self.plot_rect()
        return lambda wl, pde: QPointF(rect.left() + (wl - x0) / (x1 - x0) * rect.width(),
                                       rect.bottom() - (pde - y0) / (y1 - y0) * rect.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(self.font())
        font.setPixelSize(12)
        p.setFont(font)
        if not self.points:
            p.setPen(MUTED)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       '填写 CW 实测值和光计数率并计算后，这里显示 PDE 随波长的变化。')
            return
        (x0, x1, x_step), (y0, y1, y_step) = self.ranges()
        rect, to_point = self.plot_rect(), self.mapper()
        # Recessive hairline grid and axis labels in text tokens, never the series color.
        for y in ticks(y0, y1, y_step):
            py = to_point(x0, y).y()
            p.setPen(QPen(AXIS if y == y0 else GRID, 1))
            p.drawLine(QPointF(rect.left(), py), QPointF(rect.right(), py))
            p.setPen(MUTED)
            p.drawText(QRectF(0, py - 9, MARGIN_LEFT - 8, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f'{y:g}')
        for x in ticks(x0, x1, x_step):
            px = to_point(x, y0).x()
            p.setPen(MUTED)
            p.drawText(QRectF(px - 30, rect.bottom() + 6, 60, 16), Qt.AlignmentFlag.AlignCenter, f'{x:g}')
        p.drawText(QRectF(rect.left(), rect.bottom() + 24, rect.width(), 16), Qt.AlignmentFlag.AlignCenter, '波长 (nm)')
        p.drawText(QRectF(4, 6, 120, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, 'PDE (%)')
        points = [to_point(wl, pde) for wl, pde, _ in self.points]
        if self.hover is not None:  # crosshair snapped to the nearest wavelength
            p.setPen(QPen(AXIS, 1))
            p.drawLine(QPointF(points[self.hover].x(), rect.top()), QPointF(points[self.hover].x(), rect.bottom()))
        if len(points) > 1:
            line = QPainterPath(points[0])
            for point in points[1:]:
                line.lineTo(point)
            area = QPainterPath(line)
            area.lineTo(points[-1].x(), rect.bottom())
            area.lineTo(points[0].x(), rect.bottom())
            area.closeSubpath()
            wash = QColor(SERIES)
            wash.setAlphaF(0.10)
            p.fillPath(area, wash)
            p.setPen(QPen(SERIES, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(line)
        for i, point in enumerate(points):
            radius = 6 if i == self.hover else 4.5
            p.setPen(QPen(QColor('white'), 2))
            p.setBrush(SERIES)
            p.drawEllipse(point, radius, radius)
        peak = max(range(len(points)), key=lambda i: self.points[i][1])  # one direct label: the peak
        bold = QFont(font)
        bold.setBold(True)
        p.setFont(bold)
        p.setPen(TEXT)
        p.drawText(QRectF(points[peak].x() - 50, points[peak].y() - 26, 100, 16), Qt.AlignmentFlag.AlignCenter,
                   f'峰值 {self.points[peak][1]:.3g}%')

    def mouseMoveEvent(self, event):
        if not self.points:
            return
        to_point = self.mapper()
        x = event.position().x()
        nearest = min(range(len(self.points)), key=lambda i: abs(to_point(*self.points[i][:2]).x() - x))
        if nearest != self.hover:
            self.hover = nearest
            self.update()
        wl, pde, photons = self.points[nearest]
        photons_text = f'{photons:.3g}' if photons is not None else '—'
        QToolTip.showText(event.globalPosition().toPoint(),
                          f'<b>PDE {pde:.4g}%</b><br>{wl:g} nm · 每脉冲 {photons_text} 个光子', self)

    def leaveEvent(self, event):
        self.hover = None
        QToolTip.hideText()
        self.update()
