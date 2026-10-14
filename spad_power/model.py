"""Pure SI-based calculations; all photons are incident, not detected counts.

Power is measured with the laser in CW mode. Pulsed operation is assumed to reach the CW power
during the pulse (rectangular pulses, same drive), so the pulsed average is CW power × duty cycle.
Each wavelength uses one removable attenuator of OD `removed_od`: with it inserted and the laser
pulsed, the device receives the target photon number; calibration is done in CW mode with it removed.
"""
from dataclasses import dataclass
import math

MEASURED_UNITS = ('nW', 'nW/cm2')  # CW power-meter reading through the probe aperture, or CW density
H = 6.62607015e-34
C = 299792458.0

@dataclass(frozen=True)
class Settings:
    frequency_khz: float = 10
    pulse_ns: float = 240
    photons: float = 0.1
    major_um: float = 350
    minor_um: float = 280
    probe_diameter_mm: float = 9.5
    probe_min_nw: float = 0.5
    uniform_probe: bool = False
    variable_min: float = 0.04
    variable_max: float = 2
    measured_unit: str = 'nW'

    def validate(self):
        for name in ('frequency_khz', 'pulse_ns', 'photons', 'major_um', 'minor_um', 'probe_diameter_mm', 'probe_min_nw'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} 必须是有限正数')
        if self.duty > 1:
            raise ValueError('脉冲宽度不能超过重复周期')
        if not (math.isfinite(self.variable_min) and math.isfinite(self.variable_max) and 0 <= self.variable_min <= self.variable_max <= 30):
            raise ValueError('可变 OD 范围必须满足 0 ≤ 下限 ≤ 上限 ≤ 30')
        if self.measured_unit not in MEASURED_UNITS:
            raise ValueError('实测值单位必须是 nW 或 nW/cm2')

    @property
    def duty(self):
        return self.frequency_khz * 1e3 * self.pulse_ns * 1e-9

    @property
    def area_cm2(self):
        return math.pi * self.major_um * self.minor_um * 1e-8 / 4

    @property
    def probe_area_cm2(self):
        return math.pi * (self.probe_diameter_mm / 10) ** 2 / 4

@dataclass(frozen=True)
class Channel:
    wavelength_nm: float
    removed_od: float = 3
    measured: float | None = None  # unattenuated CW value, in Settings.measured_unit


def calculate(s: Settings, row: Channel) -> dict:
    s.validate()
    if not math.isfinite(row.wavelength_nm) or row.wavelength_nm <= 0:
        raise ValueError('波长必须是有限正数')
    if not (math.isfinite(row.removed_od) and 0 <= row.removed_od <= 30):
        raise ValueError('衰减片 OD 必须在 0～30 之间')
    measured = row.measured
    if measured is not None and (not math.isfinite(measured) or measured <= 0):
        raise ValueError('实测值必须为有限正数，或留空')
    energy = H * C / (row.wavelength_nm * 1e-9)
    power = s.photons * s.frequency_khz * 1e3 * energy
    density = power / s.area_cm2
    density_cw = density / s.duty  # CW density at the device (attenuator in) giving the target when pulsed
    calibration = density_cw * 10 ** row.removed_od
    probe = calibration * s.probe_area_cm2 if s.uniform_probe else None
    warnings = []
    measured_density = None
    if measured is not None:
        if s.measured_unit == 'nW/cm2':
            measured_density = measured * 1e-9
        elif s.uniform_probe:
            measured_density = measured * 1e-9 / s.probe_area_cm2
        else:
            warnings.append('未确认均匀覆盖，功率计读数无法换算')
    od = math.log10(measured_density / density_cw) if measured_density is not None else None
    variable = od - row.removed_od if od is not None else None
    if probe is None:
        warnings.append('未确认均匀覆盖，不输出探头读数')
    elif probe < s.probe_min_nw * 1e-9:
        warnings.append('探头目标低于参考下限')
    if variable is not None:
        if od < 0:
            warnings.append('光源不足，衰减无法达到目标')
        elif not s.variable_min <= variable <= s.variable_max:
            warnings.append('所需可变 OD 超出范围')
        else:
            warnings.append('可变 OD 可覆盖')
    result = dict(wavelength_nm=row.wavelength_nm, photon_energy_j=energy,
        pulse_energy_j=s.photons * energy, device_avg_pw=power * 1e12,
        density_avg_pw_cm2=density * 1e12, density_cw_nw_cm2=density_cw * 1e9,
        calibration_nw_cm2=calibration * 1e9, probe_nw=probe * 1e9 if probe is not None else None,
        measured_nw_cm2=measured_density * 1e9 if measured_density is not None else None,
        total_od=od, variable_od=variable, transmission=10 ** (-od) if od is not None else None,
        # Mean photons per pulse with the attenuator in and the variable attenuator at its minimum.
        max_photons=s.photons * 10 ** (variable - s.variable_min) if variable is not None else None,
        status='；'.join(warnings))
    if any(isinstance(v, float) and not math.isfinite(v) for v in result.values()):
        raise ValueError('参数导致数值溢出，请使用合理实验范围')
    return result


def recommend_fixed_od(s: Settings, rows: list[Channel]) -> dict | None:
    """Pick one integer fixed OD shared by all measured wavelengths so each needs variable OD within range.

    Uses the unattenuated maximum of each row; returns None when no row has a usable one.
    """
    totals = [(r.wavelength_nm, od) for r in rows if (od := calculate(s, r)['total_od']) is not None]
    if not totals:
        return None
    low = max(od - s.variable_max for _, od in totals)
    high = min(od - s.variable_min for _, od in totals)
    choices = list(range(max(math.ceil(low - 1e-9), 0), min(math.floor(high + 1e-9), 30) + 1))
    feasible = bool(choices)
    if feasible:
        center = (max(low, 0) + high) / 2
        od = min(choices, key=lambda c: (abs(c - center), -c))
    else:
        # No integer fits: of the two integers around the balanced point, take the one that leaves
        # the smallest excess beyond the variable range (the larger one on a tie).
        def excess(f):
            return max(max(t - f - s.variable_max, s.variable_min - (t - f), 0) for _, t in totals)
        center = (low + high) / 2
        od = min({min(max(math.floor(center), 0), 30), min(max(math.ceil(center), 0), 30)}, key=lambda c: (excess(c), -c))
    variable = [(wl, total - od) for wl, total in totals]
    max_photons = [(wl, s.photons * 10 ** (v - s.variable_min)) for wl, v in variable]
    span = max(t for _, t in totals) - min(t for _, t in totals)
    width = s.variable_max - s.variable_min
    messages = []
    if feasible:
        messages.append(f'可选整数 OD：{"、".join(map(str, choices))}（连续可行范围 {max(low, 0):.3g}～{high:.3g}），'
                        f'各波长可变 OD 均在 {s.variable_min:g}～{s.variable_max:g} 之内')
    else:
        if max(low, 0) <= high:
            messages.append(f'可变 OD 不够用：连续可行范围 OD {max(low, 0):.3g}～{high:.3g} 内没有整数')
        if span > width:
            messages.append(f'可变 OD 不够用：各波长所需总 OD 跨度 {span:.3g}，超过可变 OD 可调宽度 {width:.3g}，还差 {span - width:.3g}')
        weak = [wl for wl, t in totals if t < s.variable_min]
        if weak:
            messages.append('光源不足：' + '、'.join(f'{wl:g} nm' for wl in weak) + f' 在不加衰减片、可变 OD 取下限 {s.variable_min:g} 时仍低于目标')
        for wl, v in variable:
            if v > s.variable_max:
                messages.append(f'{wl:g} nm 需可变 OD {v:.3g}，超出上限 {v - s.variable_max:.3g}（衰减不够）')
            elif v < s.variable_min:
                messages.append(f'{wl:g} nm 需可变 OD {v:.3g}，低于下限 {s.variable_min - v:.3g}（衰减偏多）')
    probe = None
    if s.uniform_probe:
        probe = min(calculate(s, Channel(r.wavelength_nm, od))['probe_nw'] for r in rows)
        if probe < s.probe_min_nw:
            messages.append(f'该 OD 下最低校准读数 {probe:.4g} nW，低于参考下限' + ('，可选更大的整数 OD' if feasible and od < choices[-1] else ''))
    return dict(recommended_od=od, feasible=feasible, low=low, high=high, span=span, width=width,
        totals=totals, variable=variable, max_photons=max_photons, min_probe_nw=probe, messages=messages)
