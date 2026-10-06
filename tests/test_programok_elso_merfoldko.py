"""Programajánló: csak pontos, jövőbeli, helyes városú esemény kerül ki."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from modules_src.szervezes.szervezes_mod.programok import (
    ELSO_FORRASOK, feldolgoz_artmozi, feldolgoz_cinemacity, feldolgoz_jegy_helyszin,
    feldolgoz_park, osszegyujt,
    szur_programok,
)


NOW = datetime(2026, 10, 6, 18, 0, tzinfo=ZoneInfo("Europe/Budapest"))
SOURCE = ELSO_FORRASOK[1]


def _page(events):
    import json
    return ('<html><script type="application/ld+json">'
            + json.dumps({"@context": "https://schema.org", "@graph": [
                {"@type": "Place", "name": SOURCE.nev, "event": events}
            ]}, ensure_ascii=False)
            + '</script></html>')


def _event(name="Mély levegő", date="2026-10-12 19:30:00",
           city="Nyíregyháza", url="https://www.jegy.hu/program/mely-levego-194049/1465391",
           status="https://schema.org/EventScheduled"):
    return {"@type": "Event", "name": name, "startDate": date,
            "eventStatus": status, "url": url,
            "location": {"@type": "Place", "name": "Krúdy Kamaraszínpad",
                         "address": {"addressLocality": city}}}


def test_two_city_sources_are_distinct():
    assert {source.varos for source in ELSO_FORRASOK} == {"Budapest", "Nyíregyháza"}
    assert {source.fajta for source in ELSO_FORRASOK} == {"jegy", "park", "artmozi", "cinemacity"}


def test_scheduled_event_has_spoken_date_city_and_venue():
    result = feldolgoz_jegy_helyszin(_page([_event()]), SOURCE, NOW)
    assert len(result) == 1
    assert result[0].kezdet.tzinfo is not None
    assert "2026. 10. 12. 19:30" in result[0].felolvasas()
    assert "Nyíregyháza, Krúdy Kamaraszínpad" in result[0].felolvasas()


def test_no_past_cancelled_other_city_or_untrusted_links():
    events = [
        _event(date="2026-10-05 19:30:00"),
        _event(status="https://schema.org/EventCancelled"),
        _event(city="Budapest"),
        _event(url="javascript:alert(1)"),
        _event(date="2026-10-12"),
    ]
    assert feldolgoz_jegy_helyszin(_page(events), SOURCE, NOW) == []


def test_repeated_performances_remain_separate_but_duplicates_do_not():
    a = _event()
    b = _event(date="2026-10-13 19:30:00")
    result = feldolgoz_jegy_helyszin(_page([b, a, a]), SOURCE, NOW)
    assert len(result) == 2
    assert result[0].kezdet < result[1].kezdet


def test_missing_structured_events_is_a_clear_source_failure():
    with pytest.raises(ValueError, match="nincs strukturált"):
        feldolgoz_jegy_helyszin("<html><p>Nincs adat</p></html>", SOURCE, NOW)


def test_naive_reference_time_is_rejected():
    with pytest.raises(ValueError, match="időzónát"):
        feldolgoz_jegy_helyszin(_page([_event()]), SOURCE, datetime(2026, 10, 6))


def test_budapest_park_calendar_and_date_city_filters():
    import html
    import json

    park = ELSO_FORRASOK[2]
    days = [{"number": 20261010, "events": [
        {"title": "Este a Parkban", "time": "19:00", "is_cancelled": False,
         "frontend_url": "https://www.budapestpark.hu/events/este-20261010"},
        {"title": "Elmarad", "time": "20:00", "is_cancelled": True,
         "frontend_url": "https://www.budapestpark.hu/events/elmarad"},
    ]}, {"number": 20261011, "events": [
        {"title": "Vasárnapi koncert", "time": "18:00",
         "frontend_url": "https://www.budapestpark.hu/events/vasarnap"},
        {"title": "Idő nélkül", "time": "", "frontend_url": "https://www.budapestpark.hu/events/idonelkul"},
        {"title": "Külső link", "time": "20:00", "frontend_url": "https://evil.example/event"},
    ]}]
    page = '<div data-days="' + html.escape(json.dumps(days), quote=True) + '"></div>'
    result = feldolgoz_park(page, park, NOW)
    assert [p.cim for p in result] == ["Este a Parkban", "Vasárnapi koncert"]
    assert [p.cim for p in szur_programok(result, varos="BUDAPEST",
                                           ettol=date(2026, 10, 11))] == ["Vasárnapi koncert"]
    assert szur_programok(result, varos="Nyíregyháza") == []


def test_bad_calendar_and_reversed_dates_report_error():
    with pytest.raises(ValueError, match="naptáradat"):
        feldolgoz_park("<html></html>", ELSO_FORRASOK[2], NOW)
    with pytest.raises(ValueError, match="kezdő dátum"):
        szur_programok([], ettol=date(2026, 10, 12), eddig=date(2026, 10, 10))


def test_one_source_failure_keeps_other_city_and_reports_which_failed():
    valid = feldolgoz_jegy_helyszin(_page([_event()]), SOURCE, NOW)

    def fetch(source, now):
        if source is ELSO_FORRASOK[0]:
            raise OSError("időtúllépés")
        return valid if source is SOURCE else []

    collection = osszegyujt(ELSO_FORRASOK, NOW, fetch)
    assert len(collection.programok) == 1
    assert collection.programok[0].varos == "Nyíregyháza"
    assert collection.hibak == (("Müpa", "időtúllépés"),)


def test_artmozi_screenings_are_separate_dated_cinema_results():
    source = next(item for item in ELSO_FORRASOK if item.fajta == "artmozi")
    movies = {"42": {"title": "Próbafilm"}}
    cinemas = {"1450": {"name": "Művész Mozi"}}
    data = {"movies": movies, "schedule": {"20261012": {"42": {
        "18:00": {"a": {"cinema": 1450, "cinema_room": "Bódy terem",
                        "link": "https://muvesz.bpfilm.hu/tid.asp?id=1"}},
        "20:00": {"b": {"cinema": 1450, "cinema_room": "Bódy terem",
                        "link": "https://muvesz.bpfilm.hu/tid.asp?id=2"},
                  "unsafe": {"cinema": 1450, "link": "https://evil.example/film"}},
    }}}}
    found = feldolgoz_artmozi(data, cinemas, source, NOW)
    assert len(found) == 2
    assert all(item.mufaj == "Mozi" for item in found)
    assert all(item.varos == "Budapest" for item in found)
    assert "Művész Mozi – Bódy terem" in found[0].felolvasas()
    assert [item.kezdet.hour for item in found] == [18, 20]
    assert len(szur_programok(found, mufaj="Mozi", kereses="próbafilm")) == 2


def test_cinemacity_vetitesek_konkretek_es_biztonsagos_hivatkozasuak():
    source = next(item for item in ELSO_FORRASOK if item.nev == "Cinema City Nyíregyháza")
    base = {"id": "100", "filmId": "film1", "cinemaId": "1143",
            "eventDateTime": "2026-10-12T19:15:00", "auditorium": "3. terem",
            "bookingRouterLaunchLink": "https://www.cinemacity.hu/hu/booking-router/launch/1143/100?lang=hu"}
    invalid = dict(base, id="101", bookingRouterLaunchLink="https://evil.example/")
    other_cinema = dict(base, id="102", cinemaId="1132")
    data = {"body": {"films": [{"id": "film1", "name": "Űrkaland"}],
                     "events": [base, base, invalid, other_cinema]}}
    found = feldolgoz_cinemacity(data, source, NOW)
    assert len(found) == 1
    assert found[0].mufaj == "Mozi"
    assert found[0].varos == "Nyíregyháza"
    assert "Cinema City Nyíregyháza – 3. terem" in found[0].felolvasas()
