import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from spad_power.app import Window
from spad_power.model import Settings

# CW power-meter reading (nW, 9.5 mm probe) that gives 0.1 photons per pulse at 375 nm with OD 3.
CW_375_NW = 286.7597980495864 * Settings().probe_area_cm2


def fill_375(window, light='500', dark='100'):
    window.channels.item(0, 2).setText(repr(CW_375_NW))
    window.channels.item(0, 3).setText(light)
    window.channels.item(0, 4).setText(dark)


def test_gui_calculation_and_stale_results():
    app = QApplication.instance() or QApplication([])
    window = Window()
    assert len(window.results) == 6 and window.results[0]['photons'] is None
    fill_375(window)
    assert not window.results
    assert window.run()
    assert window.results[0]['photons'] is None and '无法换算' in window.results[0]['status']  # nW needs the confirmation
    window.uniform.setChecked(True)
    assert window.output.rowCount() == 0
    assert window.run()
    assert abs(window.results[0]['photons'] - 0.1) < 1e-12
    assert 41.24 < window.results[0]['pde_percent'] < 41.25
    assert not window.verdict.isHidden() and '通过' in window.verdict.text()
    window.show()
    app.processEvents()
    window.close()


def test_save_load_export(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    app = QApplication.instance() or QApplication([])
    window = Window()
    settings_path = tmp_path / 'settings.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(settings_path), ''))
    window.uniform.setChecked(True)
    fill_375(window)
    window.save()
    window.inputs['frequency_khz'].setValue(20)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(settings_path), ''))
    window.load()
    assert window.inputs['frequency_khz'].value() == 10 and window.uniform.isChecked()
    assert window.channels.item(0, 3).text() == '500.0' and 41.24 < window.results[0]['pde_percent'] < 41.25
    output_path = tmp_path / 'results.csv'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(output_path), ''))
    window.export()
    content = output_path.read_text(encoding='utf-8-sig')
    assert '41.2429' in content and 'frequency_khz,10.0' in content and '指标1_各波长PDE>7%,通过' in content
    data = json.loads(settings_path.read_text(encoding='utf-8'))
    assert data['version'] == 6 and data['channels'][0]['od'] == 3
    # Old files: v1 stored the pulsed-average density, a target photon number and a separate fixed total OD.
    data['version'] = 1
    data['settings'].update(photons=0.1, variable_min=0.04, variable_max=2, probe_min_nw=0.5)
    del data['settings']['measured_unit']
    data['channels'][0] = dict(wavelength_nm=375, removed_od=5, fixed_od=5, measured_nw_cm2=865)
    settings_path.write_text(json.dumps(data), encoding='utf-8')
    window.load()
    assert window.channels.columnCount() == 5 and window.channels.item(0, 1).text() == '5'
    assert window.unit_box.currentData() == 'nW/cm2'
    assert abs(window.results[0]['measured_nw_cm2'] - 865 / 0.0024) < 1e-6  # converted to CW
    assert abs(window.results[0]['density_avg_pw_cm2'] - 865e3 * 1e-5) < 1e-9  # back to the pulsed average, OD 5
    window.close()


def test_secondary_items_folded_by_default():
    from spad_power.app import DISPLAY_ORDER, MINOR_COLUMNS
    app = QApplication.instance() or QApplication([])
    window = Window()
    hidden = {key for col, key in enumerate(DISPLAY_ORDER) if window.output.isColumnHidden(col)}
    assert hidden == MINOR_COLUMNS
    assert not window.advanced.is_expanded() and not window.model_help.is_expanded()
    window.show_minor.setChecked(True)
    assert not any(window.output.isColumnHidden(col) for col in range(len(DISPLAY_ORDER)))
    window.close()


def test_common_od_and_dark_apply_to_all_wavelengths():
    app = QApplication.instance() or QApplication([])
    window = Window()
    window.uniform.setChecked(True)
    fill_375(window, dark='')
    window.common_od.setValue(5)
    window.apply_common_od()
    window.common_dark.setValue(100)
    window.apply_common_dark()
    assert not window.results
    rows = range(window.channels.rowCount())
    assert {window.channels.item(i, 1).text() for i in rows} == {'5'}
    assert {window.channels.item(i, 4).text() for i in rows} == {'100'}
    assert window.run()
    assert abs(window.results[0]['photons'] - 0.001) < 1e-14
    window.add_channel()
    assert window.channels.item(window.channels.rowCount() - 1, 1).text() == '5'
    window.close()


def test_pde_chart_follows_results():
    from spad_power.app import DISPLAY_ORDER
    app = QApplication.instance() or QApplication([])
    window = Window()
    assert 'status' not in DISPLAY_ORDER and window.chart.points == []
    window.uniform.setChecked(True)
    fill_375(window)
    assert window.run()
    assert len(window.chart.points) == 1 and abs(window.chart.points[0][1] - window.results[0]['pde_percent']) < 1e-12
    window.inputs['pulse_ns'].setValue(480)
    assert window.chart.points == []
    window.show()
    app.processEvents()
    window.close()
