"""Közös teszt-alap: a repó gyökere kerüljön a sys.path-ra, hogy a `superdl`
csomag és a `modules_src` (névtér-csomagként) importálható legyen a tesztekből,
telepítés nélkül."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
