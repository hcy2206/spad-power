"""Write the CHANGELOG.md section of a tag (e.g. v0.1.0) to a file, for the GitHub release body."""
import sys
from pathlib import Path

tag, output = sys.argv[1], Path(sys.argv[2])
version = tag.removeprefix('v')
lines = (Path(__file__).resolve().parents[1] / 'CHANGELOG.md').read_text(encoding='utf-8').splitlines()
start = next((i for i, line in enumerate(lines) if line.startswith(f'## [{version}]')), None)
if start is None:
    raise SystemExit(f'CHANGELOG.md has no section for {version}')
end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
body = '\n'.join(lines[start + 1:end]).strip()
download = ('\n\n---\n\n**下载：** 下方 Assets 中的 `SPAD-Power-' + tag + '-windows-x64.exe`，双击即可运行，无需安装 Python。'
            '程序未签名，首次运行若出现“Windows 已保护你的电脑”，点“更多信息”→“仍要运行”。')
output.write_text(body + download + '\n', encoding='utf-8')
