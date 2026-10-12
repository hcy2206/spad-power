"""Build on Windows; produces a standalone executable without requiring Python."""
import os
import subprocess
import sys
from pathlib import Path

if sys.platform != 'win32':
    raise SystemExit('Windows exe 必须在 Windows 上构建；Mac 调试请运行 uv run spad-power。')
# Consoles on non-Chinese Windows (e.g. cp1252 on CI) cannot encode the Chinese messages below.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
root = Path(__file__).resolve().parents[1]
assets = root / 'spad_power' / 'assets'
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed', '--name', 'SPAD-Power',
                '--icon', str(assets / 'icon.ico'), '--add-data', f'{assets}{os.pathsep}spad_power/assets',
                '--paths', str(root), str(root / 'spad_power' / '__main__.py')], cwd=root, check=True)
print('完成：dist/SPAD-Power.exe')
