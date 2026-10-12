"""Regenerate the application icon (PNG for Qt, multi-size ICO for the Windows exe)."""
import struct
import sys
from pathlib import Path
from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

OUT = Path(__file__).resolve().parents[1] / 'spad_power' / 'assets'
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def render(size):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 256, size / 256)
    background = QLinearGradient(0, 0, 256, 256)
    background.setColorAt(0, QColor('#13a3b8'))
    background.setColorAt(1, QColor('#0a5a6d'))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(background)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 52, 52)
    # Rectangular pulse train: the duty cycle that scales CW power down to the pulsed average.
    pulses = QPainterPath(QPointF(36, 180))
    for x in (64, 112, 152, 200):
        pulses.lineTo(x, pulses.currentPosition().y())
        pulses.lineTo(x, 104 if pulses.currentPosition().y() == 180 else 180)
    pulses.lineTo(220, 180)
    p.setPen(QPen(QColor('white'), 16, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(pulses)
    # A single photon above the second pulse.
    glow = QRadialGradient(QPointF(176, 62), 34)
    glow.setColorAt(0, QColor(255, 209, 102, 200))
    glow.setColorAt(1, QColor(255, 209, 102, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(glow)
    p.drawEllipse(QPointF(176, 62), 34, 34)
    p.setBrush(QColor('#ffd166'))
    p.drawEllipse(QPointF(176, 62), 15, 15)
    p.end()
    return image


def png_bytes(image):
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(buffer.data())


def write_ico(path, images):
    # ICO container with PNG-compressed entries (supported since Windows Vista).
    data = [png_bytes(image) for image in images]
    header = struct.pack('<HHH', 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = b''
    for image, blob in zip(images, data):
        side = image.width() if image.width() < 256 else 0
        entries += struct.pack('<BBBBHHII', side, side, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    path.write_bytes(header + entries + b''.join(data))


if __name__ == '__main__':
    app = QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    render(256).save(str(OUT / 'icon.png'))
    write_ico(OUT / 'icon.ico', [render(size) for size in ICO_SIZES])
    print(f'wrote {OUT / "icon.png"} and {OUT / "icon.ico"}')
