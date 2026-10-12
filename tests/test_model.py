from dataclasses import replace
import math
import pytest
from spad_power.model import Settings, Channel, calculate, recommend_fixed_od


def test_latest_reference():
    s = Settings(uniform_probe=True)
    r = calculate(s, Channel(375))
    assert s.area_cm2 == pytest.approx(0.0007696902001294994)
    assert s.duty == pytest.approx(0.0024)
    assert r['density_avg_pw_cm2'] == pytest.approx(0.688224, rel=1e-6)
    assert r['density_cw_nw_cm2'] == pytest.approx(0.688224e-3 / 0.0024, rel=1e-6)
    assert r['probe_nw'] == pytest.approx(0.48782786015698176 / 0.0024)  # CW reading, attenuator removed
    assert '低于' not in r['status']
    low = calculate(replace(s, probe_min_nw=500), Channel(375))
    assert '低于' in low['status']


def test_cw_attenuation():
    s = Settings(frequency_khz=1000, pulse_ns=200, measured_unit='nW/cm2')
    r = calculate(s, Channel(445, measured=865))
    # The pulsed average is CW × duty (0.2): log10(865 nW/cm² × 0.2 / target)
    assert r['total_od'] == pytest.approx(4.17361534314394 + math.log10(0.2))
    assert r['variable_od'] == pytest.approx(r['total_od'] - 3)
    assert r['transmission'] == pytest.approx(10 ** -r['total_od'])


def test_variable_od_is_beyond_the_attenuator():
    r = calculate(Settings(frequency_khz=1000, pulse_ns=200, measured_unit='nW/cm2'), Channel(445, removed_od=4, measured=865))
    assert r['variable_od'] == pytest.approx(r['total_od'] - 4)
    assert r['calibration_nw_cm2'] == pytest.approx(r['density_avg_pw_cm2'] * 1e-3 / 0.2 * 1e4)


def test_pulse_width_scales_cw_targets_only():
    a = calculate(Settings(uniform_probe=True, measured_unit='nW/cm2'), Channel(520, measured=1000))
    b = calculate(Settings(uniform_probe=True, measured_unit='nW/cm2', pulse_ns=480), Channel(520, measured=1000))
    assert a['device_avg_pw'] == b['device_avg_pw']
    assert a['density_cw_nw_cm2'] == pytest.approx(2 * b['density_cw_nw_cm2'])
    assert a['probe_nw'] == pytest.approx(2 * b['probe_nw'])
    assert b['total_od'] == pytest.approx(a['total_od'] + math.log10(2))


def test_probe_requires_confirmation_and_od_scaling():
    assert calculate(Settings(), Channel(808))['probe_nw'] is None
    a = calculate(Settings(uniform_probe=True), Channel(808))
    b = calculate(Settings(uniform_probe=True), Channel(808, removed_od=5))
    assert b['probe_nw'] == pytest.approx(a['probe_nw'] * 100)
    assert b['probe_nw'] == pytest.approx(22.640525687978734 / 0.0024)


@pytest.mark.parametrize('key,value', [('frequency_khz', 0), ('photons', -1), ('major_um', math.nan), ('pulse_ns', 100001), ('variable_max', -1)])
def test_invalid_settings(key, value):
    with pytest.raises(ValueError):
        calculate(replace(Settings(), **{key: value}), Channel(375))


@pytest.mark.parametrize('row', [Channel(0), Channel(math.inf), Channel(375, removed_od=-1), Channel(375, measured=-1), Channel(375, removed_od=math.nan)])
def test_invalid_channels(row):
    with pytest.raises(ValueError):
        calculate(Settings(), row)


def test_insufficient_source():
    result = calculate(Settings(measured_unit='nW/cm2'), Channel(375, measured=1e-8))
    assert result['total_od'] < 0
    assert '光源不足' in result['status']


DENSITY = Settings(measured_unit='nW/cm2')


def unattenuated(wavelength, total_od, s=DENSITY):
    return Channel(wavelength, measured=calculate(s, Channel(wavelength))['density_cw_nw_cm2'] * 10 ** total_od)


def test_recommend_fixed_od_centers_feasible_range():
    rec = recommend_fixed_od(DENSITY, [unattenuated(375, 5.0), unattenuated(445, 5.6), Channel(520)])
    assert rec['feasible']
    assert rec['low'] == pytest.approx(3.6) and rec['high'] == pytest.approx(4.96)
    assert rec['recommended_od'] == 4
    assert [v for _, v in rec['variable']] == pytest.approx([1.0, 1.6])
    assert recommend_fixed_od(DENSITY, [Channel(375)]) is None


def test_recommend_fixed_od_reports_insufficient_variable_range():
    rec = recommend_fixed_od(DENSITY, [unattenuated(375, 2.0), unattenuated(445, 5.0)])
    assert not rec['feasible']
    assert rec['span'] - rec['width'] == pytest.approx(1.04)
    assert rec['recommended_od'] == 2  # OD 2 leaves 1.0 beyond the range, OD 3 leaves 1.04
    assert '可变 OD 不够用' in rec['messages'][0]


def test_recommend_fixed_od_requires_an_integer():
    s = replace(DENSITY, variable_max=0.5)
    rec = recommend_fixed_od(s, [unattenuated(375, 5.2, s), unattenuated(445, 5.0, s)])
    assert not rec['feasible'] and '没有整数' in rec['messages'][0]
    assert rec['recommended_od'] == 5
    rec = recommend_fixed_od(DENSITY, [unattenuated(375, 5.5), unattenuated(445, 6.1)])
    assert rec['feasible'] and isinstance(rec['recommended_od'], int)


def test_power_meter_reading_uses_probe_aperture():
    density = calculate(DENSITY, Channel(445, measured=865))
    s = Settings(uniform_probe=True)
    power = calculate(s, Channel(445, measured=865 * s.probe_area_cm2))
    assert power['total_od'] == pytest.approx(density['total_od'])
    assert power['measured_nw_cm2'] == pytest.approx(865)
    unconfirmed = calculate(Settings(), Channel(445, measured=865))
    assert unconfirmed['total_od'] is None and '无法换算' in unconfirmed['status']
    assert recommend_fixed_od(Settings(), [Channel(445, measured=865)]) is None
