import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'modules_src' / 'linkek'))
from linkek_mod import core

def test_url_and_alias():
    assert core.normalize_url('lufisdavid.com') == 'https://lufisdavid.com'
    with pytest.raises(ValueError): core.normalize_url('file:///etc/passwd')
    with pytest.raises(ValueError): core.shorten('https://example.com', 'hibás')

def test_create_sends_exact_parameters_and_validates_response(monkeypatch):
    sent = []
    def post(url, **kwargs):
        sent.append(kwargs)
        return SimpleNamespace(status_code=200, json=lambda: {'shorturl':'https://is.gd/abcde'})
    monkeypatch.setattr(core.requests, 'post', post)
    result = core.shorten('https://example.com/?a=1&b=2', 'abcde', True)
    assert sent[0]['data'] == {'format':'json','url':'https://example.com/?a=1&b=2','shorturl':'abcde','logstats':'1'}
    assert sent[0]['allow_redirects'] is False and result['statistics']
    monkeypatch.setattr(core.requests, 'post', lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: {'shorturl':'https://evil.test/abcde'}))
    with pytest.raises(RuntimeError): core.shorten('https://example.com')

def test_timeout_is_uncertain_and_not_retried(monkeypatch):
    calls = []
    def post(*a, **k):
        calls.append(1); raise core.requests.Timeout()
    monkeypatch.setattr(core.requests, 'post', post)
    with pytest.raises(RuntimeError, match='egyértelmű'): core.shorten('https://example.com')
    assert len(calls) == 1

def test_qr_encoded_and_caption_saved(tmp_path):
    cv2 = pytest.importorskip('cv2')
    target = tmp_path / 'qr.png'
    core.make_qr('lufisdavid.com', 'Ha többet szeretnél rólam megtudni!', target)
    img = cv2.imread(str(target))
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    assert decoded == 'https://lufisdavid.com'

def test_qr_caption_optional(tmp_path):
    target = tmp_path / 'qr.png'
    core.make_qr('https://example.com', '', target)
    assert target.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')

