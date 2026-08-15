"""„Összes frissítése" a Modulkezelőben – Laci észrevételéből.

Laci jelezte, hogy a „Frissítés a boltból" gomb neve félrevezető (nem modult
frissít, hanem a KÍNÁLATOT tölti újra), és hogy a modulokat egyesével frissíteni
kínszenvedés. Kérése: legyen egy gomb, ami az ÖSSZES, MÁR TELEPÍTETT modult
frissíti.

Amit ezek a tesztek őriznek:
  • csak a TELEPÍTETT és valóban frissíthető modulok kerülnek bele (nem
    telepítjük fel, ami a felhasználónak nem kell);
  • az újratelepítéses tartalék (fájlzár-csapda) a HELYES SORRENDBEN dolgozik:
    ELŐBB letölt, csak AZUTÁN töröl – különben egy megszakadó net elvinné a
    modult;
  • a modul-frissítés figyelése csak a szigorúan ÚJABB verziót jelzi;
  • az újraindító kötegfájl megvárja a régi példány kilépését (a SuperDL
    egypéldányos: azonnali indításnál a második példány csendben kilépne).
"""

import types

import pytest

from superdl import coremod
from superdl import modmanagerwin as M


def _sor(nev, statusz, entry=object(), installable=True):
    return dict(id=nev.lower(), name=nev, category="Egyéb", status=statusz,
                version="1.0.0", entry=entry, installable=installable,
                removable=True)


# ------------------------------------------------- melyik sorokat érinti

def test_csak_a_telepitett_frissithetoket_valasztja_ki():
    rows = [_sor("Könyvek", "Frissíthető"),
            _sor("Rádió", "Telepítve", installable=False),
            _sor("Játékok", "Elérhető"),            # nincs telepítve → NEM
            _sor("Régi", "Telepítve (helyi)", entry=None, installable=False),
            _sor("Túl új", "Újabb SuperDL kell", installable=False)]
    nevek = [r["name"] for r in M.frissitheto_sorok(rows)]
    assert nevek == ["Könyvek"], \
        "csak a telepített, frissíthető modul kerülhet bele"


def test_ures_es_hianyos_bemenetre_sem_dol_el():
    assert M.frissitheto_sorok([]) == []
    assert M.frissitheto_sorok(None) == []
    assert M.frissitheto_sorok([{"status": "Frissíthető"}]) == [], \
        "bolt-bejegyzés nélkül nem frissíthető"


# ------------------------------------------ újratelepítés (fájlzár-tartalék)

class _HamisBejegyzes:
    id = "konyvek"
    name = "Könyvek"
    version = "1.3.0"
    url = "https://pelda/konyvek-1.3.0.zip"
    sha256 = "abc"


class _HamisLoader:
    def __init__(self, betolt_ok=True):
        self.betolt_ok = betolt_ok
        self.errors = {}
        self.unloaded = []

    def unload(self, mid):
        self.unloaded.append(mid)
        return True

    def load_dir(self, d):
        return object() if self.betolt_ok else None


def test_ujratelepites_eloszor_tolt_le_es_csak_utana_torol(monkeypatch, tmp_path):
    """A SORREND ÉLETBEVÁGÓ: ha előbb törölnénk, egy megszakadó letöltés a modul
    ELVESZTÉSÉT jelentené."""
    naplo = []
    monkeypatch.setattr(coremod, "download_bytes",
                        lambda url, prog=None: naplo.append("letoltes") or b"ZIP")
    monkeypatch.setattr(coremod, "remove_module",
                        lambda loader, mid, root=None: naplo.append("torles"))
    monkeypatch.setattr(coremod.modkit, "install_module_zip",
                        lambda data, sha, root, keep_backup=False:
                        naplo.append("telepites")
                        or types.SimpleNamespace(id="konyvek", name="Könyvek",
                                                 version="1.3.0"))
    man = coremod.reinstall_entry(_HamisLoader(), _HamisBejegyzes(),
                                  root=tmp_path)
    assert naplo == ["letoltes", "torles", "telepites"]
    assert man.version == "1.3.0"


def test_ujratelepites_hibat_dob_ha_az_uj_modul_nem_toltodik_be(monkeypatch,
                                                               tmp_path):
    monkeypatch.setattr(coremod, "download_bytes", lambda url, prog=None: b"ZIP")
    monkeypatch.setattr(coremod, "remove_module",
                        lambda loader, mid, root=None: True)
    monkeypatch.setattr(coremod.modkit, "install_module_zip",
                        lambda *a, **kw: types.SimpleNamespace(
                            id="konyvek", name="Könyvek", version="1.3.0"))
    with pytest.raises(RuntimeError):
        coremod.reinstall_entry(_HamisLoader(betolt_ok=False),
                                _HamisBejegyzes(), root=tmp_path)


# --------------------------------------------- modul-frissítések figyelése

def _bejegyzes(mid, verzio, min_core="1.0.0"):
    e = types.SimpleNamespace(id=mid, name=mid.capitalize(), version=verzio,
                              min_core_version=min_core)
    e.compatible = lambda api: True
    return e


def _telepit(tmp_path, mid, verzio):
    d = tmp_path / mid
    d.mkdir()
    (d / "manifest.json").write_text(
        '{"id": "%s", "name": "%s", "version": "%s", "entry": "%s_mod"}'
        % (mid, mid, verzio, mid), encoding="utf-8")


def test_csak_a_szigoruan_ujabb_verziot_jelzi(tmp_path):
    _telepit(tmp_path, "konyvek", "1.2.0")
    _telepit(tmp_path, "radio", "1.1.8")
    talalt = coremod.modul_frissitesek(
        root=tmp_path, entries=[_bejegyzes("konyvek", "1.3.0"),
                                _bejegyzes("radio", "1.1.7"),      # RÉGEBBI
                                _bejegyzes("jatekok", "2.0.0")])   # nincs fent
    assert [t[0] for t in talalt] == ["konyvek"]
    assert talalt[0][2] == "1.3.0"


def test_nincs_telepitett_modul_eseten_ures(tmp_path):
    assert coremod.modul_frissitesek(root=tmp_path,
                                     entries=[_bejegyzes("konyvek", "9.9.9")]) == []


def test_serult_manifest_nem_dont_el_mindent(tmp_path):
    _telepit(tmp_path, "konyvek", "1.2.0")
    rossz = tmp_path / "romlott"
    rossz.mkdir()
    (rossz / "manifest.json").write_text("{ez nem json", encoding="utf-8")
    talalt = coremod.modul_frissitesek(root=tmp_path,
                                       entries=[_bejegyzes("konyvek", "1.3.0")])
    assert [t[0] for t in talalt] == ["konyvek"], \
        "egy romlott manifest nem viheti el a többi ellenőrzését"


def test_a_tul_uj_modult_nem_ajanlja_fel(tmp_path, monkeypatch):
    """Ha a modul újabb PROGRAM-verziót kér, mint ami fut, azt ne ígérjük oda:
    a telepítése úgyis elbukna."""
    _telepit(tmp_path, "konyvek", "1.2.0")
    monkeypatch.setattr(coremod.modkit, "core_version_ok",
                        lambda v: not v.startswith("99"))
    talalt = coremod.modul_frissitesek(
        root=tmp_path, entries=[_bejegyzes("konyvek", "1.3.0",
                                           min_core="99.0.0")])
    assert talalt == []


# ------------------------------------------------------- újraindítás

def test_az_ujrainditas_megvarja_a_regi_peldany_kilepeset():
    from pathlib import Path
    script = coremod._restart_script(Path(r"C:\Prog\SuperDL.exe"), 4242)
    assert "tasklist.exe" in script and "4242" in script, \
        "a régi példányra VÁRNI kell (egypéldányos mutex)"
    assert script.index("4242") < script.index("start "), \
        "előbb a várakozás, csak utána az indítás"
    assert r"start \"\" \"C:\Prog\SuperDL.exe\"".replace("\\\"", '"') in script
    assert "del " in script, "a kötegfájl takarítsa el magát"


def test_restart_app_forrasbol_futva_nem_probalkozik(monkeypatch):
    """Fejlesztés közben (nem exe) ne írjon kötegfájlt és ne indítson semmit."""
    import sys
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert coremod.restart_app() is False
