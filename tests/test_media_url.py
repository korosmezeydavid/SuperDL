"""media.py: egy-videós URL-felismerés (rádió/mix-védelem) + emberi hibaüzenetek.
A 3.29.7-es „mindent lekapkod egy mappába" bug regressziós tesztjei."""

import pytest

media = pytest.importorskip("superdl.media")


@pytest.mark.parametrize("url,want", [
    # a bejelentett rádió/mix link: konkrét videó → CSAK azt
    ("https://www.youtube.com/watch?v=HCfH6DAA3hM&list=RDHCfH6DAA3hM"
     "&start_radio=1", True),
    ("https://www.youtube.com/watch?v=HCfH6DAA3hM", True),
    ("https://youtu.be/HCfH6DAA3hM?list=RDHCfH6DAA3hM", True),
    ("https://youtu.be/HCfH6DAA3hM", True),
    # videó + valódi lejátszási lista → akkor is a videó
    ("https://www.youtube.com/watch?v=abc&list=PLvalodiLista123", True),
    # TISZTA lista-URL → szándékosan az egész lista
    ("https://www.youtube.com/playlist?list=PLvalodiLista123", False),
    ("https://www.youtube.com/@valaki/videos", False),
    ("https://soundcloud.com/eloado/szam", False),
    ("nem-url", False),
])
def test_prefers_single_video(url, want):
    assert media._prefers_single_video(url) is want


@pytest.mark.parametrize("msg,kulcsszo", [
    ("Sign in to confirm your age. This video may be inappropriate.",
     "KORHATÁROS"),
    ("Sign in to confirm you're not a bot.", "nem robot"),
    ("Private video. Sign in if you've been granted access", "PRIVÁT"),
    ("Join this channel to get access to members-only content", "TAGSÁGHOZ"),
    ("This video is available to Music Premium members", "TAGSÁGHOZ"),
    ("The uploader has not made this video available in your country",
     "régiózár"),
    ("Video unavailable. This video has been removed by the uploader",
     "NEM ÉRHETŐ EL"),
    ("Premieres in 3 hours", "premier"),
    ("Requested format is not available", "formátum"),
    ("ffmpeg is not installed", "ffmpeg"),
    ("unable to download video data: HTTP Error 403: Forbidden", "403"),
    ("HTTP Error 429: Too Many Requests", "KORLÁTOZ"),
    ("<urlopen error [Errno 11001] getaddrinfo failed>", "HÁLÓZATI"),
    ("[Errno 28] No space left on device", "ELFOGYOTT A HELY"),
    ("[Errno 13] Permission denied: 'D:/x.mp4'", "NEM LEHET ÍRNI"),
    ("Unsupported URL: https://example.com/x", "NEM TÁMOGATJA"),
])
def test_friendly_error_kategoriak(msg, kulcsszo):
    assert kulcsszo.lower() in media.friendly_error(msg).lower()


def test_friendly_error_ismeretlen_valtozatlan():
    assert media.friendly_error("egyedi ismeretlen hiba") == \
        "egyedi ismeretlen hiba"


def test_korhatar_a_bot_ellenorzes_elott():
    """A „Sign in to confirm your age” a bot-mintára is illik — a korhatáros
    üzenetnek kell nyernie (3.29.8-ban javított sorrend)."""
    out = media.friendly_error("ERROR: Sign in to confirm your age.")
    assert "KORHATÁROS" in out
    assert "robot" not in out


def test_bot_check_uzenet_teljes_tanacssor():
    """A bot-ellenőrzés üzenete a Maxinak megígért teljes tanácssort adja:
    IP-magyarázat, hotspot-gyorsteszt, router/VPN, várakozás, privát ablakos
    cookies.txt-recept (3.29.9)."""
    out = media.friendly_error("Sign in to confirm you're not a bot")
    for kulcsszo in ("IP-címet", "hotspot", "routert", "VPN",
                     "PRIVÁT", "cookies.txt", "ZÁRD BE"):
        assert kulcsszo in out, f"hiányzik a tanácsból: {kulcsszo}"
