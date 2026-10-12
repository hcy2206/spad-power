import math
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from spad_power.app import Window


def test_gui_calculation_and_stale_results():
    app = QApplication.instance() or QApplication([])
    window = Window()
    assert len(window.results) == 6
    assert window.results[0]['probe_nw'] is None
    window.uniform.setChecked(True)
    assert not window.results
    assert window.run()
    assert 203.26 < window.results[0]['probe_nw'] < 203.27
    window.inputs['frequency_khz'].setValue(20)
    assert window.output.rowCount() == 0
    assert window.run()
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
    window.save()
    window.inputs['frequency_khz'].setValue(20)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(settings_path), ''))
    window.load()
    assert window.inputs['frequency_khz'].value() == 10
    assert window.uniform.isChecked()
    output_path = tmp_path / 'results.csv'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(output_path), ''))
    window.export()
    content = output_path.read_text(encoding='utf-8-sig')
    assert '203.2616' in content
    assert 'frequency_khz,10.0' in content
    import json
    data = json.loads(settings_path.read_text(encoding='utf-8'))
    assert data['version'] == 4 and data['settings']['measured_unit'] == 'nW'
    data['version'] = 1  # old files stored the pulsed-average density and a separate fixed total OD
    del data['settings']['measured_unit']
    data['channels'][0] = dict(wavelength_nm=375, removed_od=5, fixed_od=5, measured_nw_cm2=865)
    settings_path.write_text(json.dumps(data), encoding='utf-8')
    window.load()
    assert window.channels.columnCount() == 3 and window.channels.item(0, 1).text() == '5'
    assert window.unit_box.currentData() == 'nW/cm2'
    assert abs(window.results[0]['measured_nw_cm2'] - 865 / 0.0024) < 1e-6  # converted to CW
    assert abs(window.results[0]['total_od'] - math.log10(865e3 / window.results[0]['density_avg_pw_cm2'])) < 1e-9
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


def test_common_od_applies_to_all_wavelengths():
    app = QApplication.instance() or QApplication([])
    window = Window()
    window.common_od.setValue(5)
    window.apply_common_od()
    assert not window.results
    assert {window.channels.item(i, 1).text() for i in range(window.channels.rowCount())} == {'5'}
    window.uniform.setChecked(True)
    assert window.run()
    assert 20326 < window.results[0]['probe_nw'] < 20327
    window.add_channel()
    assert window.channels.item(window.channels.rowCount() - 1, 1).text() == '5'
    window.close()


def test_adopt_recommended_fixed_od():
    app = QApplication.instance() or QApplication([])
    window = Window()
    assert window.recommendation is None and window.advice.isHidden()
    for row, value in enumerate(['500', '800']):
        window.channels.item(row, 2).setText(value)
    assert window.run()
    assert window.recommendation is None and not window.advice.isHidden()  # nW readings need the uniform confirmation
    window.uniform.setChecked(True)
    assert window.run()
    od = window.recommendation['recommended_od']
    assert window.recommendation['feasible'] and not window.advice.isHidden()
    window.adopt_recommendation()
    assert window.results and window.channels.item(0, 1).text() == f'{od:g}'
    assert all(0.04 <= r['variable_od'] <= 2 for r in window.results if r['variable_od'] is not None)
    window.close()
