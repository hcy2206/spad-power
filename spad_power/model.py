"""Pure SI-based calculations; photon numbers are incident photons, not detected counts.

Power is measured with the laser in CW mode and no attenuator. Pulsed operation is assumed to reach
the CW power during the pulse (rectangular pulses, same drive), so the pulsed average is
CW power × duty cycle. With a fixed attenuator of OD `od` inserted, the photons incident per pulse
follow from that average power; the SPAD count rates then give the photon detection efficiency.
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
    major_um: float = 350
    minor_um: float = 280
    probe_diameter_mm: float = 9.5
    uniform_probe: bool = False
    measured_unit: str = 'nW'

    def validate(self):
        for name in ('frequency_khz', 'pulse_ns', 'major_um', 'minor_um', 'probe_diameter_mm'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} 必须是有限正数')
        if self.duty > 1:
            raise ValueError('脉冲宽度不能超过重复周期')
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
    od: float = 3  # fixed attenuator in front of the device during the count measurement
    measured: float | None = None  # unattenuated CW value, in Settings.measured_unit
    light_cps: float | None = None  # Ct: total in-gate count rate with the attenuated pulsed light (dark included)
    dark_cps: float | None = None  # Cd: in-gate count rate with the laser off


def pde_from_counts(s: Settings, row: Channel, photons: float | None, warnings: list[str]):
    """Gated SPAD synchronised with the laser at f: at most one count per gate.

    With per-gate count probabilities Pd = Cd/f (dark) and Pt = Ct/f (light on) and Poisson-distributed
    incident photons (mean μ), a gate stays silent only if there is neither a dark count nor a detected
    photon: 1 − Pt = (1 − Pd)·exp(−PDE·μ), so PDE = ln[(1 − Pd) / (1 − Pt)] / μ.
    Returns (p, PDE) where p = (Pt − Pd) / (1 − Pd) is the photon-induced count probability per gate.
    Dead time across gates, afterpulsing and crosstalk are not corrected.
    """
    if row.light_cps is None:
        return None, None
    if row.dark_cps is None:
        warnings.append('未填门内暗计数率，按 0 计算 PDE')
    f = s.frequency_khz * 1e3
    pt, pd = row.light_cps / f, (row.dark_cps or 0) / f
    if pt >= 1 or pd >= 1:
        warnings.append('门内计数率不低于重复频率，无法计算 PDE')
        return None, None
    p = (pt - pd) / (1 - pd)
    if photons is None:
        warnings.append('缺少 CW 实测值，无法计算光子数和 PDE')
        return p, None
    if p <= 0:
        warnings.append('门内总计数率不高于暗计数率，无法计算 PDE')
        return p, None
    pde = (math.log1p(-pd) - math.log1p(-pt)) / photons
    if pde > 1:
        warnings.append('PDE 超过 100%，请检查 OD、CW 实测值或计数率')
    return p, pde


def calculate(s: Settings, row: Channel) -> dict:
    s.validate()
    if not math.isfinite(row.wavelength_nm) or row.wavelength_nm <= 0:
        raise ValueError('波长必须是有限正数')
    if not (math.isfinite(row.od) and 0 <= row.od <= 30):
        raise ValueError('衰减片 OD 必须在 0～30 之间')
    measured = row.measured
    if measured is not None and (not math.isfinite(measured) or measured <= 0):
        raise ValueError('实测值必须为有限正数，或留空')
    for rate in (row.light_cps, row.dark_cps):
        if rate is not None and (not math.isfinite(rate) or rate < 0):
            raise ValueError('计数率必须为非负有限数，或留空')
    energy = H * C / (row.wavelength_nm * 1e-9)
    warnings = []
    cw_density = None  # W/cm², at the device, no attenuator
    if measured is not None:
        if s.measured_unit == 'nW/cm2':
            cw_density = measured * 1e-9
        elif s.uniform_probe:
            cw_density = measured * 1e-9 / s.probe_area_cm2
        else:
            warnings.append('未确认均匀覆盖，功率计读数无法换算')
    density = cw_density * s.duty * 10 ** -row.od if cw_density is not None else None  # pulsed average
    power = density * s.area_cm2 if density is not None else None
    photons = power / (s.frequency_khz * 1e3 * energy) if power is not None else None
    detection, pde = pde_from_counts(s, row, photons, warnings)
    result = dict(wavelength_nm=row.wavelength_nm, photon_energy_j=energy,
        photons=photons, pde_percent=pde * 100 if pde is not None else None, detection_prob=detection,
        device_avg_pw=power * 1e12 if power is not None else None,
        density_avg_pw_cm2=density * 1e12 if density is not None else None,
        measured_nw_cm2=cw_density * 1e9 if cw_density is not None else None,
        status='；'.join(warnings))
    if any(isinstance(v, float) and not math.isfinite(v) for v in result.values()):
        raise ValueError('参数导致数值溢出，请使用合理实验范围')
    return result


PDE_MIN_PERCENT = 7  # indicator 1: PDE above this at every tested wavelength (UV to NIR)
PDE_PEAK_MIN_PERCENT = 20  # indicator 2: peak PDE at least this


def evaluate_criteria(results: list[dict]) -> dict | None:
    """Check the two acceptance indicators over the wavelengths that have a PDE; None if none has."""
    measured = [(r['wavelength_nm'], r['pde_percent']) for r in results if r['pde_percent'] is not None]
    if not measured:
        return None
    below = [wl for wl, pde in measured if not pde > PDE_MIN_PERCENT]
    peak = max(measured, key=lambda item: item[1])
    return dict(all_above=not below, below=below, peak=peak, peak_ok=peak[1] >= PDE_PEAK_MIN_PERCENT,
                missing=len(results) - len(measured))
