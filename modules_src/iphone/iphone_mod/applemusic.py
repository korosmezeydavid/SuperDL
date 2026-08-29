# -*- coding: utf-8 -*-
"""A GYÁRI ZENE ALKALMAZÁSBA – az Apple saját programjain keresztül.

Miért így? Mert a telefon zene-adatbázisába kívülről írni nem lehet: a telefon
szolgáltatása birtokolja, és a kívülről írt bejegyzést előbb-utóbb felülírja
(élőben megmértük: a szám felkerül, aztán eltűnik). Az Apple viszont ad egy
HIVATALOS bejáratot a gépen – csak nem mondja el senkinek, és a felülete
képernyőolvasóval használhatatlan.

A lánc két lépésből áll, és mindkettőt élesben végigmértük:

  1. BEHOZATAL – az Apple Music figyel egy mappát („Automatically Add to Apple
     Music”). Ami oda kerül, azt magától beolvassa a könyvtárába. Ez egy
     fájlmásolás: nem tud elromlani, nem függ gomb-feliratoktól.

  2. SZINKRON – az Apple Devices átviszi a könyvtárat a telefonra, és a szám a
     gyári Zene alkalmazásban jelenik meg. Ehhez meg kell nyomni egy gombot,
     amit a program a Windows felület-automatizálásán át nyom meg – pontosan
     úgy, ahogy a felhasználó tenné egérrel, csak nem kell hozzá látni.

SEMMIT NEM KERÜLÜNK MEG: a saját gépén, a saját programjaival, a saját zenéjét
viszi át. Csak a kezelést vesszük le a válláról.

A törékeny rész a 2. lépés: ha az Apple átnevez egy gombot vagy megváltozik a
nyelv, a vezérlés nem talál rá. Ilyenkor NEM csinálunk csendben valami mást –
kimondjuk, hogy mi történt, és a felhasználó kézzel is befejezheti.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time

# A gombok és jelölőnégyzetek neve a Windows nyelvét követi, ezért magyarul ÉS
# angolul is keresünk. (Reguláris kifejezés, a PowerShell -match kapja meg.)
_ZENE_LAP = "^(Zene|Music)$"
_SZINKRON_BE = "szinkroniz.*ide|Sync music onto|Sync Music"
_SZINKRON_GOMB = "^(Szinkroniz.l.s|Alkalmaz.s|Sync|Apply)$"
_LEALLIT_GOMB = "Szinkroniz.*le.ll|Stop sync"
_TELJES_KONYVTAR = "Teljes zenek.nyvt.r|Entire music library"
_MEGEROSIT = "Elt.vol.t.s .s szinkroniz|Remove and Sync"
# Ha az Apple Devices NEM látja a telefont, hiába minden: a beállítás sem
# marad meg, és szinkron sem indul. Élesben ez fogott ki rajtunk a legtovább.
_NINCS_ESZKOZ = "csatlakoztasson egy Apple|Connect an Apple device"

_ABLAK = "Apple Devices"
_MUSIC_APPID = "AppleInc.AppleMusicWin_nzyj5cx40ttqa!App"
_DEVICES_APPID = "AppleInc.AppleDevices_nzyj5cx40ttqa!App"


class AppleHiba(Exception):
    """Amit az Apple programjaival nem sikerült elintézni."""


# ------------------------------------------------------------ 1. behozatal

def konyvtar_mappa() -> str:
    """Az Apple Music könyvtárának mappája a gépen (üres, ha nincs telepítve)."""
    alap = os.path.join(os.path.expanduser("~"), "Music", "Apple Music")
    return alap if os.path.isdir(alap) else ""


def figyelt_mappa() -> str:
    """Az a mappa, amit az Apple Music FIGYEL – ami ide kerül, azt beolvassa.

    A nevét nem írjuk be kőbe: verziónként és nyelvenként lehet „Automatically
    Add to Apple Music” vagy „…to Music”, ezért a kezdete alapján keressük."""
    alap = konyvtar_mappa()
    if not alap:
        return ""
    media = os.path.join(alap, "Media")
    if not os.path.isdir(media):
        return ""
    for nev in sorted(os.listdir(media)):
        teljes = os.path.join(media, nev)
        if os.path.isdir(teljes) and nev.lower().startswith("automatically add"):
            return teljes
    return ""


def elerheto() -> bool:
    """Használható-e ez az út ezen a gépen?"""
    return bool(figyelt_mappa())


def _inditsd(appid: str):
    """Egy Store-alkalmazás indítása (ha már fut, csak előhozza)."""
    try:
        subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + appid],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        pass


def behoz(utak: list, on_progress=None, megszakit=None,
          varakozas: float = 90.0) -> tuple:
    """Fájlok behozatala az Apple Music könyvtárába.

    A fájlt a figyelt mappába másoljuk, majd MEGVÁRJUK, míg az Apple Music
    elnyeli (ekkor tűnik el onnan). Ha a program nem fut, elindítjuk – enélkül
    a fájl ott maradna, és a felhasználó azt hinné, elveszett.

    Visszaad: (sikeres darab, hibák listája)."""
    figyelt = figyelt_mappa()
    if not figyelt:
        raise AppleHiba(
            "Nem találom az Apple Music könyvtárát ezen a gépen. Telepítsd a "
            "Microsoft Store-ból az Apple Music alkalmazást, indítsd el "
            "egyszer, és próbáld újra.")
    utak = [u for u in (utak or []) if os.path.isfile(u)]
    if not utak:
        return 0, []

    _inditsd(_MUSIC_APPID)                 # nélküle nem olvasná be
    ok, hibak = 0, []
    n = len(utak)
    for i, ut in enumerate(utak, 1):
        if megszakit is not None and megszakit():
            break
        try:
            cel = _szabad_nev(figyelt, os.path.basename(ut))
            shutil.copy2(ut, cel)
            if _megvarja_hogy_elnyeljek(cel, varakozas, megszakit):
                ok += 1
            else:
                # Élesben megmértük: ha az Apple Music könyvtára frissen jött
                # létre (vagy hiányzik), a figyelt mappát NEM olvassa be. A
                # felhasználónak ilyenkor tudnia kell, mit tegyen – a fájl
                # egyébként ott van, nem veszett el.
                os.path.basename(ut)
                hibak.append(
                    "%s: az Apple Music nem olvasta be. Nyisd meg egyszer az "
                    "Apple Music alkalmazást, és győződj meg róla, hogy a "
                    "zenekönyvtárad látszik benne; utána próbáld újra. A fájl "
                    "addig itt vár: %s" % (os.path.basename(ut), figyelt))
        except Exception as ex:
            hibak.append("%s: %s" % (os.path.basename(ut), ex))
        if on_progress:
            on_progress(i, n, os.path.basename(ut), ok)
    return ok, hibak


def _szabad_nev(mappa: str, nev: str) -> str:
    cel = os.path.join(mappa, nev)
    if not os.path.exists(cel):
        return cel
    torzs, kit = os.path.splitext(nev)
    i = 2
    while os.path.exists(os.path.join(mappa, "%s (%d)%s" % (torzs, i, kit))):
        i += 1
    return os.path.join(mappa, "%s (%d)%s" % (torzs, i, kit))


def _megvarja_hogy_elnyeljek(ut: str, masodperc: float, megszakit=None) -> bool:
    """Az Apple Music a beolvasott fájlt ELVISZI a figyelt mappából – ez a
    visszaigazolás, hogy tényleg bekerült a könyvtárba."""
    hatarido = time.monotonic() + max(5.0, masodperc)
    while time.monotonic() < hatarido:
        if not os.path.exists(ut):
            return True
        if megszakit is not None and megszakit():
            return False
        time.sleep(0.5)
    return not os.path.exists(ut)


# ------------------------------------------------------------- 2. szinkron

_PS_SEGED = r'''
# A SuperDL felület-vezérlő segédje az Apple Devices alkalmazáshoz.
# Csak azt teszi, amit a felhasználó tenne egérrel; JSON-t ad vissza.
param([string]$muvelet = "allapot")

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes

function Valasz($h) { $h | ConvertTo-Json -Compress }

function Ablak() {
  $root = [System.Windows.Automation.AutomationElement]::RootElement
  $f = New-Object System.Windows.Automation.PropertyCondition(
      [System.Windows.Automation.AutomationElement]::NameProperty, "ABLAK_NEVE")
  for ($i = 0; $i -lt 40; $i++) {
    $a = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $f)
    if ($a) { return $a }
    Start-Sleep -Milliseconds 750
  }
  return $null
}

function Elemek($ablak) {
  $ablak.FindAll([System.Windows.Automation.TreeScope]::Descendants,
                 [System.Windows.Automation.Condition]::TrueCondition)
}

function Keres($elemek, $minta, $tipus) {
  foreach ($e in $elemek) {
    $t = $e.Current.ControlType.ProgrammaticName -replace 'ControlType\.',''
    if ($t -match $tipus -and $e.Current.Name -match $minta) { return $e }
  }
  return $null
}

# Az ablak MEGLÉTE még nem jelenti, hogy a tartalma is felépült: előhozás után
# a felület-fa egy ideig üres. Ezért megvárjuk a keresett elemet.
function Varj($ablak, $minta, $tipus, $masodperc = 20) {
  $hatarido = (Get-Date).AddSeconds($masodperc)
  do {
    $t = Keres (Elemek $ablak) $minta $tipus
    if ($t) { return $t }
    Start-Sleep -Milliseconds 600
  } while ((Get-Date) -lt $hatarido)
  return $null
}

$ablak = Ablak
if (-not $ablak) { Valasz @{ ok = $false; hiba = "nincs_ablak" }; exit }

# a Zene lapra lépünk (ez csak navigáció, semmit nem kapcsol)
$zene = Varj $ablak "ZENE_LAP" "ListItem"
if ($zene) {
  try {
    $zene.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
    Start-Sleep -Milliseconds 1200
  } catch {}
}
$e = Elemek $ablak

$pipa   = Keres $e "SZINKRON_BE" "CheckBox"
$gomb   = Varj $ablak "SZINKRON_GOMB" "Button" 8
$leall  = Keres $e "LEALLIT_GOMB" "Button"
$teljes = Keres $e "TELJES_KONYVTAR" "RadioButton"
$megero = Keres $e "MEGEROSIT_GOMB" "Button"
$nincs  = Keres $e "NINCS_ESZKOZ" "Text"

$be = $false
if ($pipa) {
  try { $be = ($pipa.GetCurrentPattern(
      [System.Windows.Automation.TogglePattern]::Pattern).Current.ToggleState -eq "On") } catch {}
}
$teljes_e = $false
if ($teljes) {
  try { $teljes_e = $teljes.GetCurrentPattern(
      [System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected } catch {}
}

if ($muvelet -eq "allapot") {
  Valasz @{ ok = $true; bekapcsolva = $be; fut = [bool]$leall;
            teljes_konyvtar = $teljes_e; van_gomb = [bool]$gomb;
            megerosites_var = [bool]$megero;
            van_eszkoz = $(if ($nincs) { $false } else { $true });
            gomb_neve = $(if ($gomb) { $gomb.Current.Name } else { "" });
            keszulek = $(if ($zene) { $true } else { $false }) }
  exit
}

if ($muvelet -eq "szinkron") {
  if ($leall) { Valasz @{ ok = $true; mar_fut = $true }; exit }
  if (-not $gomb) { Valasz @{ ok = $false; hiba = "nincs_gomb" }; exit }
  if (-not $gomb.Current.IsEnabled) { Valasz @{ ok = $false; hiba = "gomb_tiltva" }; exit }
  $gomb.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
  Start-Sleep -Seconds 3
  $e2 = Elemek $ablak
  $leall2 = Keres $e2 "LEALLIT_GOMB" "Button"
  Valasz @{ ok = $true; elindult = [bool]$leall2 }
  exit
}

if ($muvelet -eq "bekapcsol") {
  # A zene-szinkron bekapcsolása és a „teljes könyvtár” beállítása.
  # A hívó oldal ELŐTTE megkérdezi a felhasználót, mert ez azt jelenti, hogy a
  # telefon zenéje a gépi könyvtárhoz fog igazodni.
  if (-not $pipa) { Valasz @{ ok = $false; hiba = "nincs_pipa" }; exit }
  if (-not $be) {
    $pipa.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Toggle()
    Start-Sleep -Milliseconds 1200
  }
  $e2 = Elemek $ablak
  $teljes2 = Keres $e2 "TELJES_KONYVTAR" "RadioButton"
  if ($teljes2) {
    try {
      $sp = $teljes2.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
      if (-not $sp.Current.IsSelected) { $sp.Select() }
    } catch {}
  }
  $pipa2 = Keres $e2 "SZINKRON_BE" "CheckBox"
  $be2 = $false
  if ($pipa2) {
    try { $be2 = ($pipa2.GetCurrentPattern(
        [System.Windows.Automation.TogglePattern]::Pattern).Current.ToggleState -eq "On") } catch {}
  }
  Valasz @{ ok = $true; bekapcsolva = $be2 }
  exit
}

if ($muvelet -eq "megerosit") {
  $m = Varj $ablak "MEGEROSIT_GOMB" "Button" 10
  if (-not $m) { Valasz @{ ok = $true; nem_kellett = $true }; exit }
  $m.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
  Start-Sleep -Seconds 2
  Valasz @{ ok = $true; megerositve = $true }
  exit
}

if ($muvelet -eq "leallit") {
  if (-not $leall) { Valasz @{ ok = $true; nem_futott = $true }; exit }
  $leall.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
  Valasz @{ ok = $true; leallitva = $true }
  exit
}

Valasz @{ ok = $false; hiba = "ismeretlen_muvelet" }
'''


def _ps(muvelet: str, idokorlat: int = 120) -> dict:
    """A felület-vezérlő segéd futtatása. A PowerShell beépített felület-
    automatizálását használjuk: nem kell hozzá külső csomag, és a lefagyasztott
    programban sem kell semmit generálni."""
    script = (_PS_SEGED
              .replace("ABLAK_NEVE", _ABLAK)
              .replace("ZENE_LAP", _ZENE_LAP)
              .replace("SZINKRON_BE", _SZINKRON_BE)
              .replace("SZINKRON_GOMB", _SZINKRON_GOMB)
              .replace("LEALLIT_GOMB", _LEALLIT_GOMB)
              .replace("TELJES_KONYVTAR", _TELJES_KONYVTAR)
              .replace("MEGEROSIT_GOMB", _MEGEROSIT)
              .replace("NINCS_ESZKOZ", _NINCS_ESZKOZ))
    f = tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                    encoding="utf-8-sig")
    f.write(script)
    f.close()
    try:
        p = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", f.name, muvelet],
            capture_output=True, text=True, timeout=idokorlat,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        sor = (p.stdout or "").strip().splitlines()
        for s in reversed(sor):                 # az utolsó sor a JSON
            s = s.strip()
            if s.startswith("{"):
                return json.loads(s)
        raise AppleHiba(
            "Az Apple Devices vezérlése nem adott értelmes választ. "
            + ((p.stderr or "").strip()[:200] or ""))
    except subprocess.TimeoutExpired as ex:
        raise AppleHiba("Az Apple Devices nem válaszolt időben.") from ex
    finally:
        try:
            os.remove(f.name)
        except OSError:
            pass


def szinkron_allapot(inditsd: bool = True) -> dict:
    """Mit mutat most az Apple Devices? {'bekapcsolva','fut','teljes_konyvtar'}."""
    if inditsd:
        _inditsd(_DEVICES_APPID)
    v = _ps("allapot")
    if not v.get("ok"):
        if v.get("hiba") == "nincs_ablak":
            raise AppleHiba(
                "Nem találom az Apple Devices ablakát. Indítsd el egyszer "
                "kézzel (Start menü → Apple Devices), és próbáld újra.")
        raise AppleHiba("Az Apple Devices állapota nem olvasható ki.")
    return v


def szinkron_bekapcsol() -> dict:
    """A zene-szinkron bekapcsolása („teljes könyvtár” módban).

    FIGYELEM: ettől a telefon zenéje a GÉPI könyvtárhoz igazodik. A hívó
    felületnek ezt a felhasználóval EL KELL FOGADTATNIA, mielőtt idejön."""
    _inditsd(_DEVICES_APPID)
    v = _ps("bekapcsol")
    if not v.get("ok"):
        raise AppleHiba(
            "Nem találom a zene-szinkron kapcsolóját az Apple Devices "
            "ablakában. Kapcsold be kézzel: Apple Devices → a telefonod → "
            "Zene → „Zenék szinkronizálása”.")
    if not v.get("bekapcsolva"):
        raise AppleHiba("A zene-szinkron nem kapcsolt be.")
    return v


def szinkronizal() -> dict:
    """A szinkron elindítása – ugyanaz, mintha a felhasználó nyomná meg."""
    _inditsd(_DEVICES_APPID)
    v = _ps("szinkron")
    if not v.get("ok"):
        hiba = v.get("hiba")
        if hiba == "nincs_gomb":
            raise AppleHiba(
                "Nem találom a Szinkronizálás gombot az Apple Devices "
                "ablakában. Elképzelhető, hogy az Apple megváltoztatta a "
                "felületet, vagy nincs csatlakoztatva a telefon. A zene a gépi "
                "könyvtárba MÁR BEKERÜLT – az Apple Devices ablakában kézzel "
                "elindíthatod a szinkronizálást.")
        if hiba == "gomb_tiltva":
            raise AppleHiba(
                "A Szinkronizálás gomb most nem nyomható meg (nincs mit "
                "átvinni, vagy a telefon nem csatlakozik). A zene a gépi "
                "könyvtárba már bekerült.")
        raise AppleHiba("A szinkronizálás nem indult el.")
    return v


def szinkron_megerosit() -> dict:
    """Az Apple megerősítő kérdésének elfogadása.

    Amikor a zene-szinkron bekapcsol, az Apple Devices megkérdezi, hogy a
    telefon meglévő zenéjét eltávolíthatja-e. A felület EZT A KÉRDÉST a saját
    szavaival már feltette a felhasználónak – itt csak a válaszát adjuk tovább."""
    return _ps("megerosit")


def szinkron_leallit() -> dict:
    return _ps("leallit")


def teljes_lanc(utak: list, on_progress=None, megszakit=None,
                szinkronizaljon: bool = True) -> dict:
    """A teljes út: fájl → Apple Music könyvtár → telefon.

    Visszaad: {"behozva", "hibak", "szinkron"} – a `szinkron` mondja meg,
    sikerült-e elindítani az átvitelt. A behozatal akkor is siker, ha a
    szinkron elakad: a zene a gépi könyvtárban már ott van, és az Apple
    Devices ablakában kézzel is elindítható."""
    ok, hibak = behoz(utak, on_progress=on_progress, megszakit=megszakit)
    eredmeny = {"behozva": ok, "hibak": hibak, "szinkron": ""}
    if not ok or not szinkronizaljon:
        return eredmeny
    try:
        a = szinkron_allapot()
        if not a.get("van_eszkoz", True):
            # Ez fogott ki rajtunk a legtovább: amíg az Apple Devices nem látja
            # a telefont, a beállítás sem marad meg, és szinkron sem indul.
            raise AppleHiba(
                "Az Apple Devices most nem látja a telefont, ezért nem tudom "
                "átküldeni. Húzd ki és dugd vissza a kábelt (a telefon legyen "
                "feloldva), majd próbáld újra. A zene a gépi könyvtárba MÁR "
                "bekerült – nem veszett el.")
        if not a.get("bekapcsolva"):
            szinkron_bekapcsol()
            szinkron_megerosit()
        szinkronizal()
        eredmeny["szinkron"] = "elindult"
    except AppleHiba as ex:
        eredmeny["szinkron"] = str(ex)
    return eredmeny
