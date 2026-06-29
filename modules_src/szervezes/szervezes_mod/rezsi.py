"""Rezsi/költség-kalkulátor – adat + számítás (a naptár „Rezsi" füléhez).

Tételenként: név, összeg, gyakoriság (havi/heti/negyedéves/féléves/éves/egyszeri),
esedékesség (a hónap napja), megjegyzés. A kalkulátor HAVI és ÉVES összesítést ad,
és a naptárba emlékeztetőt tehet a következő esedékességre.

Opcionális PIN-LAKAT (max 6 számjegy): ha be van állítva, a fül adatai csak a
helyes PIN beírása után jelennek meg. A PIN-t SÓVAL hash-eljük (sosem nyersen).
Az adat a ~/.superdl mappában (felhasználói profil) tárolódik.
"""

import hashlib
import os
from dataclasses import asdict, dataclass, field

from superdl import store

REZSI_FILE = store.CONFIG_DIR / "rezsi.json"

# gyakoriság → HÁNY HAVI költségnek felel meg (az egyszeri nem havi: 0)
MONTHLY_MULT = {
    "havi": 1.0,
    "heti": 52.0 / 12.0,
    "negyedéves": 1.0 / 3.0,
    "féléves": 1.0 / 6.0,
    "éves": 1.0 / 12.0,
    "egyszeri": 0.0,
}
PERIODS = list(MONTHLY_MULT.keys())


@dataclass
class Item:
    name: str
    amount: float
    period: str = "havi"
    day: int = 1
    note: str = ""


@dataclass
class RezsiData:
    items: list = field(default_factory=list)     # list[Item]
    pin_hash: str = ""
    pin_salt: str = ""

    # ---- tárolás -----------------------------------------------------

    @classmethod
    def load(cls) -> "RezsiData":
        d = store.load_json(REZSI_FILE, {})
        items = [Item(**{k: it.get(k) for k in ("name", "amount", "period",
                                                "day", "note")})
                 for it in d.get("items", []) if it.get("name")]
        return cls(items=items, pin_hash=d.get("pin_hash", ""),
                   pin_salt=d.get("pin_salt", ""))

    def save(self):
        store.save_json(REZSI_FILE, {
            "items": [asdict(i) for i in self.items],
            "pin_hash": self.pin_hash, "pin_salt": self.pin_salt})

    # ---- számítás ----------------------------------------------------

    def monthly_total(self) -> float:
        """Az ISMÉTLŐDŐ tételek havi összege (az egyszeri NEM számít bele)."""
        return sum(i.amount * MONTHLY_MULT.get(i.period, 0.0) for i in self.items)

    def yearly_total(self) -> float:
        """Az ismétlődő tételek éves összege (havi × 12)."""
        return self.monthly_total() * 12.0

    def onetime_total(self) -> float:
        return sum(i.amount for i in self.items if i.period == "egyszeri")

    # ---- PIN-lakat ---------------------------------------------------

    @staticmethod
    def _hash(pin: str, salt: str) -> str:
        return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()

    def has_pin(self) -> bool:
        return bool(self.pin_hash)

    def set_pin(self, pin: str):
        """PIN beállítása (max 6 számjegy). Üres pin = lakat törlése."""
        if not pin:
            self.pin_hash = ""
            self.pin_salt = ""
        else:
            self.pin_salt = os.urandom(16).hex()
            self.pin_hash = self._hash(pin, self.pin_salt)
        self.save()

    def check_pin(self, pin: str) -> bool:
        return bool(self.pin_hash) and self._hash(pin, self.pin_salt) == self.pin_hash
