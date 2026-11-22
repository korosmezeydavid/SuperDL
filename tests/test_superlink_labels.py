from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'modules_src' / 'linkek'))
from linkek_mod import core as C

@pytest.mark.parametrize('text', ['só', 'bors', 'vegeta', 'árvíztűrő tükörfúrógép'])
def test_label_qr_is_plain_text_and_offline(text, tmp_path, monkeypatch):
    cv2 = pytest.importorskip('cv2')
    monkeypatch.setattr(C.requests, 'post', lambda *a, **k: pytest.fail('network request'))
    path = tmp_path / 'label.png'
    C.make_label(text, path)
    value, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(path)))
    assert value == text


def test_label_persistence_and_invalid_contents(tmp_path, monkeypatch):
    monkeypatch.setattr(C.store, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(C, 'LABELS_DATA', tmp_path/'labels.json')
    assert C.load_labels() == []
    C.save_labels(['só', 'bors', 'vegeta'])
    assert C.load_labels() == ['só', 'bors', 'vegeta']
    C.save_labels(['só', 'bors, őrölt'])
    assert C.load_labels() == ['só', 'bors, őrölt']
    with pytest.raises(ValueError): C.save_labels([''])
    C.LABELS_DATA.write_text('{bad', encoding='utf-8')
    with pytest.raises(ValueError): C.load_labels()
    assert C.LABELS_DATA.read_text(encoding='utf-8') == '{bad'


def test_existing_qr_still_encodes_web_address(tmp_path):
    cv2 = pytest.importorskip('cv2')
    path = tmp_path/'link.png'; C.make_qr('lufisdavid.com', 'Cím', path)
    value, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(path)))
    assert value == 'https://lufisdavid.com'


def test_png_stores_print_size_and_keeps_qr_square(tmp_path):
    cv2 = pytest.importorskip('cv2')
    from PIL import Image
    path = tmp_path / 'cedula.png'
    C.make_label('só', path, '3,5', 4)
    value, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(path)))
    assert value == 'só'
    image = Image.open(path)
    assert image.size[0] / image.size[1] == pytest.approx(3.5 / 4)
    assert image.info['dpi'][0] == pytest.approx(image.width * 2.54 / 3.5, rel=0.02)
    assert image.info['dpi'][1] == pytest.approx(image.height * 2.54 / 4, rel=0.02)
    assert C.size_sentence(3, 3.5) == 'Nyomtatáskor 3 centiméter széles és 3,5 centiméter magas.'
    assert C.label_origin_mm(210, 297, 3, 3) == (90, 133.5)
    with pytest.raises(ValueError, match='nem fér el'):
        C.label_origin_mm(210, 297, 20, 3)
    with pytest.raises(ValueError, match='2 és 20'):
        C.print_centimeters('1')


def test_label_dialog_can_add_edit_and_delete(monkeypatch, tmp_path):
    wx = pytest.importorskip('wx')
    from linkek_mod.window import LabelDialog
    monkeypatch.setattr(C.store, 'CONFIG_DIR', tmp_path)
    monkeypatch.setattr(C, 'LABELS_DATA', tmp_path/'labels.json')
    monkeypatch.setattr(wx, 'MessageBox', lambda *args, **kwargs: wx.YES)
    app=wx.App.Get() or wx.App(False); parent=wx.Frame(None); dlg=LabelDialog(parent)
    try:
        assert dlg.text.GetName() == 'Tárgy neve vagy címke szövege'
        assert dlg.width.GetName() == 'Cédula szélessége centiméterben'
        assert dlg.height.GetValue() == '3'
        names = [child.GetName() for child in dlg.GetChildren()[0].GetChildren()]
        assert 'A tárgycédula közvetlen nyomtatása a megadott méretben' in names
        dlg.text.SetValue('só')
        dlg.width.SetValue('1')
        notes = []
        monkeypatch.setattr(wx, 'MessageBox', lambda *args, **kwargs: notes.append(args[0]) or wx.OK)
        monkeypatch.setattr(wx, 'Printer', lambda *args: pytest.fail('Hibás méretnél nincs nyomtatás'))
        dlg.on_print(None)
        assert any('2 és 20' in note for note in notes)
        dlg.width.SetValue('3')
        monkeypatch.setattr(wx, 'MessageBox', lambda *args, **kwargs: wx.YES)
        dlg.text.SetValue('só'); dlg.on_add(None)
        dlg.text.SetValue('bors'); dlg.on_add(None)
        assert C.load_labels() == ['só', 'bors']
        dlg.text.SetValue('őrölt bors'); dlg.on_update(None)
        assert C.load_labels() == ['só', 'őrölt bors']
        dlg.on_delete(None)
        assert C.load_labels() == ['só']
    finally:
        dlg.Destroy(); parent.Destroy()

