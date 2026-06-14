"""Súgó az AI API-kulcsok beszerzéséhez – pontos linkek, lépések, ingyenes
keret és gazdaságosság mind a négy szolgáltatóra.

Akadálymentes: a teljes leírás egy csak olvasható, nyilakkal bejárható
szövegmezőben; alul gombok, amelyek a böngészőben megnyitják az adott
szolgáltató kulcs-oldalát.
"""

import webbrowser

import wx

KEY_PAGES = [
    ("&Google Gemini megnyitása", "https://aistudio.google.com/app/apikey"),
    ("&OpenAI megnyitása", "https://platform.openai.com/api-keys"),
    ("&Anthropic megnyitása", "https://console.anthropic.com/settings/keys"),
    ("&xAI megnyitása", "https://console.x.ai/"),
]

HELP_TEXT = """AI API-kulcsok beszerzése

Mind a négy szolgáltatóhoz külön, ingyenes regisztrációval létrehozható fiók \
és egy saját API-kulcs kell. A kulcsot a Beállítások → AI fülön illeszd be. \
A kulcs olyan, mint egy jelszó: ne oszd meg senkivel, ne tedd közzé.

──────────────────────────────────────────────
1) GOOGLE GEMINI — a legkönnyebb és ingyenes kezdés
   Oldal: https://aistudio.google.com/app/apikey
   Lépések: jelentkezz be a Google-fiókoddal, majd kattints a „Create API \
key” (API-kulcs létrehozása) gombra, és másold ki a kulcsot.
   Ingyen: VAN valódi ingyenes keret (napi és perces korláttal), általában \
bankkártya megadása nélkül is. Tud szöveget, képet, hangot és videót is.
   Gazdaságosság: kezdésre és tesztelésre ez a legjobb — sokszor teljesen \
ingyen elég. Erősen ajánlott első kulcsnak.

──────────────────────────────────────────────
2) OPENAI (GPT és Whisper)
   Oldal: https://platform.openai.com/api-keys
   Lépések: regisztrálj vagy lépj be, majd „Create new secret key”, és \
másold ki a kulcsot (csak egyszer látható, mentsd el!).
   Ingyen: az API általában FIZETŐS, használat alapú; egy kis egyenleget \
fel kell tölteni (Billing menü). Új fióknak néha van kevés próbakeret, de \
ez nem garantált.
   Gazdaságosság: a „gpt-4o-mini” modell nagyon olcsó képhez és szöveghez; \
a Whisper hang-átirat is olcsó (nagyjából néhány forint percenként). Jó \
ár-érték, megbízható.

──────────────────────────────────────────────
3) ANTHROPIC (Claude)
   Oldal: https://console.anthropic.com/settings/keys
   Lépések: regisztrálj vagy lépj be, majd „Create Key”, és másold ki.
   Ingyen: FIZETŐS, használat alapú; egyenleget kell vásárolni. Hosszú \
dokumentumokhoz, összefoglaláshoz, kérdezéshez kiváló.
   Gazdaságosság: a kisebb „Haiku” modell olcsó és gyors; a „Sonnet” \
közepes árú és nagyon okos; az „Opus” a legdrágább, de a legerősebb.

──────────────────────────────────────────────
4) xAI (Grok)
   Oldal: https://console.x.ai/  (API Keys → „Create API Key”)
   Lépések: lépj be az xAI / X-fiókoddal, nyisd meg az API Keys részt, és \
hozz létre egy kulcsot.
   Ingyen: FIZETŐS, használat alapú; időnként ad promóciós kreditet. Tud \
szöveget és képet.
   Gazdaságosság: a többi fizetős szolgáltatóhoz hasonló nagyságrend.

──────────────────────────────────────────────
RÖVID ÖSSZEGZÉS — melyiket válaszd?
 • Ingyen, bankkártya nélkül indulnál → GEMINI.
 • Olcsó, megbízható fizetős → OPENAI (gpt-4o-mini, Whisper).
 • Hosszú szöveg, dokumentum-összefoglalás → ANTHROPIC (Claude).
 • Ha már van xAI/Grok hozzáférésed → xAI.

A program a beállított „alapértelmezett szolgáltatót” használja a képhez és \
a szöveghez; a hang-átirathoz viszont automatikusan az OpenAI-t vagy a \
Gemini-t választja, mert hangot csak ez a kettő dolgoz fel.

FIGYELEM: az árak és az ingyenes keretek bármikor változhatnak — a pontos, \
aktuális feltételeket mindig a szolgáltató saját oldalán ellenőrizd."""


class AIKeysHelpDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="AI-kulcsok beszerzése",
                         size=(720, 600))
        v = wx.BoxSizer(wx.VERTICAL)
        txt = wx.TextCtrl(self, value=HELP_TEXT,
                          style=wx.TE_MULTILINE | wx.TE_READONLY |
                          wx.TE_BESTWRAP)
        txt.SetName("AI-kulcsok beszerzése – leírás")
        v.Add(txt, 1, wx.EXPAND | wx.ALL, 8)

        grid = wx.WrapSizer(wx.HORIZONTAL)
        for label, url in KEY_PAGES:
            b = wx.Button(self, label=label)
            b.Bind(wx.EVT_BUTTON, lambda e, u=url: webbrowser.open(u))
            grid.Add(b, 0, wx.RIGHT | wx.BOTTOM, 6)
        v.Add(grid, 0, wx.LEFT | wx.RIGHT, 8)
        v.Add(wx.Button(self, wx.ID_CANCEL, "&Bezárás"), 0,
              wx.ALL | wx.ALIGN_RIGHT, 8)
        self.SetSizer(v)
        txt.SetInsertionPoint(0)
        txt.SetFocus()
