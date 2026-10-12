"""Build on Windows; produces a standalone executable without requiring Python."""
import subprocess
import sys
from pathlib import Path

if sys.platform != 'win32':
    raise SystemExit('Windows exe 必须在 Windows 上构建；Mac 调试请运行 uv run spad-power。')
root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed', '--name', 'SPAD-Power', '--paths', str(root), str(root / 'spad_power' / '__main__.py')], cwd=root, check=True)
print('完成：dist/SPAD-Power.exe')
