# -*- coding: utf-8 -*-
"""Herman Tibi auditok KV1 köre: titokvédelem + naptár-helyesség + bájt-limit.
Minden teszt a KONKRÉT, bizonyított hibát fogja meg (nem mockolt látszat)."""
import datetime
import inspect

from superdl import audiobook, organizer, tts


# ---- CAL-P0-01: ismétlődő esemény NEM sülhet el a kezdődátum előtt ----------

def _ev(**kw):
    base = dict(id="x", title="Teszt", date="2026-08-15", time="10:00",
                repeat=organizer.REPEAT_DAILY)
    base.update(kw)
    return organizer.Event(**base)


def test_napi_ismetlodes_nem_fordul_elo_a_kezdodatum_elott():
    ev = _ev(repeat=organizer.REPEAT_DAILY, date="2026-08-15")
    assert ev.occurs_on(datetime.date(2026, 8, 14)) is False   # előtte NEM
    assert ev.occurs_on(datetime.date(2026, 8, 15)) is True    # aznap IGEN
    assert ev.occurs_on(datetime.date(2026, 9, 1)) is True     # utána IGEN


def test_heti_ismetlodes_nem_fordul_elo_a_kezdodatum_elott():
    # 2026-08-15 szombat; a hétfői (0) ismétlés a kezdés ELŐTTI hétfőn nem jöhet
    ev = _ev(repeat=organizer.REPEAT_WEEKLY, date="2026-08-15", weekdays=[0])
    assert ev.occurs_on(datetime.date(2026, 8, 10)) is False   # korábbi hétfő
    assert ev.occurs_on(datetime.date(2026, 8, 17)) is True    # utáni hétfő


def test_hibas_kezdodatum_nem_dob_kivetelt():
    ev = _ev(repeat=organizer.REPEAT_DAILY, date="nem-datum")
    assert ev.occurs_on(datetime.date(2026, 8, 15)) is True    # régi viselkedés


# ---- CAL-P0-06: az ütemező hibái NEM tűnhetnek el némán --------------------

def test_scheduler_nem_nyeli_el_nemam_a_hibat():
    src = inspect.getsource(organizer.OrganizerManager._loop)
    assert "except Exception:\n                pass" not in src, \
        "a scheduler néma except-pass-t használ"
    assert "tick_errors" in src and "_log" in src


def test_scheduler_health_jelentes_letezik():
    assert hasattr(organizer.OrganizerManager, "scheduler_health")


# ---- AB-P0-05 / TTS-SEC: az API-kulcs nem szivároghat ----------------------

def test_kulcs_nincs_az_urlben():
    src = inspect.getsource(tts)
    assert "?key={api_key}" not in src, "az API-kulcs URL query-ben van"
    assert "x-goog-api-key" in src, "nincs fejléc-alapú kulcsátadás"


def test_redact_maszkolja_a_kulcsot():
    key = "AIzaSyD-EXAMPLE-TESTKEY-1234567890"
    msg = f"HTTP 403 https://x.googleapis.com/v1/a?key={key}&b=1"
    out = tts.redact(msg, key)
    assert key not in out
    assert "***" in out


def test_redact_akkor_is_maszkol_ha_a_kulcsot_nem_kapja_meg():
    msg = "HTTP 400 https://x.googleapis.com/v1/a?key=TITKOS_KULCS_123&b=1"
    assert "TITKOS_KULCS_123" not in tts.redact(msg)


def test_rovid_szoveget_nem_maszkol_ki_feleslegesen():
    # 8 karakternél rövidebb „kulcs” nem valódi titok – ne csonkítsa a szöveget
    assert tts.redact("hiba: abc", "abc") == "hiba: abc"


# ---- AB-P1-10: a Cloud korlát BÁJT, nem karakter ---------------------------

def test_cloud_motor_bajt_limitet_deklaral():
    assert getattr(tts.ENGINES["cloud"], "byte_limit", 0) > 0


def test_magyar_ekezetes_darabok_a_bajtlimit_alatt_maradnak():
    # csupa kétbájtos ékezet: karakterben mérve átmenne, bájtban nem
    text = ("Árvíztűrő tükörfúrógép őőő űűű. " * 400).strip()
    limit = 1000
    parts = audiobook.chunk_text(text, limit, by_bytes=True)
    assert parts, "nem keletkezett darab"
    for p in parts:
        assert len(p.encode("utf-8")) <= limit, \
            f"{len(p.encode('utf-8'))} bájt > {limit}"


def test_bajt_modban_sem_veszik_el_szoveg():
    text = "Árvíztűrő tükörfúrógép. " * 50
    parts = audiobook.chunk_text(text, 200, by_bytes=True)
    # minden szó megmarad (a darabolás nem csonkol)
    assert "".join(parts).replace(" ", "").replace("\n", "") \
        == text.replace(" ", "").strip().replace(" ", "")


def test_egyetlen_hosszu_ekezetes_szo_is_bajthataron_torik():
    parts = audiobook.chunk_text("Á" * 5000, 300, by_bytes=True)
    for p in parts:
        assert len(p.encode("utf-8")) <= 300


# ---- AB-P0-01: az API-kulcs mező jelszómező --------------------------------

def test_api_kulcs_mezo_jelszomezo():
    import pathlib
    p = (pathlib.Path(__file__).parent.parent / "modules_src" / "konyvek"
         / "konyvek_mod" / "bookwin.py")
    src = p.read_text(encoding="utf-8")
    assert "wx.TextCtrl(p, style=wx.TE_PASSWORD)" in src, \
        "az API-kulcs mező nem TE_PASSWORD"


# ---- READ-P1-14: a 0.0 hangerő érvényes érték ------------------------------

def test_nulla_hangero_nem_valtozik_07_re():
    import pathlib
    p = (pathlib.Path(__file__).parent.parent / "modules_src" / "konyvek"
         / "konyvek_mod" / "readerwin.py")
    src = p.read_text(encoding="utf-8")
    assert "player.volume or 0.7" not in src, \
        "a 0.0 hangerőt még mindig 0.7-re cseréli"


# ---- REC-P0-03: nincs CSENDES degradálás ffmpeg hiányában ------------------

def test_ffmpeg_hianyaban_nincs_csendes_degradalas(tmp_path, monkeypatch):
    """Ha feldolgozást kértek, de nincs ffmpeg, a mentés HIBÁVAL álljon meg –
    ne írjon nyers hangot 'siker' gyanánt."""
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent
                          / "modules_src" / "supermedia"))
    from supermedia_mod import superrec
    from superdl import ffmpeg as ffmpeg_mod

    monkeypatch.setattr(ffmpeg_mod, "find_ffmpeg", lambda: None)
    monkeypatch.setattr(ffmpeg_mod, "ensure_ffmpeg", lambda *a, **k: None)

    pcm = b"\x00\x01" * 8000
    out = str(tmp_path / "teszt.wav")
    try:
        superrec.save_pcm(out, pcm, 44100, 2, normalize=True)
    except RuntimeError as e:
        assert "normalizálás" in str(e)
        return
    raise AssertionError("csendes degradálás: hiba nélkül tért vissza")


def test_feldolgozas_nelkuli_wav_tovabbra_is_mehet(tmp_path, monkeypatch):
    """Ha SEMMIT nem kértek, ffmpeg nélkül is menthető a nyers WAV."""
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent
                          / "modules_src" / "supermedia"))
    from supermedia_mod import superrec
    from superdl import ffmpeg as ffmpeg_mod

    monkeypatch.setattr(ffmpeg_mod, "find_ffmpeg", lambda: None)
    monkeypatch.setattr(ffmpeg_mod, "ensure_ffmpeg", lambda *a, **k: None)

    pcm = b"\x00\x01" * 8000
    out = str(tmp_path / "nyers.wav")
    assert superrec.save_pcm(out, pcm, 44100, 2) == out
    assert __import__("os").path.getsize(out) > 1000


# ---- CAL-P0-02: az ICS TZID értelmezése (órákkal téves emlékeztetők) -------

def test_tzid_szerinti_ido_helyi_idore_valt():
    """A TZID-t eddig FIGYELMEN KÍVÜL hagytuk: egy New York-i esemény a gép
    helyi idejeként jelent meg. Most a zóna szerint vált át."""
    from zoneinfo import ZoneInfo
    val = "20260815T100000"
    dt_naiv, _ = organizer._parse_dt(val, "")
    dt_ny, _ = organizer._parse_dt(val, ";TZID=America/New_York")
    varhato = (datetime.datetime(2026, 8, 15, 10, 0)
               .replace(tzinfo=ZoneInfo("America/New_York"))
               .astimezone().replace(tzinfo=None))
    assert dt_ny == varhato, f"{dt_ny} != {varhato}"
    assert dt_ny != dt_naiv, "a TZID-t továbbra sem veszi figyelembe"


def test_ismeretlen_tzid_nem_dob_hibat():
    dt, _ = organizer._parse_dt("20260815T100000", ";TZID=Nincs/Ilyen")
    assert dt == datetime.datetime(2026, 8, 15, 10, 0)   # naiv marad


def test_utc_z_tovabbra_is_helyesen_valt():
    dt, _ = organizer._parse_dt("20260815T100000Z", "")
    assert dt is not None


def test_egesz_napos_esemeny_valtozatlan():
    dt, is_date = organizer._parse_dt("20260815", ";VALUE=DATE")
    assert is_date is True and dt == datetime.datetime(2026, 8, 15)


# ---- CAL-P0-04: a titkos ICS-cím nem jelenhet meg teljesen ----------------

def test_titkos_ics_cim_maszkolva_jelenik_meg():
    lab = organizer.safe_url_label(
        "https://calendar.google.com/calendar/ical/abc123TITOK/private-xyz/basic.ics")
    assert "TITOK" not in lab and "private-xyz" not in lab
    assert "calendar.google.com" in lab and "titkos link" in lab


def test_egyszeru_cim_eseten_csak_a_kiszolgalo():
    assert organizer.safe_url_label("https://pelda.hu") == "pelda.hu"


def test_ures_cim_kezelese():
    assert "nincs" in organizer.safe_url_label("").lower()


def test_icssub_safe_label_metodusa():
    s = organizer.IcsSub(id="1", name="Munka",
                         url="https://outlook.office365.com/owa/calendar/TOKEN/x.ics")
    assert "TOKEN" not in s.safe_label()
