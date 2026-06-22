"""Hang- vagy írás-vezérelt asszisztens: természetes nyelvű parancsot az AI
értelmez, és a SuperDL megfelelő eszközéhez/akciójához irányít.

Az AI egy JSON-objektumot ad vissza ({action, params, say}) – ez minden
szolgáltatóval működik (nem provider-specifikus function-calling). A tényleges
akciót a GUI hajtja végre (assistantwin), a BIZTONSÁGI alapelv szerint: az
olvasó/lekérdező akciók automatikusan futnak, a kifelé menő/kockázatosak
megerősítéssel.
"""

import json
import re

# akció-kulcs -> (emberi leírás, kockázatos-e [megerősítés kell])
# A kifelé menő / hálózati letöltést indító akciók KOCKÁZATOSAK: ezeket egy
# félrehallott vagy pontatlanul visszaadott parancs ne indíthassa el magától,
# ezért a GUI megerősítést kér rájuk (lásd assistantwin._execute + confirm_text).
ACTIONS = {
    "download":      ("egy URL letöltése (params.url)", True),
    "search":        ("médiakeresés (params.query)", False),
    "radio":         ("internetes rádió megnyitása/keresése (params.query)", False),
    "agenda":        ("a mai/közelgő naptár-események felolvasása", False),
    "subscriptions": ("új epizódok ellenőrzése + letöltése", True),
    "datetime":      ("a pontos dátum és idő bemondása", False),
    "open_tool":     ("egy eszköz megnyitása (params.tool)", False),
    "none":          ("nem érthető kérés", False),
}

# a megnyitható eszközök (open_tool params.tool)
TOOLS = {
    "kereso": "Médiakereső", "media": "Médiakereső",
    "radio": "Internetes rádió",
    "konvertalo": "Médiakonvertáló", "konverter": "Médiakonvertáló",
    "csengohang": "Csengőhang-készítő",
    "videokeszito": "Videókészítő", "videovago": "Videóvágó",
    "hangalamondas": "AI hangalámondás",
    "podcast": "Podcast-felfedező",
    "naptar": "Naptár / szervező", "szervezo": "Naptár / szervező",
    "fajlkuldes": "Fájlküldés (P2P)", "p2p": "Fájlküldés (P2P)",
    "konyvolvaso": "Könyvolvasó", "olvaso": "Könyvolvasó",
    "hirolvaso": "Hírolvasó", "hirek": "Hírolvasó",
}

SYSTEM_PROMPT = (
    "Te a SuperDL nevű, akadálymentes médiaközpont hangasszisztense vagy. A "
    "felhasználó természetes nyelven (magyarul) mond egy parancsot, te pedig "
    "PONTOSAN EGY JSON-objektummal válaszolsz, semmi mással. A JSON mezői:\n"
    '  "action": az alábbiak egyike,\n'
    '  "params": a paraméterek objektuma,\n'
    '  "say": rövid, magyar, felolvasható visszajelzés a felhasználónak.\n\n'
    "Választható action-ök és paramétereik:\n"
    '  "download" {"url": "<a letöltendő hivatkozás>"}\n'
    '  "search" {"query": "<keresőszó>"}\n'
    '  "radio" {"query": "<állomásnév vagy műfaj, lehet üres>"}\n'
    '  "agenda" {}  – a mai/közelgő naptár-események\n'
    '  "subscriptions" {}  – új epizódok ellenőrzése\n'
    '  "datetime" {}  – pontos dátum és idő\n'
    '  "open_tool" {"tool": "<egy eszköz kulcsa>"}\n'
    '  "none" {}  – ha nem érted a kérést\n\n'
    "Az open_tool tool-kulcsai: kereso, radio, konvertalo, csengohang, "
    "videokeszito, videovago, hangalamondas, podcast, naptar, fajlkuldes, "
    "konyvolvaso, hirolvaso.\n"
    "Ha a parancsban URL/hivatkozás van és letöltést kér, használd a "
    "download-ot. Csak a JSON-t add vissza, magyarázat nélkül."
)


def _extract_json(raw: str) -> dict:
    """Az első {...} blokk kinyerése és értelmezése a modell válaszából."""
    if not raw:
        return {"action": "none", "params": {}, "say": "Nem értettem."}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"action": "none", "params": {},
                "say": "Nem értettem a kérést."}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"action": "none", "params": {},
                "say": "Nem értettem a kérést."}
    if not isinstance(data, dict):
        return {"action": "none", "params": {},
                "say": "Nem értettem a kérést."}
    action = data.get("action", "none")
    if action not in ACTIONS:
        action = "none"
    # a params SZIGORÚAN objektum legyen; ha a modell szöveget/listát ad, a
    # későbbi params.get() elszállna – ezért üres dict-re cseréljük
    p = data.get("params")
    say = data.get("say")
    return {"action": action,
            "params": p if isinstance(p, dict) else {},
            "say": say if isinstance(say, str) else ""}


def parse_command(text: str) -> dict:
    """A parancs értelmezése AI-val → {action, params, say}. Hálózati/AI hiba
    esetén none-t ad vissza, érthető üzenettel."""
    from . import aiclient
    try:
        raw = aiclient.chat(text, system=SYSTEM_PROMPT, max_tokens=300)
    except Exception as e:
        return {"action": "none", "params": {},
                "say": f"Az AI nem elérhető: {e}"}
    return _extract_json(raw)


def is_risky(action: str) -> bool:
    return ACTIONS.get(action, ("", False))[1]


def confirm_text(action: str, params: dict) -> str:
    """Felolvasható megerősítő kérdés egy kockázatos akcióhoz (a GUI ezt mutatja
    meg / mondja be, mielőtt végrehajtaná)."""
    params = params or {}
    if action == "download":
        url = (params.get("url") or "").strip() or "(nincs megadva cím)"
        return f"Letöltés indul a következő címről:\n{url}\n\nElindítsam?"
    if action == "subscriptions":
        return ("Ellenőrzöm a feliratkozásokat, és letöltöm az összes új "
                "epizódot.\n\nFolytassam?")
    return "Biztosan végrehajtsam ezt a műveletet?"


# open_tool kulcs -> a fő ablak megnyitó metódusa
TOOL_METHODS = {
    "kereso": "_on_search_window", "media": "_on_search_window",
    "radio": "_on_radio_window",
    "konvertalo": "_on_convert_window", "konverter": "_on_convert_window",
    "csengohang": "_on_ringtone_window",
    "videokeszito": "_on_video_window",
    "videovago": "_on_videoedit_window",
    "hangalamondas": "_on_videodescribe_window",
    "podcast": "_on_podcast_window",
    "naptar": "_on_organizer_window", "szervezo": "_on_organizer_window",
    "fajlkuldes": "_on_p2p_window", "p2p": "_on_p2p_window",
    "konyvolvaso": "_on_reader_window", "olvaso": "_on_reader_window",
    "hirolvaso": "_on_news_window", "hirek": "_on_news_window",
}


def agenda_text(main) -> str:
    """A közelgő naptár-események rövid, felolvasható összefoglalója."""
    org = getattr(main, "_organizer", None)
    if not org:
        return "A naptár nem érhető el."
    try:
        items = org.upcoming(days=7)
    except Exception:
        items = []
    if not items:
        return "Nincs közelgő esemény a következő egy hétben."
    parts = [f"{dt.strftime('%m. %d. %H:%M')} {ev.title}"
             for dt, ev in items[:5]]
    return "A közelgő események: " + "; ".join(parts) + "."


def execute(main, action: str, params: dict, say) -> None:
    """Egy értelmezett akció végrehajtása a fő ablak (main) eszközeivel.
    `say` egy hívható(szöveg) a hangos visszajelzéshez. A GUI-szálon hívandó."""
    params = params or {}
    if action == "download":
        url = (params.get("url") or "").strip()
        if url:
            main._on_add(url=url)
        else:
            say("Nem találtam letölthető hivatkozást a parancsban.")
    elif action == "search":
        q = (params.get("query") or "").strip()
        main._on_search_window()
        win = getattr(main, "_search_win", None)
        if win and q:
            win.search_entry.SetValue(q)
            win._on_search()
    elif action == "radio":
        main._on_radio_window()
        q = (params.get("query") or "").strip()
        win = getattr(main, "_radio_win", None)
        if win and q:
            win.search_entry.SetValue(q)
            win._on_search()
    elif action == "agenda":
        say(agenda_text(main))
    elif action == "subscriptions":
        if hasattr(main, "_check_feeds"):
            main._check_feeds(quiet=False)
    elif action == "datetime":
        import datetime as _dt
        say(_dt.datetime.now().strftime(
            "Ma %Y. %m. %d. van, az idő %H óra %M perc."))
    elif action == "open_tool":
        tool = (params.get("tool") or "").strip().lower()
        method = TOOL_METHODS.get(tool)
        if method and hasattr(main, method):
            getattr(main, method)()
        else:
            say("Ezt az eszközt nem ismerem fel.")
    # "none": csak a say hangzott el
