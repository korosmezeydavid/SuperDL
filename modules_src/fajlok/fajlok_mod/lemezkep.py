"""ISO csatolása a Windows Storage szolgáltatásával."""

from base64 import b64encode

import ctypes
import os
import string
import time
import re
import subprocess
from pathlib import Path

_STORAGE = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$p = $env:SUPERDL_ISO_PATH
$image = Get-DiskImage -ImagePath $p -StorageType ISO
if ($env:SUPERDL_ISO_ACTION -eq 'detach') {
    if ($image.Attached) { Dismount-DiskImage -ImagePath $p -StorageType ISO | Out-Null }
    if ((Get-DiskImage -ImagePath $p -StorageType ISO).Attached) {
        throw 'The image is still attached.'
    }
    return
}
if (!$image.Attached) {
    Mount-DiskImage -ImagePath $p -StorageType ISO | Out-Null
}
$image = Get-DiskImage -ImagePath $p -StorageType ISO
if (!$image.Attached) { throw 'The image is not attached.' }
Write-Output ([string]$image.DevicePath)
"""


def muvelet(fajl, levalaszt=False):
    path = Path(fajl).resolve()
    if not path.is_file() or path.suffix.lower() != ".iso":
        raise ValueError("Jelölj ki egy helyi ISO-fájlt.")
    powershell = (Path(os.environ["SystemRoot"]) / "System32" /
                  "WindowsPowerShell" / "v1.0" / "powershell.exe")
    env = dict(os.environ, SUPERDL_ISO_PATH=str(path),
               SUPERDL_ISO_ACTION="detach" if levalaszt else "attach")
    command = b64encode(_STORAGE.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-EncodedCommand", command],
        env=env, capture_output=True, text=True, errors="replace", timeout=40,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise OSError(result.stderr.strip() or "A Windows lemezkép-művelete sikertelen.")
    if levalaszt:
        return ""
    device = result.stdout.strip().rsplit(chr(92), 1)[-1]
    if not re.fullmatch(r"CDROM[0-9]+", device, re.IGNORECASE):
        raise OSError("A Windows nem adott virtuális DVD-eszközazonosítót.")
    target = (chr(92) + "Device" + chr(92) + device).casefold()
    query = ctypes.windll.kernel32.QueryDosDeviceW
    buffer = ctypes.create_unicode_buffer(4096)
    for _ in range(12):
        for letter in string.ascii_uppercase:
            if query(letter + ":", buffer, len(buffer)) and buffer.value.casefold() == target:
                return letter + ":" + chr(92)
        time.sleep(0.25)
    raise OSError("Az ISO csatolva van, de nincs meghajtóbetűjele. Leválaszthatod az ISO-fájlról.")
