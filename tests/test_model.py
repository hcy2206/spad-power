from dataclasses import replace
import math
import pytest
from spad_power.model import Settings, Channel, calculate

DENSITY = Settings(measured_unit='nW/cm2')
# CW density (nW/cm², no attenuator) that gives 0.1 photons per pulse at 375 nm with OD 3 and the default
# 10 kHz / 240 ns / 350 × 280 μm setup: 0.688224 pW/cm² pulsed average / 0.24 % duty × 10^3.
CW_375 = 286.7597980495864


def test_reference_photons_per_pulse():
    r = calculate(DENSITY, Channel(375, od=3, measured=CW_375))
    assert DENSITY.area_cm2 == pytest.approx(0.0007696902001294994)
    assert DENSITY.duty == pytest.approx(0.0024)
    assert r['density_avg_pw_cm2'] == pytest.approx(0.688224, rel=1e-6)
    assert r['photons'] == pytest.approx(0.1)
    assert r['measured_nw_cm2'] == pytest.approx(CW_375)


def test_photons_scale_with_od_duty_and_wavelength():
    base = calculate(DENSITY, Channel(375, od=3, measured=CW_375))['photons']
    assert calculate(DENSITY, Channel(375, od=5, measured=CW_375))['photons'] == pytest.approx(base / 100)
    assert calculate(replace(DENSITY, pulse_ns=480), Channel(375, od=3, measured=CW_375))['photons'] == pytest.approx(base * 2)
    assert calculate(DENSITY, Channel(750, od=3, measured=CW_375))['photons'] == pytest.approx(base * 2)
    assert calculate(DENSITY, Channel(375))['photons'] is None


def test_power_meter_reading_uses_probe_aperture():
    s = Settings(uniform_probe=True)
    power = calculate(s, Channel(375, od=3, measured=CW_375 * s.probe_area_cm2))
    assert power['photons'] == pytest.approx(0.1)
    unconfirmed = calculate(Settings(), Channel(375, od=3, measured=CW_375))
    assert unconfirmed['photons'] is None and '无法换算' in unconfirmed['status']


def test_pde_from_light_and_dark_counts():
    r = calculate(DENSITY, Channel(375, od=3, measured=CW_375, light_cps=500, dark_cps=100))
    assert r['detection_prob'] == pytest.approx(0.04)  # (500 − 100) / 10 kHz
    assert r['pde_percent'] == pytest.approx(-math.log(0.96) / 0.1 * 100)
    no_dark = calculate(DENSITY, Channel(375, od=3, measured=CW_375, light_cps=500))
    assert '按 0 计算' in no_dark['status'] and no_dark['pde_percent'] == pytest.approx(-math.log(0.95) / 0.1 * 100)
    below = calculate(DENSITY, Channel(375, od=3, measured=CW_375, light_cps=50, dark_cps=100))
    assert below['pde_percent'] is None and '无法计算 PDE' in below['status']
    no_photons = calculate(DENSITY, Channel(375, light_cps=500, dark_cps=100))
    assert no_photons['pde_percent'] is None and '缺少 CW 实测值' in no_photons['status']
    assert '超过 100%' in calculate(DENSITY, Channel(375, od=5, measured=CW_375, light_cps=500))['status']


@pytest.mark.parametrize('key,value', [('frequency_khz', 0), ('major_um', math.nan), ('pulse_ns', 100001), ('measured_unit', 'W')])
def test_invalid_settings(key, value):
    with pytest.raises(ValueError):
        calculate(replace(Settings(), **{key: value}), Channel(375))


@pytest.mark.parametrize('row', [Channel(0), Channel(math.inf), Channel(375, od=-1), Channel(375, od=math.nan),
                                 Channel(375, measured=-1), Channel(375, light_cps=-1), Channel(375, dark_cps=math.inf)])
def test_invalid_channels(row):
    with pytest.raises(ValueError):
        calculate(Settings(), row)
