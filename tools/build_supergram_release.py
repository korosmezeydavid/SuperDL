"""Build a self-contained Supergram ZIP from verified local TDLib packages.

The Telegram application ID/hash is deliberately read from a file outside the
repository and copied only into the release ZIP. Never commit the generated
ZIP or the private configuration file to source control.
"""

import argparse
import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path

from tools.build_module import build


DLL_HASHES = {
    "tdjson.dll": "AD1A96C4582E195DAA555733F78A45CDBD2F8038DE74E42D10B1A68E27CDD91D",
    "libcrypto-3-x64.dll": "97308FEEA369B305E562C0098638A1B02A06F52EE9FCC4B8CF3DA362FF563CF4",
    "libssl-3-x64.dll": "8B71CD694F8EDFBDDC76674111278DB6BCDCDE0DCD63B99238420193848E6DBF",
    "libgcc_s_seh-1.dll": "791EBF66E99C7C1B4ED3666468CEC45A0172B4C8942AC6C84C3E9CAB3E1B5270",
    "libstdc++-6.dll": "4E4822DC4AAA99383F581DAE7AB9464AE89346C5CA742F7EFBCDEBE20B0FE7B5",
    "libwinpthread-1.dll": "E765EE6109A0080A7C42848911F4349099B3C15AA734D845CB0E438F6F5A91B5",
    "zlib1.dll": "11CD91171765CD65F1C3362E3DF67E5F5A618A6B88C8CDEC899B802EAF1C7B0D",
}
LICENSE_FILES = {
    "tdlib/LICENSE_1_0.txt": "TDLib-Boost.txt",
    "tdlib/SQLCipher-LICENSE": "TDLib-SQLCipher.txt",
    "tdlib/tg_cli-GPL-3.0.txt": "TDLib-tg_cli-GPL-3.0.txt",
    "openssl/LICENSE": "OpenSSL.txt",
    "gcc/COPYING.RUNTIME": "GCC-Runtime-Exception.txt",
    "gcc/COPYING3": "GCC-GPL-3.0.txt",
    "libwinpthread/COPYING": "libwinpthread.txt",
    "zlib/LICENSE": "zlib.txt",
}


def _verified_dlls(source: Path, target: Path):
    target.mkdir(parents=True)
    for name, expected in DLL_HASHES.items():
        data = (source / name).read_bytes()
        if hashlib.sha256(data).hexdigest().upper() != expected:
            raise ValueError(f"Nem a rögzített, ellenőrzött TDLib-futásidő: {name}")
        (target / name).write_bytes(data)


def _public_credentials(path: Path) -> bytes:
    from modules_src.supergram.supergram_mod.protocol import load_credentials

    # This parser validates the ID/hash without printing either value.
    api_id, api_hash = load_credentials(path.parent)
    if not api_id or len(api_hash) != 32:
        raise ValueError("Hiányos Telegram projektazonosító.")
    data = path.read_bytes()
    if b"TELEGRAM_API_ID" not in data and b"telegram.api_id" not in data:
        raise ValueError("Nem található a projektazonosító.")
    return data


def release(source: Path, runtime: Path, licenses: Path, credentials: Path,
            output: Path):
    source, runtime, licenses, credentials = map(
        Path, (source, runtime, licenses, credentials))
    if credentials.name != "telegram.local.properties":
        raise ValueError("A kiadáshoz explicit telegram.local.properties fájl kell.")
    # Do not permit a stale package or transient local data in the source.
    forbidden = list(source.rglob("telegram.*.properties")) + list(source.rglob("*.dll"))
    if forbidden:
        raise ValueError("Helyi Telegram-adat vagy DLL található a forrásban.")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="supergram-release-", dir=output) as temp:
        stage = Path(temp) / "supergram"
        shutil.copytree(source, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # Git on Windows may check out CRLF while an isolated worktree or CI
        # uses LF. Normalize text inputs so the release hash is reproducible.
        for item in stage.rglob("*"):
            if item.is_file() and item.suffix in {".py", ".json"}:
                item.write_bytes(item.read_bytes().replace(b"\r\n", b"\n"))
        package = stage / "supergram_mod"
        (package / "telegram.public.properties").write_bytes(_public_credentials(credentials))
        _verified_dlls(runtime, package / "tdlib")
        license_target = package / "tdlib" / "licenses"
        license_target.mkdir()
        for relative, renamed in LICENSE_FILES.items():
            shutil.copy2(licenses / relative, license_target / renamed)
        artifact, sha, entry = build(str(stage), str(output))
        with zipfile.ZipFile(artifact) as archive:
            names = set(archive.namelist())
            assert "supergram_mod/telegram.public.properties" in names
            assert "supergram_mod/telegram.local.properties" not in names
            assert all("/db/" not in n and "/files/" not in n for n in names)
            assert all(f"supergram_mod/tdlib/{n}" in names for n in DLL_HASHES)
        return artifact, sha, entry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("modules_src/supergram"))
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--licenses", type=Path, required=True,
                        help="MSYS2 UCRT64 share/licenses directory")
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("dist_modules"))
    args = parser.parse_args()
    release(args.source, args.runtime, args.licenses, args.credentials, args.output)
