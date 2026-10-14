<p align="center">
  <img src="spad_power/assets/icon.png" width="96" alt="SPAD-Power icon">
</p>

<h1 align="center">SPAD-Power · SPAD 目标光功率计算器</h1>

<p align="center">
  <a href="https://github.com/hcy2206/spad-power/actions/workflows/ci.yml"><img src="https://github.com/hcy2206/spad-power/actions/workflows/ci.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/hcy2206/spad-power/releases/latest"><img src="https://img.shields.io/github/v/release/hcy2206/spad-power" alt="Release"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey" alt="Platform">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
</p>

<p align="center">
  <b>测量激光 CW 功率，按占空比和衰减片换算，确保每个脉冲平均只入射设定数目（如 0.1 个）的光子。</b>
</p>

> **English:** A small desktop calculator for single-photon (SPAD) experiments. Measure the laser power in CW mode; the app converts it with the pulse duty cycle and attenuator OD into the settings that deliver a target mean photon number per pulse (e.g. 0.1). It outputs the CW power-meter reading for calibration, the required total and variable OD, and a recommended integer fixed OD shared by all wavelengths, warning when the variable attenuator range is insufficient. The UI is in Simplified Chinese. Windows builds are on the [Releases](https://github.com/hcy2206/spad-power/releases) page.

![SPAD-Power 界面](docs/interface.png)

## 下载

- **Windows：** 在 [Releases](https://github.com/hcy2206/spad-power/releases/latest) 页面下载 `SPAD-Power-<版本>-windows-x64.exe`，双击运行，无需安装 Python。程序未签名，首次运行若出现“Windows 已保护你的电脑”，点“更多信息”→“仍要运行”。
- **macOS / 其他平台：** 从源码运行，见[从源码运行](#从源码运行)。

程序是离线计算工具，不连接或控制激光器、功率计和 SPAD，也不采集仪器数据。它计算的是**入射光子数对应的目标光强**，不从 SPAD 探测计数反推光功率。

## 为什么是 CW 方案

在单光子探测实验中，实验目标通常是“每个脉冲平均入射 0.1 个光子”。脉冲模式下的平均功率极低（pW 量级），功率计难以测准。本方案在 CW（连续）模式下测量激光功率，再利用脉冲占空比 D = fτ 和外置衰减片把光强降到目标。例如默认参数下，脉冲模式的校准读数约 0.49 nW，低于常见探头的测量下限；改在 CW 模式校准后约 203 nW，容易测准。

## 功能

- **设定目标光强：** 给定波长、重复频率、脉宽、目标光子数和像元面积，计算器件处需要的脉冲平均功率密度，以及对应的 CW 等效功率密度（= 平均 / 占空比）。
- **CW 校准读数：** 计算 CW 模式下取出衰减片时功率计应调到的读数。校准时在 CW 模式下取出衰减片，用可变衰减调到该读数，再插回衰减片、切换到脉冲模式，即达到每脉冲目标光子数。
- **确定衰减量：** 输入各波长 CW 模式、不加任何衰减片时的功率，计算所需总 OD（已计入占空比）、衰减片之外还需可变衰减承担的 OD，并判断是否落在可调范围内。
- **推荐整数固定 OD：** 推荐一个各波长共用的整数衰减片 OD，使每个波长所需的可变 OD 都落在可调范围内且两端留有余量；可变 OD 不够用时明确提示还差多少，并给出折中值，可一键采用。
- **多波长：** 同时计算多个波长，每个波长可设置独立的衰减片 OD 和实测值；“统一衰减片 OD”一键填入所有波长。
- **记录与导出：** 保存和加载 JSON 参数，导出包含输入、计算结果和推荐 OD 的 CSV。

## 界面说明

界面采用浅色卡片式布局（固定为浅色主题，不随系统深色模式变化），标题栏右侧为保存、加载、导出和恢复默认。

- **左侧：** 核心实验参数（大字号）与均匀覆盖确认；探头孔径、参考下限和可变 OD 范围收在“探头与可变 OD 设置”中，模型说明收在“模型与适用条件”中，均默认折叠。
- **右上：** 逐波长参数。可在“统一衰减片 OD”中输入数值后按回车或点“应用到全部波长”，一键填入所有波长（滤光片在这些波长范围内不更换时使用），个别波长仍可单独修改，新添加的波长也默认使用该值；“实测值单位”可在 nW（功率计读数）和 nW/cm²（功率密度）之间切换。
- **右下：** 推荐固定 OD 卡片和计算结果。目标脉冲平均功率密度和 CW 校准探头读数加粗突出，提示按严重程度着色（红：光源不足或可变 OD 超出范围；橙：读数低于参考下限或功率计读数无法换算；绿：可变 OD 可覆盖）。器件脉冲平均功率、CW 插衰减片功率密度、透过率和 CW 换算功率密度为次要列，默认隐藏，可勾选“显示次要列”查看；CSV 始终导出全部列。

鼠标悬停在输入框和表头上可查看说明。快捷键：计算 Ctrl+Enter（Mac 为 Cmd+Return）、保存 Ctrl+S、加载 Ctrl+O、导出 Ctrl+E。修改参数后旧结果立即清空并显示橙色提示，避免导出过期结果；“恢复默认”会先确认再清除当前输入。

## 使用流程

1. 输入实验的重复频率、实际光脉冲宽度、目标平均光子数，以及椭圆像元的完整长轴和短轴；程序显示占空比 D = fτ。
2. 添加需要计算的波长，填写各波长对应衰减片的实测 OD（脉冲模式下插上后满足目标、CW 校准时取出的那片）；若各波长使用同一片滤光片，用“统一衰减片 OD”一键填入。
3. 把激光切到 CW 模式（与脉冲模式相同的驱动条件），不加任何衰减片（含可变衰减），在器件位置用功率计测量各波长功率并填入；只计算目标时可以留空。
4. 勾选“确认光斑均匀覆盖探头有效孔径，且探头与器件位置的辐照度相同”，程序才会把功率计读数换算为功率密度并输出 CW 校准读数；探头孔径可在“探头与可变 OD 设置”中修改。
5. 点击“计算目标”，查看推荐固定 OD、CW 校准读数和衰减范围提示；点“采用推荐 OD”即可填入全部波长并重新计算。
6. 实验时：CW 模式下取出衰减片，用可变衰减把功率计调到“CW 不插衰减片探头读数”；插回衰减片，切换到脉冲模式。

例如：375 nm、10 kHz、240 ns（占空比 0.24%）、350 × 280 μm 的椭圆像元，希望平均每脉冲入射 0.1 个光子时，器件处目标脉冲平均功率密度约为 **0.688224 pW/cm²**。若使用 OD3 衰减片、直径 9.5 mm 的探头且满足均匀覆盖条件，CW 模式下取出衰减片时功率计应读约 **203.262 nW**。

## 输入与输出

| 输入 | 默认值 | 用途 |
|---|---|---|
| 波长 λ | 375、445、520、633、730、808 nm | 各波长独立计算，可增删 |
| 重复频率 f | 10 kHz | 平均功率与占空比 |
| 光脉冲高值宽度 τ | 240 ns | 决定占空比；CW 校准读数和所需 OD 都随之变化，不改变目标脉冲平均功率 |
| 每脉冲平均入射光子数 μ | 0.1 | 统计均值，不是探测计数 |
| 椭圆完整长轴 / 短轴 | 350 / 280 μm | 不是半轴；换算像元面积 |
| 衰减片 OD（逐波长，校准时移除） | 3 | 脉冲模式下插上后器件处满足目标；CW 校准时取出、正式测量时插回 |
| CW 无衰减实测值（逐波长） | 留空 | 可选，CW 模式、不加任何衰减片（含可变衰减）时在器件位置测量，用于总 OD、可变 OD、透过率和推荐固定 OD；更改驱动条件后须重测 |
| 实测值单位 | nW（功率计读数） | 可切换为 nW/cm²（功率密度）；功率计读数按探头有效孔径面积换算为功率密度，需勾选均匀覆盖确认 |
| 可变 OD 上下限 | 0.04～2 | 判断滤片能否覆盖；下限也用于计算可变衰减取最小时的每脉冲光子数 |
| 探头有效孔径直径 | 9.5 mm | 可修改，S130VC 参考值 |
| 探头参考测量下限 | 0.5 nW | 提示读数偏低，不代表测量精度保证 |
| 确认均匀覆盖孔径且辐照度相同 | 默认未勾选 | 勾选后才输出 CW 校准读数，并允许将功率计读数换算为功率密度；未勾选时提示“未确认均匀覆盖” |

输出：像元面积、占空比、器件脉冲平均功率（pW）、目标脉冲平均功率密度（pW/cm²）、CW 插衰减片功率密度（nW/cm²）、CW 不插衰减片功率密度（nW/cm²）、CW 不插衰减片探头读数（nW）、所需总 OD、可变 OD、可变衰减取下限时每脉冲光子数、透过率、CW 换算功率密度（次要列）及范围提示；填写了 CW 实测值时，另给出推荐整数固定 OD、可行范围、采用后各波长所需可变 OD 和可变衰减取下限时的每脉冲光子数，以及可变 OD 不够用时的差额（CSV 末尾一并导出）。

## 计算模型与适用条件

取精确 SI 常数 h = 6.62607015e−34 J·s、c = 299792458 m/s：

- A = π × 长轴 × 短轴 / 4（统一换算为 cm²）
- Eγ = hc/λ；D = fτ
- 器件目标脉冲平均功率 P = μfEγ；目标脉冲平均功率密度 I = P/A
- CW 插衰减片功率密度（= 脉冲高值功率密度）I_CW = I/D
- CW 不插衰减片功率密度 = I_CW × 10^(衰减片 OD)
- 均匀覆盖时，CW 不插衰减片探头读数 = CW 不插衰减片功率密度 × 探头有效孔径面积
- 实测值为功率计读数时，CW 无衰减功率密度 = 读数 / 探头有效孔径面积（需均匀覆盖）
- 总 OD = log10(CW 无衰减功率密度 × D / I) = log10(CW 无衰减功率密度 / I_CW)；可变 OD = 总 OD − 衰减片 OD
- 总透过率 = 10^(−总 OD)
- 可变衰减取下限时每脉冲光子数 = μ × 10^(总 OD − 衰减片 OD − 可变 OD 下限) = μ × 10^(可变 OD − 下限)：插入衰减片、可变衰减开到最小时可达到的最大值；低于 μ 说明光不够（界面标红）
- 推荐固定 OD F：各波长可变 OD = 总 OD_i − F 需落在 [下限, 上限]，可行区间为 max(总 OD_i − 上限, 0) ≤ F ≤ min(总 OD_i − 下限)；F 只取整数：区间内有整数时取最接近中点的整数（两端余量最大）；区间为空或区间内没有整数时说明可变 OD 不够用（各波长总 OD 跨度 > 上限 − 下限、区间内无整数，或光源不足），并在相邻两个整数中取超出可变范围最少者作为折中值

**核心假设：脉冲模式下的高值功率等于 CW 功率**（矩形脉冲、相同驱动条件），因此脉冲平均功率 = CW 功率 × 占空比。半导体激光器在调制下可能因开关瞬态、热效应或驱动电路带宽，使实际脉冲高值功率偏离 CW 值，脉宽越短越明显；必要时应用快速探测器或其他方法核对。脉宽应为实际光脉冲宽度，电调制宽度未必相同；低值期间漏光忽略。

像元区域内照明近似均匀。功率计换算要求光斑均匀、完全覆盖探头有效孔径，且测量处和器件处辐照度相同；不适用于直接按孔径面积换算小光斑、明显高斯光斑或不同平面光强。

光子数是入射光子统计均值，无需 PDE、暗计数、死时间；这些属于从检测计数反推光功率的另一个模型。OD 应使用对应波长的实测值，不能把单波长标称 OD 无条件套到所有波长。衰减片指外置滤片，不是功率探头自身已校准的内置滤片。

更改重复频率、脉宽或激光驱动条件后，所需 OD 和 CW 校准读数都会变化；更改驱动条件后应重新测量 CW 功率。表中的默认值仅为示例实验配置，应按实际实验修改。

**验证基准：** 375 nm 默认参数应得到面积 7.696902e−4 cm²、占空比 0.24%、目标脉冲平均功率密度 0.688224 pW/cm²。确认探头均匀覆盖、衰减片 OD3 时，CW 不插衰减片探头读数约 203.262 nW，808 nm 对应 94.3355 nW；OD5 时分别为 20326.2 和 9433.55 nW。

## 参数文件与导出

参数保存为 JSON（当前为第 4 版格式，实测值为 CW 值并记录单位）。旧版文件可直接加载：第 1～3 版中的实测值是脉冲平均值，加载时按 ÷ 占空比换算为 CW 值，所需 OD 保持不变；第 1、2 版的实测值按 nW/cm² 解读，第 1 版的“最终固定总 OD”加载时会被忽略。CSV 使用 UTF-8 BOM（可直接用 Excel 打开），包含本次输入、全部结果列和推荐固定 OD。

## 从源码运行

先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，在项目目录运行：

```sh
uv sync --locked --group dev
uv run spad-power        # 或 uv run python -m spad_power
uv run pytest            # 运行测试
```

首次同步需要网络；之后运行使用项目虚拟环境。Python 默认 3.12（项目声明支持 3.12–3.14，CI 在 3.12 上测试）。

## 打包与发布

Windows exe 必须在 Windows 上构建（PyInstaller 不支持交叉打包）。

- **本地打包：** 在 Windows 安装 uv，双击 `build-windows.bat`，或运行 `uv run python scripts/build_windows.py`，输出 `dist/SPAD-Power.exe`。构建机器需要网络下载依赖。
- **GitHub Actions：** 推送到 `main` 或提交 PR 时，[Tests](.github/workflows/ci.yml) 会在 Windows 和 macOS 上运行测试；在 Actions 页面手动运行 [Windows build & release](.github/workflows/windows.yml) 可得到 exe 构建产物。
- **发布新版本：** 修改 `spad_power/__init__.py` 中的 `__version__`，在 `CHANGELOG.md` 添加对应版本的条目，提交后推送标签（如 `git tag v0.2.0 && git push origin v0.2.0`）。工作流会检查标签与版本号一致，运行测试、打包，并自动创建 GitHub Release（说明取自 CHANGELOG）。

程序图标由 `scripts/make_icon.py` 生成（`uv run python scripts/make_icon.py`）。exe 未签名，签名证书不包含在本项目中。

## 项目结构

```text
spad_power/
  model.py                 光功率、衰减与固定 OD 推荐的计算模型（无界面依赖）
  app.py                   图形界面、参数保存/加载、结果导出
  assets/                  程序图标
  __init__.py              版本号
  __main__.py              Python 模块启动入口
tests/                     计算模型与界面功能测试
scripts/
  build_windows.py         Windows 打包脚本
  release_notes.py         从 CHANGELOG 提取 Release 说明
  make_icon.py             生成程序图标
build-windows.bat          Windows 一键构建入口
.github/workflows/         测试与 Windows 构建/发布流程
docs/interface.png         界面截图
CHANGELOG.md               更新日志
```

## 参考

- [uv 项目管理](https://docs.astral.sh/uv/guides/projects/)
- [Qt / PyInstaller 部署](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)
- [Thorlabs S130VC 参考规格](https://www.thorlabs.com/catalogpages/V21/1561.PDF)：9.5 mm 孔径及 500 pW 参考下限。请按所用探头和功率计的实际校准、量程核实。

## 许可证

[MIT](LICENSE) © 2026 hcy2206
