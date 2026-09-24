"""Szöveg-felolvasó (TTS) motorok közös felülete a hangoskönyv-készítőhöz.

Négy backend:
  sapi   – helyi Windows-hangok (offline, ingyenes)
  edge   – Microsoft Edge neural hangok (online, ingyenes, KULCS NÉLKÜL)
  gemini – Google Gemini TTS (saját API-kulcs)
  cloud  – Google Cloud Text-to-Speech (saját API-kulcs)

Mindegyik motor egy hang-azonosítóra és (ahol támogatott) pitch/sebesség
értékre szintetizál egy hangfájlt. A pitch és a rate egységesen -10..10
egész; a motorok a sajátjukra képezik le. A hosszú szöveget a hívó
darabolja a `char_limit` szerint.
"""

import base64
import contextlib
import json
import logging
import os
import queue
import re
import subprocess
import threading
import urllib.request
from dataclasses import dataclass

_log = logging.getLogger("superdl.tts")


# ======================================================================
#  SAPI 32 BITEN – a magyar hangok nagy része CSAK így szólal meg
# ======================================================================
#
# ⚠️ MÉRVE 2026-09-24, Dávid gépén, ugyanazzal a szöveggel:
#
#   64 bites folyamat (a SuperDL maga):  11 hang látszik, ebből 9 ELBUKIK
#       BME-TMIT Eszti/Eszter/Gabi/Gábor/Péter/Peti/Vera/Veronika:
#           0x80045001 (SPERR_UNINITIALIZED) – pontosan Tóth László hibája
#       Peter: 0x80040154 („az osztály nincs regisztrálva")
#       csak a Zira és a BraiLab PC működik
#   32 bites folyamat (SysWOW64 PowerShell): 18 hang látszik, MIND A 18 MŰKÖDIK
#
# Az ok: ezeknek a hangoknak a beszédmotorja 32 bites DLL. Egy 64 bites
# program a hang NEVÉT még látja a nyilvántartásban, de a motort betölteni
# nem tudja — ezért „nincs inicializálva". A magyar vak felhasználók
# legelterjedtebb helyi hangjai (Profivox / BME-TMIT) mind ilyenek, vagyis a
# „belső hangok" a SuperDL-ben gyakorlatilag SOHA nem működtek.
#
# A megoldás: a Windows MINDEN 64 bites gépen hordoz egy 32 bites
# PowerShellt (SysWOW64). Azt indítjuk el EGYSZER, háttérben, és a
# szövegdarabokat neki küldjük; ő mondja fájlba a 32 bites SAPI-val.
# Nem kell hozzá semmit telepíteni vagy csomagolni.
#
# ⚠️ -EncodedCommand, NEM -File: a végrehajtási házirend (ExecutionPolicy)
# a SZKRIPTFÁJLOKRA vonatkozik; egy céges gépen az „AllSigned" házirend a
# fájlt elutasítaná, a parancsként átadott szöveget nem.
#
# ⚠️ A protokoll SORONKÉNT base64: a szöveg magyar ékezetes, a konzol
# kódlapja pedig gépenként más. Base64-ben semmi nem veszhet el.

_SAPI32_SZKRIPT = r"""
$ErrorActionPreference = "Stop"
$u = New-Object System.Text.UTF8Encoding($false)
function Ki($s) { [Console]::Out.WriteLine($s); [Console]::Out.Flush() }
function B64($s) { [Convert]::ToBase64String($u.GetBytes([string]$s)) }
$hangok = @{}
Ki "KESZ"
while ($true) {
  $sor = [Console]::In.ReadLine()
  if ($sor -eq $null) { break }
  $sor = $sor.Trim()
  if ($sor -eq "") { continue }
  try {
    $k = $u.GetString([Convert]::FromBase64String($sor)) | ConvertFrom-Json
    if ($k.c -eq "list") {
      $v0 = New-Object -ComObject SAPI.SpVoice
      $lista = @()
      foreach ($t in $v0.GetVoices()) {
        $lang = ""
        try { $lang = [string]$t.GetAttribute("Language") } catch {}
        $lista += @{ n = [string]$t.GetDescription(); l = $lang }
      }
      Ki ("OK " + (B64 (ConvertTo-Json -InputObject @($lista) -Compress)))
    } elseif ($k.c -eq "say") {
      $nev = [string]$k.v
      if (-not $hangok.ContainsKey($nev)) {
        $v = New-Object -ComObject SAPI.SpVoice
        $talalt = ($nev -eq "")
        foreach ($t in $v.GetVoices()) {
          if ($t.GetDescription() -eq $nev) { $v.Voice = $t; $talalt = $true; break }
        }
        if (-not $talalt) { throw ("Ez a hang nincs meg ezen a gépen: " + $nev) }
        $hangok[$nev] = $v
      }
      $v = $hangok[$nev]
      $fs = New-Object -ComObject SAPI.SpFileStream
      $fs.Open([string]$k.o, 3)
      try {
        $v.AudioOutputStream = $fs
        $v.Rate = [int]$k.r
        [void]$v.Speak([string]$k.t, [int]$k.f)
      } finally {
        $fs.Close()
      }
      Ki ("OK " + (Get-Item -LiteralPath ([string]$k.o)).Length)
    } elseif ($k.c -eq "bye") {
      break
    }
  } catch {
    Ki ("HIBA " + (B64 $_.Exception.Message))
  }
}
"""

# SAPI Speak-jelzők. ⚠️ MÉRVE 2026-09-24 (BraiLab PC, 32 bit): a szöveg elé
# tett `<pitch absmiddle='0'/>` az ALAPÉRTELMEZETT jelzővel ÜRES hangfájlt
# ad (46 bájt), az IsXML-lel viszont rendes hangot. Ezért: hangmagasság
# nélkül SIMA SZÖVEG (IsNotXML – a motor semmit nem értelmez benne, és a
# „&" sem kell, hogy „&amp;" legyen), hangmagassággal kifejezetten IsXML.
SVSF_IS_XML = 8
SVSF_IS_NOT_XML = 16

# Az ennél kisebb WAV gyakorlatilag csak fejléc: a hang NEM mondott semmit.
URES_WAV_BAJT = 100


class _Sapi32Nincs(RuntimeError):
    """A 32 bites segéd nem érhető el ezen a gépen (nincs SysWOW64
    PowerShell, vagy nem indult el). Ilyenkor a régi, 64 bites út jön."""


class _Sapi32:
    """A háttérben futó 32 bites PowerShell, ami a SAPI-t kiszolgálja."""

    INDULAS_MP = 25.0
    LISTA_MP = 30.0
    MONDAS_MP = 180.0      # egy darab (≈ 1-2 ezer karakter) bőven belefér

    def __init__(self):
        self._zar = threading.Lock()
        self._proc = None
        self._sorok: "queue.Queue[str | None]" = queue.Queue()
        self._nincs = False      # egyszer már kiderült, hogy nem megy

    @staticmethod
    def powershell32() -> "str | None":
        if os.name != "nt":
            return None
        windir = (os.environ.get("SystemRoot") or os.environ.get("WINDIR")
                  or r"C:\Windows")
        p = os.path.join(windir, "SysWOW64", "WindowsPowerShell", "v1.0",
                         "powershell.exe")
        return p if os.path.isfile(p) else None

    def _olvaso(self, cso) -> None:
        try:
            for sor in iter(cso.readline, b""):
                self._sorok.put(sor.decode("ascii", "replace").strip())
        except Exception:
            pass
        self._sorok.put(None)

    def _leallit(self) -> None:
        p, self._proc = self._proc, None
        if p is None:
            return
        try:
            p.kill()
        except Exception:
            pass
        try:
            p.wait(timeout=5)
        except Exception:
            pass

    def _indit(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._leallit()
        ps = self.powershell32()
        if not ps:
            self._nincs = True
            raise _Sapi32Nincs("nincs 32 bites PowerShell ezen a gépen")
        kod = base64.b64encode(_SAPI32_SZKRIPT.encode("utf-16-le")).decode()
        self._sorok = queue.Queue()
        try:
            self._proc = subprocess.Popen(
                [ps, "-NoLogo", "-NoProfile", "-NonInteractive",
                 "-EncodedCommand", kod],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            self._nincs = True
            raise _Sapi32Nincs(str(e))
        threading.Thread(target=self._olvaso, args=(self._proc.stdout,),
                         daemon=True, name="sapi32-olvaso").start()
        try:
            elso = self._sorok.get(timeout=self.INDULAS_MP)
        except queue.Empty:
            elso = None
        if elso != "KESZ":
            self._leallit()
            self._nincs = True
            raise _Sapi32Nincs("a 32 bites segéd nem indult el (%r)" % elso)

    def _kerdez(self, parancs: dict, varakozas: float) -> str:
        """Egy parancs, egy válaszsor. A zár alatt: a segéd sorban dolgozik."""
        if self._nincs:
            raise _Sapi32Nincs("korábban már nem indult el")
        with self._zar:
            self._indit()
            sor = base64.b64encode(
                json.dumps(parancs, ensure_ascii=False).encode("utf-8"))
            try:
                self._proc.stdin.write(sor + b"\n")
                self._proc.stdin.flush()
                valasz = self._sorok.get(timeout=varakozas)
            except queue.Empty:
                self._leallit()
                raise RuntimeError(
                    "A helyi beszédhang %d másodperc alatt sem végzett ezzel "
                    "a darabbal." % int(varakozas))
            except OSError as e:
                self._leallit()
                raise RuntimeError("A helyi beszédhang segédje leállt: %s" % e)
            if valasz is None:
                self._leallit()
                raise RuntimeError("A helyi beszédhang segédje váratlanul "
                                   "leállt.")
        if valasz.startswith("OK"):
            return valasz[2:].strip()
        if valasz.startswith("HIBA "):
            try:
                uzenet = base64.b64decode(valasz[5:]).decode("utf-8", "replace")
            except Exception:
                uzenet = valasz[5:]
            raise RuntimeError(uzenet.strip() or "ismeretlen SAPI-hiba")
        raise RuntimeError("értelmezhetetlen válasz: %r" % valasz[:80])

    def hangok(self) -> list:
        """[(név, nyelv)] a 32 bites SAPI szerint."""
        adat = self._kerdez({"c": "list"}, self.LISTA_MP)
        lista = json.loads(base64.b64decode(adat).decode("utf-8") or "[]")
        if isinstance(lista, dict):          # egyelemű PowerShell-tömb
            lista = [lista]
        return [(str(x.get("n", "")), str(x.get("l", "")))
                for x in lista if x.get("n")]

    def mond(self, szoveg: str, hang: str, rate: int, jelzo: int,
             ut: str) -> int:
        """Fájlba mondja; visszaadja a keletkezett WAV méretét bájtban."""
        meret = self._kerdez({"c": "say", "t": szoveg, "v": hang,
                              "r": int(rate), "f": int(jelzo), "o": ut},
                             self.MONDAS_MP)
        try:
            return int(meret)
        except ValueError:
            return 0


_SAPI32 = _Sapi32()


def _sapi32_leallit() -> None:
    try:
        _SAPI32._leallit()
    except Exception:
        pass


import atexit as _atexit                     # noqa: E402
_atexit.register(_sapi32_leallit)


@contextlib.contextmanager
def _sapi_com():
    """A SAPI-t (win32com) használó szál KÖTELEZŐEN inicializálja a COM-ot.
    E nélkül HÁTTÉRSZÁLON „CoInitialize has not been called” com_error jön, amit
    a hívók néha némán elnyelnek (élesben igazolt hiba: a hangoskönyv-készítő
    SAPI-hanggal háttérszálon elszállt). Ha a hívó szál (pl. wx főszál) már
    inicializálta a COM-ot, a CoInitialize S_FALSE-t ad, de a számláló így is
    kiegyensúlyozott a CoUninitialize-zal, ezért biztonságos mindkét esetben."""
    did = False
    try:
        import pythoncom
        pythoncom.CoInitialize()
        did = True
    except Exception:
        did = False
    try:
        yield
    finally:
        if did:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass


@dataclass
class Voice:
    id: str
    name: str
    lang: str = ""
    gender: str = ""


# ======================================================================
#  SAPI – helyi hangok
# ======================================================================
class SapiEngine:
    key = "sapi"
    name = "Helyi hangok (SAPI, offline, ingyenes)"
    char_limit = 0            # 0 = nincs gyakorlati korlát
    supports_pitch = True
    supports_rate = True
    needs_key = False

    def voices(self, api_key: str = "") -> list[Voice]:
        # ELŐSZÖR a 32 bites segéd: ő látja az ÖSSZES hangot (Dávid gépén 18
        # a 64 bites 11 helyett), és ő is tudja megszólaltatni őket.
        try:
            lista = _SAPI32.hangok()
            if lista:
                return [Voice(id=n, name=n, lang=l) for n, l in lista]
        except _Sapi32Nincs as e:
            _log.info("32 bites SAPI nem érhető el, a 64 bites jön: %s", e)
        except Exception as e:
            _log.warning("32 bites SAPI hanglista hiba, a 64 bites jön: %s", e)
        return self._voices64()

    def _voices64(self) -> list[Voice]:
        import win32com.client
        out = []
        with _sapi_com():           # háttérszál-biztos COM-inicializálás
            v = win32com.client.Dispatch("SAPI.SpVoice")
            for t in v.GetVoices():
                desc = t.GetDescription()
                lang = ""
                try:
                    lang = t.GetAttribute("Language")
                except Exception:
                    pass
                out.append(Voice(id=desc, name=desc, lang=lang))
            t = None
            v = None                # a COM-objektumokat még inicializált COM alatt engedjük el
        return out

    @staticmethod
    def szoveg_es_jelzo(text: str, pitch: int) -> "tuple[str, int]":
        """A SAPI-nak átadott szöveg és Speak-jelző.

        ⚠️ MÉRVE (BraiLab PC): a hangmagasság-jelölés az alapértelmezett
        jelzővel ÜRES hangot adott. Ezért nulla hangmagasságnál egyáltalán
        NEM küldünk jelölést, és a szöveget kifejezetten sima szövegként
        adjuk át (a benne lévő „<" és „&" is betű marad)."""
        p = max(-10, min(10, int(pitch or 0)))
        if p == 0:
            return text, SVSF_IS_NOT_XML
        return (f"<pitch absmiddle='{p}'/>" + _xml_escape(text), SVSF_IS_XML)

    def synth(self, text, voice_id, out_base, pitch=0, rate=0,
              api_key="") -> str:
        path = out_base + ".wav"
        r = max(-10, min(10, int(rate or 0)))
        try:
            szoveg, jelzo = self.szoveg_es_jelzo(text, pitch)
            meret = _SAPI32.mond(szoveg, voice_id, r, jelzo, path)
            if meret <= URES_WAV_BAJT and jelzo == SVSF_IS_XML:
                # ⚠️ MÉRVE: a BraiLab a hangmagasság-kérésre CSENDET ad.
                # Inkább szóljon hangmagasság nélkül, mint sehogy.
                _log.info("A(z) %s hang nem tud hangmagasságot, anélkül "
                          "mondom.", voice_id)
                szoveg, jelzo = self.szoveg_es_jelzo(text, 0)
                meret = _SAPI32.mond(szoveg, voice_id, r, jelzo, path)
            if meret <= URES_WAV_BAJT:
                raise RuntimeError(
                    "A(z) „%s” hang nem mondott semmit erre a darabra (üres "
                    "hangfájl lett belőle)." % voice_id)
            return path
        except _Sapi32Nincs as e:
            _log.info("32 bites SAPI nem érhető el, a 64 bites jön: %s", e)
        return self._synth64(text, voice_id, path, pitch, r)

    def _synth64(self, text, voice_id, path, pitch, rate) -> str:
        """A régi, 64 bites út – csak ha a 32 bites segéd nem érhető el.
        A magyar BME-TMIT hangok ezen az úton NEM szólalnak meg (mérve)."""
        import win32com.client
        with _sapi_com():           # háttérszál-biztos COM-inicializálás
            fs = win32com.client.Dispatch("SAPI.SpFileStream")
            fs.Open(path, 3)
            v = win32com.client.Dispatch("SAPI.SpVoice")
            for t in v.GetVoices():
                if t.GetDescription() == voice_id:
                    v.Voice = t
                    break
            v.AudioOutputStream = fs
            v.Rate = max(-10, min(10, int(rate)))
            szoveg, jelzo = self.szoveg_es_jelzo(text, pitch)
            v.Speak(szoveg, jelzo)
            fs.Close()
            t = None
            v = None
            fs = None               # a COM-objektumokat még inicializált COM alatt engedjük el
        return path


# ======================================================================
#  EDGE – ingyenes neural hangok, kulcs nélkül
# ======================================================================
class EdgeEngine:
    key = "edge"
    name = "Edge neural (online, ingyenes, kulcs nélkül)"
    char_limit = 0
    supports_pitch = True
    supports_rate = True
    needs_key = False

    def voices(self, api_key: str = "") -> list[Voice]:
        import asyncio

        import edge_tts
        data = asyncio.run(edge_tts.list_voices())
        out = []
        for v in data:
            out.append(Voice(id=v["ShortName"],
                             name=f"{v['ShortName']}  ({v.get('Gender','')})",
                             lang=v.get("Locale", ""),
                             gender=v.get("Gender", "")))
        out.sort(key=lambda x: (not x.lang.startswith("hu"), x.lang, x.id))
        return out

    def synth(self, text, voice_id, out_base, pitch=0, rate=0,
              api_key="") -> str:
        import asyncio

        import edge_tts
        path = out_base + ".mp3"
        r = f"{'+' if rate >= 0 else '-'}{abs(int(rate))*10}%"
        p = f"{'+' if pitch >= 0 else '-'}{abs(int(pitch))*5}Hz"

        async def go():
            c = edge_tts.Communicate(text, voice_id, rate=r, pitch=p)
            await c.save(path)

        asyncio.run(go())
        return path


# ======================================================================
#  GEMINI TTS – saját kulcs
# ======================================================================
GEMINI_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]


class GeminiEngine:
    key = "gemini"
    name = "Google Gemini TTS (saját API-kulcs)"
    char_limit = 4000
    supports_pitch = False
    supports_rate = False
    needs_key = True
    model = "gemini-2.5-flash-preview-tts"

    def voices(self, api_key: str = "") -> list[Voice]:
        return [Voice(id=n, name=n) for n in GEMINI_VOICES]

    def synth(self, text, voice_id, out_base, pitch=0, rate=0,
              api_key="") -> str:
        # a kulcs FEJLÉCBEN megy (nem az URL-ben) – így kivételben sem szivárog
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent")
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_id}}},
            },
        }
        data = _post_json(url, body, api_key=api_key)
        part = data["candidates"][0]["content"]["parts"][0]
        pcm = base64.b64decode(part["inlineData"]["data"])
        path = out_base + ".wav"
        _write_wav(path, pcm, rate=24000, channels=1)
        return path


# ======================================================================
#  GOOGLE CLOUD TTS – saját kulcs
# ======================================================================
class CloudEngine:
    key = "cloud"
    name = "Google Cloud Text-to-Speech (saját API-kulcs)"
    char_limit = 5000
    # A szolgáltatás korlátja BÁJTBAN értendő (nem karakterben): a magyar
    # ékezetek 2 bájtosak, ezért karakterben mérve túlléphetnénk a limitet.
    # Tartalékkal 4800, mert a kérés kerete is beleszámít. [Herman Tibi AB-P1-10]
    byte_limit = 4800
    supports_pitch = True
    supports_rate = True
    needs_key = True

    def voices(self, api_key: str = "") -> list[Voice]:
        url = "https://texttospeech.googleapis.com/v1/voices"
        data = _get_json(url, api_key=api_key)
        out = []
        for v in data.get("voices", []):
            lang = (v.get("languageCodes") or [""])[0]
            out.append(Voice(id=v["name"], name=f"{v['name']}  ({lang})",
                             lang=lang,
                             gender=v.get("ssmlGender", "")))
        out.sort(key=lambda x: (not x.lang.startswith("hu"), x.lang, x.id))
        return out

    def synth(self, text, voice_id, out_base, pitch=0, rate=0,
              api_key="") -> str:
        lang = "-".join(voice_id.split("-")[:2]) if "-" in voice_id else "en-US"
        url = "https://texttospeech.googleapis.com/v1/text:synthesize"
        body = {
            "input": {"text": text},
            "voice": {"languageCode": lang, "name": voice_id},
            "audioConfig": {"audioEncoding": "MP3",
                            "speakingRate": max(0.25, min(4.0, 1 + rate * 0.1)),
                            "pitch": max(-20.0, min(20.0, float(pitch)))},
        }
        data = _post_json(url, body, api_key=api_key)
        path = out_base + ".mp3"
        with open(path, "wb") as f:
            f.write(base64.b64decode(data["audioContent"]))
        return path


ENGINES = {e.key: e for e in (SapiEngine(), EdgeEngine(),
                              GeminiEngine(), CloudEngine())}


# ---- segédek ----------------------------------------------------------

def _xml_escape(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _write_wav(path, pcm: bytes, rate=24000, channels=1, width=2) -> None:
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(pcm)


def redact(text: str, *secrets: str) -> str:
    """Az API-kulcsok MASZKOLÁSA minden felhasználónak megjelenő szövegben.
    A hálózati kivételek szövege tartalmazhatja a kérés URL-jét/fejlécét; e nélkül
    a titkos kulcs megjelenhetne a képernyőn, a képernyőolvasó beszédében vagy egy
    támogatási levélben. [Herman Tibi AB-P0-05 / TTS-SEC-001]"""
    out = str(text)
    for s in secrets:
        s = (s or "").strip()
        if len(s) >= 8:                       # rövid „kulcs” nem valódi titok
            out = out.replace(s, "***")
    # biztonsági háló: bármilyen key=... query-paraméter maradványa
    return re.sub(r"(?i)([?&]key=)[^&\s\"']+", r"\1***", out)


class TTSError(RuntimeError):
    """TTS-hiba MASZKOLT szöveggel (soha nem tartalmaz API-kulcsot)."""


def _api_headers(api_key: str = "") -> dict:
    """A Google API-k a kulcsot FEJLÉCBEN is elfogadják (x-goog-api-key). Így a
    kulcs NEM kerül az URL-be, tehát a kivételek/naplók URL-je sem szivárogtatja."""
    h = {"User-Agent": "SuperDL"}
    if api_key:
        h["x-goog-api-key"] = api_key
    return h


def _get_json(url, timeout=30, api_key=""):
    req = urllib.request.Request(url, headers=_api_headers(api_key))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:
        raise TTSError(redact(e, api_key)) from None


def _post_json(url, body, timeout=120, api_key=""):
    data = json.dumps(body).encode("utf-8")
    headers = _api_headers(api_key)
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:
        raise TTSError(redact(e, api_key)) from None
