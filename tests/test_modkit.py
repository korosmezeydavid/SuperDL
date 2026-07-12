"""modkit: verzió-összevetés, manifest-érvényesítés, min_core_version lánc,
biztonságos telepítő (SHA-ellenőrzés + elutasítások)."""

import io
import json
import zipfile

import pytest

modkit = pytest.importorskip("superdl.modkit")


def _zip_module(manifest: dict, entry_files: dict | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        for arc, data in (entry_files or {}).items():
            z.writestr(arc, data)
    return buf.getvalue()


def _entry(**kw):
    base = dict(id="t", name="T", category="Egyéb", description="",
                version="1.0", min_core_api="1.0",
                url="https://example.com/x.zip", sha256="", size=1)
    base.update(kw)
    return modkit.ModuleEntry(**base)


# ---- verzió-összevetés -------------------------------------------------

@pytest.mark.parametrize("a,b,want", [
    ("1.1.0", "1.0.9", True),
    ("1.0.10", "1.0.9", True),      # számjegy-csoportos, nem szöveges
    ("1.0.9", "1.0.10", False),
    ("1.0.0", "1.0.0", False),      # egyenlő nem „újabb"
])
def test_version_gt(a, b, want):
    assert modkit.version_gt(a, b) is want


def test_core_version_ok():
    cur = modkit.current_core_version()
    assert modkit.core_version_ok("")            # üres = nincs megkötés
    assert modkit.core_version_ok(None)
    assert modkit.core_version_ok("3.0.0")
    assert modkit.core_version_ok(cur)           # pont a futó verzió
    assert not modkit.core_version_ok("99.0.0")


# ---- manifest ----------------------------------------------------------

def test_parse_manifest_ervenyes():
    m = modkit.parse_manifest({"id": "demo", "name": "Demó", "version": "1.2",
                               "entry": "demo_mod",
                               "min_core_version": "3.29.0"})
    assert m.id == "demo" and m.min_core_version == "3.29.0"


@pytest.mark.parametrize("rossz", [
    {},                                              # minden hiányzik
    {"id": "x", "name": "X", "version": "1"},        # nincs entry
    {"id": "Nagy Betű", "name": "X", "version": "1", "entry": "m"},  # rossz id
    {"id": "x", "name": "X", "version": "1", "entry": "1rossz"},     # rossz entry
])
def test_parse_manifest_hibas(rossz):
    with pytest.raises(modkit.ManifestError):
        modkit.parse_manifest(rossz)


# ---- modules.json / ModuleEntry ---------------------------------------

def test_parse_index_min_core_version():
    idx = {"modules": [{"id": "m1", "name": "M1", "latest": {
        "version": "1.0", "min_core_api": "1.0", "min_core_version": "99.0.0",
        "url": "https://e/x.zip", "sha256": "", "size": 1}}]}
    e = modkit.parse_index(idx)[0]
    assert e.min_core_version == "99.0.0"
    assert not e.compatible()


def test_module_entry_compatible():
    assert _entry().compatible()
    assert _entry(min_core_version="3.0.0").compatible()
    assert not _entry(min_core_version="99.0.0").compatible()
    assert not _entry(min_core_api="99.0").compatible()


# ---- biztonságos telepítő ---------------------------------------------

def test_install_sha_elteres_elutasit(tmp_path):
    data = _zip_module({"id": "m", "name": "M", "version": "1",
                        "entry": "m_mod"}, {"m_mod/__init__.py": ""})
    with pytest.raises(modkit.InstallError):
        modkit.install_module_zip(data, expected_sha256="0" * 64,
                                  root=tmp_path)


def test_install_min_core_version_elutasit(tmp_path):
    data = _zip_module({"id": "m", "name": "M", "version": "1",
                        "entry": "m_mod", "min_core_version": "99.0.0"},
                       {"m_mod/__init__.py": ""})
    with pytest.raises(modkit.InstallError) as ei:
        modkit.install_module_zip(data, root=tmp_path)
    assert "99.0.0" in str(ei.value)     # érthető üzenet a kért verzióval


def test_install_regi_manifest_megy(tmp_path):
    """min_core_version nélküli (régi) modul változatlanul telepíthető."""
    data = _zip_module({"id": "regi", "name": "Régi", "version": "1.0",
                        "entry": "regi_mod"},
                       {"regi_mod/__init__.py": "def register(core): pass\n"})
    man = modkit.install_module_zip(data, root=tmp_path)
    assert man.id == "regi"
    assert (tmp_path / "regi" / "manifest.json").is_file()


def test_install_zip_slip_elutasit(tmp_path):
    """Útvonalbejárásos (zip-slip) bejegyzés nem írhat a célmappán kívülre."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps(
            {"id": "gonosz", "name": "G", "version": "1", "entry": "g_mod"}))
        z.writestr("../kivul.txt", "szivárgás")
        z.writestr("g_mod/__init__.py", "")
    with pytest.raises(modkit.InstallError):
        modkit.install_module_zip(buf.getvalue(), root=tmp_path)
    assert not (tmp_path.parent / "kivul.txt").exists()
