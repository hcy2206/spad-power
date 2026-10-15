<p align="center">
  <img src="spad_power/assets/icon.png" width="96" alt="SPAD-Power icon">
</p>

<h1 align="center">SPAD-Power · SPAD 光子数与 PDE 计算器</h1>

<p align="center">
  <a href="https://github.com/hcy2206/spad-power/actions/workflows/ci.yml"><img src="https://github.com/hcy2206/spad-power/actions/workflows/ci.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/hcy2206/spad-power/releases/latest"><img src="https://img.shields.io/github/v/release/hcy2206/spad-power" alt="Release"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey" alt="Platform">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
</p>

<p align="center">
  <b>测量激光 CW 功率，按占空比和衰减片 OD 算出每个脉冲入射到 SPAD 像元的光子数，再由门控计数和暗计数按门控公式计算光子探测效率（PDE），并判定 PDE 指标。</b>
</p>

> **English:** A small desktop calculator for single-photon avalanche diode (SPAD) experiments. Measure the laser power in CW mode without attenuation; the app combines it with the pulse duty cycle and the attenuator OD to give the mean number of photons incident on the pixel per pulse, then derives the photon detection efficiency (PDE) of a gated SPAD from the in-gate total and dark count rates, PDE = ln[(1 − Cd/f)/(1 − Ct/f)]/μ, and checks the PDE acceptance indicators. The UI is in Simplified Chinese. Windows builds are on the [Releases](https://github.com/hcy2206/spad-power/releases) page.

![SPAD-Power 界面](docs/interface.png)

## 下载

- **Windows：** 在 [Releases](https://github.com/hcy2206/spad-power/releases/latest) 页面下载 `SPAD-Power-<版本>-windows-x64.exe`，双击运行，无需安装 Python。程序未签名，首次运行若出现“Windows 已保护你的电脑”，点“更多信息”→“仍要运行”。
- **macOS / 其他平台：** 从源码运行，见[从源码运行](#从源码运行)。

程序是离线计算工具，不连接或控制激光器、功率计和 SPAD，也不采集仪器数据。

## 为什么是 CW 方案

脉冲模式下的平均功率极低（pW 量级），功率计难以测准。本方案在 CW（连续）模式、不加衰减片时测量激光功率，再按脉冲占空比 D = fτ 和衰减片 OD 换算到实际照射 SPAD 时的脉冲平均功率和每脉冲光子数。例如默认参数下（10 kHz、240 ns、OD5），375 nm 的 CW 功率计读数约 20.3 μW 时，每个脉冲约入射 0.1 个光子。

## 功能

- **每脉冲入射光子数：** 由各波长的 CW 无衰减实测值、占空比和衰减片 OD，计算每个脉冲平均入射到像元的光子数。
- **PDE 计算：** 输入门控时间内的总计数率 Ct 和暗计数率 Cd，按门控 SPAD 的泊松公式计算光子探测效率。
- **指标判定：** 指标 1：各波长 PDE > 7%；指标 2：峰值 PDE ≥ 20%。结果区显示是否通过，低于 7% 的 PDE 标红。
- **PDE 曲线：** 结果旁绘制 PDE 随波长变化的折线图，标出峰值，悬停可查看各波长的 PDE 和光子数。
- **多波长：** 同时计算多个波长；“统一衰减片 OD”和“统一门内暗计数 Cd”一键填入所有波长，个别波长仍可单独修改。
- **实测值单位：** 功率计读数（nW，按探头孔径换算为功率密度）或功率密度（nW/cm²）。
- **记录与导出：** 保存和加载 JSON 参数，导出包含输入和全部结果的 CSV。

## 界面说明

界面采用浅色卡片式布局（固定为浅色主题，不随系统深色模式变化），标题栏右侧为保存、加载、导出和恢复默认。

- **左侧：** 实验参数（重复频率、脉宽、像元长短轴，大字号）；“功率计换算”卡片包含实测值单位和均匀覆盖确认，探头孔径收在“探头设置”中，模型说明收在“模型与适用条件”中，均默认折叠。
- **右上：** 逐波长参数——波长、衰减片 OD、CW 无衰减实测值、门内总计数 Ct、门内暗计数 Cd；上方可统一填入衰减片 OD 和门内暗计数（输入后按回车或点“应用到全部波长”）。
- **右下：** 计算结果。上方一行显示两项指标是否通过（✓/✗ 加文字）；下方左侧表格、右侧 PDE 曲线（横轴波长、纵轴 PDE，带 7% 和 20% 指标参考线，中间可拖动调整宽度）。低于 7% 的 PDE 在表格中标红、曲线上该点为红色。表格中每脉冲入射光子数和 PDE 加粗突出；每门光致计数概率、器件脉冲平均功率与功率密度、CW 换算功率密度为次要列，默认隐藏，可勾选“显示次要列”查看。无法计算的值显示为橙色“—”，鼠标悬停该行可查看原因，顶部摘要会注明有几个波长有提示；CSV 始终导出全部列（含提示）。

鼠标悬停在输入框和表头上可查看说明。快捷键：计算 Ctrl+Enter（Mac 为 Cmd+Return）、保存 Ctrl+S、加载 Ctrl+O、导出 Ctrl+E。修改参数后旧结果立即清空并显示橙色提示，避免导出过期结果；“恢复默认”会先确认再清除当前输入。

## 使用流程

1. 输入重复频率、实际光脉冲宽度，以及椭圆像元的完整长轴和短轴；程序显示占空比 D = fτ。
2. 把激光切到 CW 模式（与脉冲模式相同的驱动条件），不加衰减片，在器件位置用功率计测量各波长功率，填入“CW 无衰减实测值”。
3. 实测值为功率计读数时，勾选“确认光斑均匀覆盖探头有效孔径，且探头与器件位置的辐照度相同”，程序才会按探头孔径换算为功率密度；探头孔径可在“探头设置”中修改。
4. SPAD 门控与激光同步于频率 f。插入衰减片、切回脉冲模式，记录门控时间内的总计数率 Ct；关闭光源，在相同门控和偏置条件下记录门内暗计数率 Cd。填入衰减片 OD 和计数率（各波长相同时用“统一衰减片 OD”“统一门内暗计数 Cd”一键填入）。计数器采集时间不是 1 秒时，先换算为每秒计数。
5. 点击“计算”，结果表给出每脉冲入射光子数和 PDE，右侧曲线显示 PDE 随波长的变化，上方显示指标判定；按需保存参数、导出 CSV。

## 输入与输出

| 输入 | 默认值 | 用途 |
|---|---|---|
| 波长 λ | 375、445、520、633、730、808 nm | 各波长独立计算，可增删 |
| 重复频率 f | 10 kHz | 占空比；把计数率换算为每脉冲探测概率 |
| 光脉冲高值宽度 τ | 240 ns | 占空比 D = fτ |
| 椭圆完整长轴 / 短轴 | 350 / 280 μm | 不是半轴；换算像元面积 |
| 衰减片 OD（逐波长） | 3 | 测计数时插在器件前的外置衰减片，填该波长处的实测 OD |
| CW 无衰减实测值（逐波长） | 留空 | CW 模式、不加衰减片时在器件位置测量；计算光子数和 PDE 必填 |
| 门内总计数 Ct（逐波长） | 留空 | 插入衰减片、脉冲模式下 SPAD 门控时间内的计数之和（cps，含暗计数），填写后计算 PDE |
| 门内暗计数 Cd（逐波长） | 留空 | 关闭光源、相同门控与偏置条件下门控时间内的计数之和（cps），不是自由运行的整周期暗计数；留空按 0 计算并提示 |
| 实测值单位 | nW（功率计读数） | 可切换为 nW/cm²（功率密度） |
| 探头有效孔径直径 | 9.5 mm | 功率计读数换算为功率密度，S130VC 参考值 |
| 确认均匀覆盖孔径且辐照度相同 | 默认未勾选 | 实测值为功率计读数时，勾选后才能换算 |

输出：像元面积、占空比；逐波长的每脉冲入射光子数、PDE（%），指标判定，以及次要列中的每门光致计数概率、器件脉冲平均功率（pW）、器件脉冲平均功率密度（pW/cm²）、CW 无衰减功率密度（nW/cm²）；PDE 随波长的折线图；CSV 中另含各波长的提示和指标判定。

## 计算方法（详细）

本节逐步给出程序的全部计算，便于核对。所有计算在 `spad_power/model.py` 中完成（`Settings` 的属性、`calculate()`、`pde_from_counts()`），界面只负责读取输入和显示结果。下面的推导与代码一一对应，最后附一个用程序实际算出的完整数值例子。

### 1. 输入与单位换算

程序内部统一使用 SI 单位，面积用 cm²、功率用 W。界面输入按下表换算：

| 输入 | 界面单位 | 内部换算 | 符号 |
|---|---|---|---|
| 重复频率 | kHz | × 10³ → Hz | f |
| 光脉冲高值宽度 | ns | × 10⁻⁹ → s | τ |
| 椭圆完整长轴、短轴 | μm | × 10⁻⁴ → cm | a、b |
| 探头有效孔径直径 | mm | × 10⁻¹ → cm | d |
| 波长 | nm | × 10⁻⁹ → m | λ |
| 衰减片 OD | 无量纲 | — | OD |
| CW 无衰减实测值 | nW 或 nW/cm² | × 10⁻⁹ → W 或 W/cm² | P_meter 或 I_CW |
| 门内总计数、门内暗计数 | cps（次/秒） | — | C_t、C_d |

### 2. 物理常数

采用 2019 SI 精确值：普朗克常数 h = 6.62607015 × 10⁻³⁴ J·s，光速 c = 299792458 m/s。

### 3. 计算步骤

**(1) 单光子能量**

$$E_\gamma = \frac{hc}{\lambda}$$

单位 J。

**(2) 像元面积**

像元按椭圆处理，a、b 是完整的长轴和短轴（不是半轴）：

$$A = \frac{\pi a b}{4}$$

单位 cm²，代码为 `Settings.area_cm2`。

**(3) 占空比**

$$D = f\tau$$

无量纲，代码为 `Settings.duty`。程序要求 D ≤ 1。

**(4) CW 无衰减功率密度**（器件位置、CW 模式、不加衰减片），单位 W/cm²：

- 实测值单位为 nW/cm² 时，直接采用：$I_\text{CW} = $ 实测值 × 10⁻⁹。
- 实测值单位为 nW（功率计读数）时，按探头有效孔径面积换算：

$$A_\text{probe} = \frac{\pi d^2}{4}, \qquad I_\text{CW} = \frac{P_\text{meter}}{A_\text{probe}}$$

$A_\text{probe}$ 对应代码 `Settings.probe_area_cm2`。这一步要求勾选“确认光斑均匀覆盖探头有效孔径，且探头与器件位置的辐照度相同”；未勾选时不做换算，后续各量都不计算，并给出提示。

**(5) 器件处脉冲平均功率密度**（脉冲模式、插入衰减片），单位 W/cm²：

$$I = I_\text{CW} \cdot D \cdot 10^{-\text{OD}}$$

这一步依赖核心假设：脉冲高值期间的功率等于 CW 功率，因此一个周期内的平均功率等于 CW 功率乘以占空比。衰减片按透过率 $10^{-\text{OD}}$ 计入。

**(6) 像元上的脉冲平均功率**

$$P = I \cdot A$$

单位 W。

**(7) 每脉冲平均入射光子数**

每秒入射的光子数为 $P / E_\gamma$，每秒有 f 个脉冲，所以

$$\mu = \frac{P}{f\,E_\gamma} = \frac{I_\text{CW}\,D\,10^{-\text{OD}}\,A\,\lambda}{f\,h\,c}$$

由于 D = fτ，上式也可以写成 $\mu = I_\text{CW}\,\tau\,10^{-\text{OD}}\,A\,\lambda/(hc)$，即“高值期间的能量除以单光子能量”。可见 μ 与重复频率无关，与脉宽 τ 成正比。

**(8) 每门计数概率**（代码 `pde_from_counts()`）

SPAD 工作在门控模式，门与激光脉冲同步于频率 f，每个门至多记一次计数。C_t、C_d 是门控时间内的计数率（次/秒），所以

$$P_t = \frac{C_t}{f}, \qquad P_d = \frac{C_d}{f}$$

分别是有光和无光时每个门产生计数的概率。门内暗计数留空时按 0 计算，并给出提示。

**(9) PDE（门控泊松模型，与测试方法公式相同）**

每个脉冲入射的光子数服从均值为 μ 的泊松分布，每个光子以概率 PDE 被独立探测到，所以被探测到的光子数服从均值为 PDE·μ 的泊松分布，“一个都没探测到”的概率为 $e^{-\text{PDE}\cdot\mu}$。暗计数与光子探测相互独立。一个门**没有计数**，要求既没有暗计数、也没有探测到光子：

$$1 - P_t = (1 - P_d)\,e^{-\text{PDE}\cdot\mu}$$

解得

$$\text{PDE} = \frac{1}{\mu}\ln\frac{1 - C_d/f}{1 - C_t/f}$$

代码用 `(math.log1p(-Pd) - math.log1p(-Pt)) / μ` 计算，概率很小时数值更精确。界面显示 PDE × 100（%）。

次要列“每门光致计数概率”为 $p = (P_t - P_d)/(1 - P_d)$，即排除暗计数后由光子引起计数的概率。可以验证 $\text{PDE} = -\ln(1 - p)/\mu$，和上式等价。

与常见的线性公式 PDE ≈ (C_t − C_d)/(μf) 相比：门控公式考虑了“已被暗计数触发的门不能再记光子”，以及一个门里有多个光子时只记一次，所以结果更大。两项修正在概率很小时分别约为 P_d 和 p/2。

### 4. 完整数值例子（可用于核对）

输入：375 nm，f = 10 kHz，τ = 240 ns，像元 350 × 280 μm，OD = 5，CW 功率计读数 20300 nW（探头直径 9.5 mm，已确认均匀覆盖），门内总计数 C_t = 420 cps，门内暗计数 C_d = 100 cps。

| 步骤 | 计算 | 结果 |
|---|---|---|
| (1) | $E_\gamma$ = 6.62607015e−34 × 299792458 / 375e−9 | 5.297189 × 10⁻¹⁹ J |
| (2) | A = π × 0.035 × 0.028 / 4 | 7.696902 × 10⁻⁴ cm² |
| (3) | D = 10⁴ × 240 × 10⁻⁹ | 0.0024 |
| (4) | $A_\text{probe}$ = π × 0.95² / 4；$I_\text{CW}$ = 20300 × 10⁻⁹ / 0.7088218 | 0.7088218 cm²；2.863907 × 10⁻⁵ W/cm²（28639.07 nW/cm²） |
| (5) | I = 2.863907e−5 × 0.0024 × 10⁻⁵ | 6.873377 × 10⁻¹³ W/cm²（0.6873377 pW/cm²） |
| (6) | P = 6.873377e−13 × 7.696902e−4 | 5.290371 × 10⁻¹⁶ W（0.0005290371 pW） |
| (7) | μ = 5.290371e−16 / (10⁴ × 5.297189e−19) | 0.09987129 个/脉冲 |
| (8) | P_t = 420 / 10⁴；P_d = 100 / 10⁴ | 0.042；0.01 |
| (9) | PDE = [ln(1 − 0.01) − ln(1 − 0.042)] / 0.09987129 = (−0.01005034 + 0.04290750) / 0.09987129 | 0.3289951（32.89951%） |

作为对比，线性公式 (C_t − C_d)/(μf) 给出 32.04124%，门控公式多出约 2.7%（≈ P_d + p/2）。以上每一行都与程序的 `calculate()` 输出一致。截图中 375 nm 一行就是这组输入。

另一组便于心算的基准：375 nm、OD3、$I_\text{CW}$ = 286.7598 nW/cm²（9.5 mm 探头读数约 203.26 nW）时，μ = 0.1000；再取 C_t = 500 cps、C_d = 100 cps，得 PDE = ln(0.99 / 0.95) / 0.1 = 41.24%。

### 5. 误差如何传递到 PDE

PDE ∝ 1/μ。在 p 不变时，μ 的相对误差会以相反符号、同样大小传到 PDE。μ 与各输入的关系如下：

| 输入 | μ 与它的关系 | 举例 |
|---|---|---|
| CW 功率计读数 / 功率密度 | 正比 | 读数偏高 5% → 算出的 PDE 偏低约 5%（准确为 1 − 1/1.05 ≈ 4.8%） |
| 衰减片 OD | 10^(−OD) | OD 偏差 0.02 → μ 变化约 4.7%；偏差 0.05 → 约 12% |
| 脉宽 τ | 正比（μ 与 f 无关） | 实际光脉宽比输入值宽 10% → 算出的 PDE 偏高约 10% |
| 像元长轴、短轴 | 各自正比 | 每轴偏差 2% → 面积偏差约 4% |
| 探头孔径直径 d | 与 d² 成反比（功率计读数模式） | d 偏差 2% → 约 4% |
| 波长 λ | 正比 | 通常可忽略 |
| 门内总计数 C_t、暗计数 C_d | PDE 近似正比于 C_t − C_d | C_d 接近 C_t 时，相对误差会被放大；Cd 误用整周期暗计数会严重低估 PDE |

其中 OD 的影响最大，应使用该波长处实测的 OD。“脉冲高值功率等于 CW 功率”这一假设的偏差，会直接按比例进入 μ。

### 6. 无法计算时的处理

| 情况 | 处理 |
|---|---|
| 实测值为功率计读数，但未勾选均匀覆盖 | 不换算，光子数和 PDE 显示“—”，提示“功率计读数无法换算” |
| 未填 CW 实测值，但填了门内总计数 | 光子数和 PDE 显示“—”，提示“缺少 CW 实测值” |
| 未填门内暗计数 | 按 0 计算，并提示 |
| C_t ≤ C_d（总计数不高于暗计数） | PDE 显示“—”，并提示 |
| C_t ≥ f 或 C_d ≥ f（每门计数概率 ≥ 1） | 公式不适用，PDE 显示“—”，并提示 |
| PDE > 100% | 照常显示，并提示检查 OD、CW 实测值或计数率 |
| 输入非法（频率、脉宽、尺寸非正，OD 超出 0～30，计数率为负，D > 1 等） | 计算前报错，弹窗说明 |

界面表格显示 7 位有效数字，CSV 导出保留全部精度。

### 7. 指标判定（代码 `evaluate_criteria()`）

- **指标 1：** 有 PDE 的每个波长都满足 PDE > 7%（严格大于，等于 7% 判为未通过）。未通过时列出低于指标的波长。
- **指标 2：** 各波长 PDE 的最大值（峰值）≥ 20%，同时给出峰值所在波长。
- 没有 PDE 的波长（缺少 CW 实测值或计数）不参与判定，结果中注明其数量。“紫外到近红外”的覆盖范围由所测波长决定，程序不检查波段是否齐全。
- 两项判定显示在结果区上方，并写入 CSV 末尾。

### 8. 适用前提

- **脉冲高值功率等于 CW 功率**（矩形脉冲、相同驱动条件），脉冲平均功率 = CW 功率 × 占空比。半导体激光器在调制下可能因开关瞬态、热效应或驱动电路带宽，使实际脉冲高值功率偏离 CW 值，脉宽越短越明显；必要时应用快速探测器或其他方法核对。τ 应为实际光脉冲宽度，电调制宽度未必相同；低值期间的漏光忽略不计。
- **照明均匀：** 像元区域内照明近似均匀。功率计换算还要求光斑均匀、完全覆盖探头有效孔径，且测量处和器件处辐照度相同；不适用于小光斑、明显高斯光斑或不同平面的光强。
- **OD 取值：** 使用对应波长的实测 OD，不能把单波长的标称 OD 套用到所有波长。衰减片指外置滤片，不是功率探头自身已校准的内置滤片。
- **计数：** 按门控 SPAD 处理，门与激光同步于 f、每门至多一次计数；C_t、C_d 均为门控时间内的计数率，且在相同门宽、门位置、偏压和温度下测量。未修正后脉冲和串扰。测试方法要求每个波长重复测量三次、取三次 PDE 的平均值，本程序每次计算一组计数，平均需在程序外完成。
- **重测：** 更改重复频率、脉宽或激光驱动条件后，应重新测量 CW 功率。

## 参数文件与导出

参数保存为 JSON（当前为第 6 版格式）。旧版文件可直接加载：不再使用的设置（目标光子数、可变 OD 范围、探头参考下限、第 1 版的“最终固定总 OD”）会被忽略；第 1～3 版中的实测值是脉冲平均值，加载时按 ÷ 占空比换算为 CW 值；第 1、2 版的实测值按 nW/cm² 解读。CSV 使用 UTF-8 BOM（可直接用 Excel 打开），包含本次输入和全部结果列。

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
  model.py                 光子数与 PDE 的计算模型（无界面依赖）
  app.py                   图形界面、参数保存/加载、结果导出
  chart.py                 PDE 随波长变化的折线图
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