"""Ordinary Del in the combined inbox must use the message account's Trash."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modules_src.mail.mail_mod import mailwin as MW


class CombinedDeleteTest(unittest.TestCase):
    def test_del_moves_to_own_accounts_trash(self):
        first = {"email": "first@example.com"}
        second = {"email": "second@example.com"}
        message = {"uid": "42", "_fiok": second, "_mappa": "INBOX",
                   "felado": "Sender", "targy": "Subject"}
        actions = []

        class Client:
            def kapcsolodik(self):
                return self

            def mappak(self):
                return ["INBOX", "Trash"]

            def athelyez(self, uid, dest, source):
                actions.append(("move", uid, dest, source))
                return True

            def torol(self, uid, source):
                actions.append(("delete", uid, source))

            def bezar(self):
                pass

        class List:
            def Set(self, rows):
                pass

            def SetSelection(self, index):
                pass

        frame = SimpleNamespace(
            _torles_folyamatban=False, _closing=False,
            _lista=[message], _aktiv=first, _mappa=MW.MC.OSSZES_MAPPA,
            _kivalasztottak=lambda: [message],
            _elso_kijelolt_index=lambda: 0,
            _kuka_mappa=lambda: None,
            _mond=lambda value: None,
            _sor_szoveg=lambda value: value["targy"],
            _halo_hiba=lambda ex: self.fail(str(ex)),
            level_lista=List(),
        )

        def run(work, done, error):
            try:
                done(work())
            except Exception as exc:
                error(exc)

        with patch.object(MW, "_kliens", return_value=Client()), \
             patch.object(MW, "_hatterben", side_effect=run):
            MW.MailFrame._torol(frame, None)

        self.assertEqual(actions, [("move", "42", "Trash", "INBOX")])
        self.assertFalse(frame._torles_folyamatban)


if __name__ == "__main__":
    unittest.main()
