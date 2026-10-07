"""Super Surf: forrásadat, cikkstruktúra, biztonság és hozzáférhető kimenet."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules_src" / "supersurf"))
from supersurf_mod.models import ContentBlock, ReaderContent, ResearchQuery  # noqa: E402
from supersurf_mod.network import FetchError, public_url  # noqa: E402
from supersurf_mod.reader import extract_article  # noqa: E402
from supersurf_mod.service import ResearchService  # noqa: E402
from supersurf_mod.wikipedia import extract_wikipedia  # noqa: E402


ARTICLE = """<html><head><title>Cikk címe | Portál</title></head><body>
<nav><p>Menü és más oldal tartalma.</p></nav><main><article>
<h1>Cikk címe</h1><p>Ez a cikk első hosszú, érdemi bekezdése, amely olvasható.</p>
<div class='advert'><p>Ez a reklám nem kerülhet a tiszta eredménybe.</p></div>
<h2>Háttér</h2><p>Ez a második hosszabb bekezdés érdemi információval.</p>
<ul><li>Első elem</li><li>Második elem</li></ul>
</article></main></body></html>"""


def test_reader_article_structure_and_noise():
    content = extract_article(ARTICLE, "https://example.com/news")
    assert content.title == "Cikk címe"
    assert [(b.kind, b.level) for b in content.blocks] == [
        ("paragraph", 0), ("heading", 2), ("paragraph", 0), ("list", 0)]
    assert "reklám" not in content.plain_text()
    assert "Forrás: https://example.com/news" in content.plain_text()


def test_reader_no_content_is_explicit():
    with pytest.raises(FetchError) as error:
        extract_article("<html><body><nav>menü</nav></body></html>", "https://example.com")
    assert error.value.code == "no_content"


def test_reader_keeps_rich_article_content_and_short_text():
    page = """<html><head><title>Új cikk | Hírportál</title>
    <meta property='article:published_time' content='2026-10-05'></head><body>
    <header><p>Oldalfejléc</p></header><nav><p>Menü</p></nav>
    <main><article><h1>Új cikk</h1><p>Rövid hír.</p><h2>Részletek</h2>
    <p>Az érdemi tartalom itt olvasható.</p>
    <table><caption>Összehasonlítás</caption><tr><th>Év</th><th>Érték</th></tr>
    <tr><td>2026</td><td>42</td></tr></table>
    <figure><img alt='Ábra'><figcaption>Az eredmény ábrája</figcaption></figure>
    <div class='image-caption'>Második képaláírás</div><img alt='Önálló diagram'>
    <dl><dt>Fogalom</dt><dd>Magyarázat</dd></dl>
    <div class='related'><p>Másik cikk ajánlója</p></div>
    </article></main><footer><p>Lábléc</p></footer></body></html>"""
    content = extract_article(page, "https://example.com/news")
    result = content.plain_text()
    assert content.published_at == "2026-10-05"
    assert "Rövid hír." in result
    assert "Év: Érték" in result and "2026: 42" in result
    assert "Az eredmény ábrája" in result
    assert "Második képaláírás" in result and "Önálló diagram" in result
    assert "Fogalom" in result and "Magyarázat" in result
    assert "Menü" not in result and "ajánlója" not in result and "Lábléc" not in result


def test_reader_keeps_short_semantic_article_without_page_chrome():
    page = "<html><body><div>Nem cikk.</div><article><h1>Cím</h1><p>Egy mondat.</p></article></body></html>"
    content = extract_article(page, "https://example.com/brief")
    assert "Egy mondat." in content.plain_text()
    assert "Nem cikk." not in content.plain_text()


def test_blocks_are_escaped_in_semantic_html():
    pytest.importorskip("wx")
    from supersurf_mod.window import render_html, sections_from_content
    content = ReaderContent("Cikk címe", (ContentBlock("heading", "<jelölés>", level=2),))
    html = render_html(content)
    assert "<h1>Cikk címe</h1>" in html
    assert "<h2>&lt;jelölés&gt;</h2>" in html
    assert "default-src 'none'" in html
    assert "<script" not in html
    assert sections_from_content(content) == [("Eredmény", content.plain_text())]


def test_native_sections_follow_heading_order():
    pytest.importorskip("wx")
    from supersurf_mod.window import sections_from_content
    content = ReaderContent("Cikk", (
        ContentBlock("paragraph", "Bevezető."),
        ContentBlock("heading", "Első", level=2),
        ContentBlock("paragraph", "Első fejezet."),
        ContentBlock("heading", "Részlet", level=3),
        ContentBlock("paragraph", "Alfejezet szövege."),
    ))
    assert sections_from_content(content) == [
        ("Összefoglaló", "Bevezető."),
        ("Első", "Első fejezet."),
        ("Alfejezet: Részlet", "Alfejezet szövege."),
    ]


@pytest.mark.skipif(sys.platform != "win32", reason="wx-fókuszpróba Windowson")
def test_source_choice_keeps_focus_while_selection_changes():
    wx = pytest.importorskip("wx")
    from supersurf_mod.window import SuperSurfFrame
    app = wx.GetApp() or wx.App(False)
    frame = SuperSurfFrame(None, type("Core", (), {"voice": None})())
    try:
        frame.Show()
        app.Yield()
        frame.mode.SetFocus()
        frame.mode.SetSelection(1)
        frame._mode_changed(None)
        app.Yield()
        assert frame.FindFocus() is frame.mode
    finally:
        frame.Destroy()


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://localhost/a", "http://127.0.0.1/a",
                                 "http://10.0.0.1/a", "http://[::1]/a", "http://example.com:8080/a"])
def test_local_or_unsupported_urls_blocked(url):
    with pytest.raises(FetchError):
        public_url(url)


class FakeHttp:
    def json(self, url):
        if "/search/page?" in url:
            return {"pages": [{"title": "Budapest"}, {"title": "Budapest története"}]}, url
        if "/w/api.php?" in url:
            return {"parse": {"title": "Budapest", "text": """<div class='mw-parser-output'>
                <p>Magyarország fővárosa.</p><h2>Története</h2><p>Régi történet.</p>
                <table><caption>Adatok</caption><tr><th>Lakosság</th><td>1 600 000</td></tr></table>
                <figure><img alt='Duna-part'><figcaption>A Duna-part látképe</figcaption></figure>
                <div class='thumb'><div class='thumbcaption'>Második fénykép</div></div>
                <h2>Források</h2><ol><li>Első forrás</li></ol>
                </div>"""}}, url
        if "geocoding" in url:
            return {"results": [{"name": "Budapest", "country": "Magyarország",
                                 "latitude": 47.5, "longitude": 19.0}]}, url
        if "open-meteo.com/v1/forecast" in url:
            return {"current": {"temperature_2m": 12, "wind_speed_10m": 6},
                    "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"}}, url
        if "frankfurter" in url:
            return {"date": "2026-10-02", "rates": {"HUF": 390.5}}, url
        if "dictionaryapi" in url:
            return [{"word": "hello", "origin": "greeting", "meanings": [
                {"partOfSpeech": "exclamation", "definitions": [{"definition": "a greeting"}]}]}], url
        raise AssertionError(url)

    def html(self, url):
        return ARTICLE, url


@pytest.mark.parametrize("kind,value", [
    ("wikipedia_search", "Budapest"), ("article_url", "https://example.com/news"),
    ("weather", "Budapest"), ("exchange_rate", "EUR HUF"), ("dictionary", "hello")])
def test_all_modes_return_source_and_readable_content(kind, value):
    result = ResearchService(FakeHttp()).run(ResearchQuery(kind, value))
    assert result.status == "success"
    assert result.source_name and result.source_url
    assert result.content and result.content.plain_text()


def test_wikipedia_returns_full_article_not_just_summary():
    result = ResearchService(FakeHttp()).run(ResearchQuery("wikipedia_search", "Budapest"))
    assert result.status == "success"
    assert [block.text for block in result.content.blocks if block.kind == "heading"] == [
        "Története", "Adatok", "Források"]
    assert "1 600 000" in result.content.plain_text()
    assert "A Duna-part látképe" in result.content.plain_text()
    assert "Második fénykép" in result.content.plain_text()
    assert "Első forrás" in result.content.plain_text()
    assert "rövid összefoglaló" not in " ".join(result.warnings)


def test_wikipedia_removes_edit_controls_but_keeps_short_paragraphs():
    content = extract_wikipedia("<div class='mw-parser-output'><p>Rövid.</p>"
        "<span class='mw-editsection'>[szerkesztés]</span><h2>Fejezet</h2>"
        "<p>Teljes szöveg.</p></div>", "Cikk", "https://hu.wikipedia.org/wiki/Cikk")
    assert "Rövid." in content.plain_text()
    assert "szerkesztés" not in content.plain_text()


def test_invalid_rate_and_cancellation():
    service = ResearchService(FakeHttp())
    assert service.run(ResearchQuery("exchange_rate", "EURO HUF")).error.code == "invalid_input"
    assert service.run(ResearchQuery("weather", "Budapest"), cancelled=lambda: True).status == "cancelled"


def test_dictionary_timeout_uses_exact_fallback_definition():
    class SlowDictionary(FakeHttp):
        def json(self, url):
            if "dictionaryapi.dev" in url:
                raise FetchError("timeout", "A lekérdezés túllépte az időkorlátot.", True)
            if "api.datamuse.com" in url:
                return [{"word": "computer", "defs": ["n\tA programmable electronic device."]}], url
            return super().json(url)

    result = ResearchService(SlowDictionary()).run(ResearchQuery("dictionary", "computer"))
    assert result.status == "success"
    assert result.source_name == "Datamuse"
    assert "A programmable electronic device." in result.content.plain_text()
    assert "tartalék forrásból" in result.warnings[0]


def test_dictionary_fallback_rejects_approximate_word():
    class ApproximateDictionary(FakeHttp):
        def json(self, url):
            if "dictionaryapi.dev" in url:
                raise FetchError("timeout", "Időtúllépés.", True)
            if "api.datamuse.com" in url:
                return [{"word": "computerized", "defs": ["adj\tRelated to computers."]}], url
            return super().json(url)

    result = ResearchService(ApproximateDictionary()).run(ResearchQuery("dictionary", "computer"))
    assert result.status == "empty"
    assert result.error.code == "no_content"
