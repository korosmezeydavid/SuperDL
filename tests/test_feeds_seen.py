# -*- coding: utf-8 -*-
"""feeds: a podcast-feliratkozás „látott" (seen) megőrzése.

Bug (felhasználó, super-dl.com podcast): a hibára futó epizódot a
feliratkozás-figyelő ÚJRA MEG ÚJRA letölti („kikukázza"), mert a `mark_seen`
CSAK sikeres letöltéskor hívódott. Javítás (superdl_gui `_enqueue_episodes`):
az epizódot MÁR INDÍTÁSKOR látottnak jelöljük és MENTJÜK, így hiba esetén sem
próbálja végtelenszer újra. Ez a teszt a megőrzés-mechanizmust ellenőrzi."""
import pytest

feeds = pytest.importorskip("superdl.feeds")
from superdl import store  # noqa: E402


def test_seen_megorzodik_es_kizarja_az_epizodot(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SUBS_FILE", tmp_path / "subs.json")

    fm = feeds.FeedManager()                       # üres (tmp)
    sub = feeds.Subscription(feed_url="http://példa/rss", title="Teszt podcast")
    fm.subs.append(sub)
    ep = feeds.Episode(title="1. epizód", guid="ep-guid-1",
                       url="http://példa/ep1.mp3")

    assert "ep-guid-1" not in sub.seen             # eleinte „új"
    fm.mark_seen(sub, ep)                          # a fix ezt INDÍTÁSKOR teszi
    fm.save()
    assert "ep-guid-1" in sub.seen

    # ÚJRATÖLTÉS: a seen megőrződött → az epizód többé NEM lesz „új" → nem
    # próbálja újra leszedni (nincs feltámadás)
    fm2 = feeds.FeedManager()
    sub2 = fm2.find("http://példa/rss")
    assert sub2 is not None
    assert "ep-guid-1" in sub2.seen


def test_gui_indit_utan_jelol_es_ment():
    """A javítás a helyén van: az _enqueue_episodes MÁR az mgr.add UTÁN, a
    sikeres letöltéstől FÜGGETLENÜL jelöli látottnak és menti a feliratkozást."""
    import inspect
    import superdl_gui
    src = inspect.getsource(superdl_gui.MainFrame._enqueue_episodes)
    assert "self.fm.mark_seen(sub, ep)" in src
    assert "self.fm.save()" in src
    # a MÉDIA-ági jelölés (az utolsó előfordulás) az mgr.add UTÁN van → indításkor,
    # nem csak sikeres letöltésre jelöl látottnak
    assert src.rindex("self.fm.mark_seen(sub, ep)") > src.index("mgr.add(")
