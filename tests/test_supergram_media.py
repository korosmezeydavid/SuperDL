"""Hangüzenet és botgomb célzott, hálózat nélküli ellenőrzése."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import wx

from modules_src.supergram.supergram_mod import protocol
from modules_src.supergram.supergram_mod.window import SupergramFrame


class SupergramMediaTests(unittest.TestCase):
    def test_common_message_types_have_useful_labels(self):
        for kind, expected in (("messagePhoto", "Fénykép"),
                               ("messageSticker", "Matrica"),
                               ("messageLocation", "Megosztott helyzet")):
            label = protocol.message_label({"date": 0, "content": {"@type": kind}})
            self.assertIn(expected, label)
            self.assertNotIn("ismeretlen", label)
        poll = {"date": 0, "content": {"@type": "messagePoll",
                "poll": {"question": {"text": "Melyik?"}}}}
        self.assertIn("Szavazás: Melyik?", protocol.message_label(poll))

    def test_login_shows_only_the_required_field(self):
        app = wx.App.Get() or wx.App(False)
        with patch.object(SupergramFrame, "_diagnose", return_value=False):
            frame = SupergramFrame(None, None)
        try:
            frame._login_state("authorizationStateWaitPhoneNumber")
            self.assertTrue(frame.login.IsShown())
            self.assertFalse(frame.secret.IsShown())
            self.assertFalse(frame.chat_list.IsShown())
            frame._login_state("authorizationStateWaitCode")
            self.assertFalse(frame.login.IsShown())
            self.assertTrue(frame.secret.IsShown())
        finally:
            frame.Destroy()

    def test_only_chat_list_is_visible_until_chat_opens(self):
        app = wx.App.Get() or wx.App(False)
        with patch.object(SupergramFrame, "_diagnose", return_value=False):
            frame = SupergramFrame(None, None)
        try:
            requests = []
            frame._request = lambda request, context: requests.append((request, context))
            frame.Show()
            frame._auth({"@type": "authorizationStateReady"})
            frame._put_chat({"id": 42, "title": "Próba", "unread_count": 0})
            frame._put_chat({"id": 43, "title": "Másik", "unread_count": 0})
            wx.Yield()
            self.assertTrue(frame.chat_list.IsShown())
            self.assertFalse(frame.message_list.IsShown())
            self.assertFalse(frame.draft.IsShown())
            self.assertFalse(frame.login_button.IsShown())
            self.assertFalse(frame.connect.IsShown())
            self.assertFalse(frame.status.AcceptsFocus())
            focusable = {child for child in frame.panel.GetChildren()
                         if child.IsShown() and child.AcceptsFocus()}
            self.assertEqual(focusable, {frame.chat_search_button, frame.chat_list})
            self.assertIs(wx.Window.FindFocus(), frame.chat_list)
            frame._open_chat(None)
            wx.Yield()
            self.assertFalse(frame.chat_list.IsShown())
            self.assertTrue(frame.message_list.IsShown())
            self.assertTrue(frame.draft.IsShown())
            self.assertIs(wx.Window.FindFocus(), frame.draft)
            frame.draft.SetValue("Félbehagyott üzenet")
            frame._back_to_chats()
            wx.Yield()
            self.assertTrue(frame.chat_list.IsShown())
            self.assertFalse(frame.message_list.IsShown())
            self.assertIs(wx.Window.FindFocus(), frame.chat_list)
            frame.chat_list.SetSelection(1)
            frame._open_chat(None)
            self.assertEqual(frame.draft.GetValue(), "")
            frame._back_to_chats()
            frame.chat_list.SetSelection(0)
            frame._open_chat(None)
            self.assertEqual(frame.draft.GetValue(), "Félbehagyott üzenet")
            frame._send_text(None)
            frame._back_to_chats()
            frame.chat_list.SetSelection(1)
            frame._open_chat(None)
            frame.draft.SetValue("Másik beszélgetés új szövege")
            frame._complete_send(True)
            self.assertEqual(frame.draft.GetValue(), "Másik beszélgetés új szövege")
            self.assertEqual(frame.chat_drafts[42], "")
        finally:
            frame.Destroy()

    def test_callback_button_preserves_payload(self):
        button = {"text": "Következő", "type": {
            "@type": "inlineKeyboardButtonTypeCallback", "data": "AQID"}}
        message = {"id": 3, "reply_markup": {"@type": "replyMarkupInlineKeyboard",
                   "rows": [[button]]}}
        self.assertEqual(protocol.inline_buttons(message), [button])
        self.assertEqual(protocol.callback_button_request(5, 3, button), {
            "@type": "getCallbackQueryAnswer", "chat_id": 5, "message_id": 3,
            "payload": {"@type": "callbackQueryPayloadData", "data": "AQID"}})
        with self.assertRaises(ValueError):
            protocol.callback_button_request(5, 3, {"type": {
                "@type": "inlineKeyboardButtonTypeUrl", "url": "https://example.com"}})

    def test_voice_download_and_playback_toggle(self):
        app = wx.App.Get() or wx.App(False)
        with patch.object(SupergramFrame, "_diagnose", return_value=False):
            frame = SupergramFrame(None, None)
        try:
            requests = []
            frame._request = lambda request, context: requests.append((request, context))
            voice = {"id": 4, "content": {"@type": "messageVoiceNote",
                     "voice_note": {"voice": {"id": 9, "local": {}}}}}
            frame._play_message(voice)
            self.assertEqual(requests[-1][0]["@type"], "downloadFile")
            self.assertIn(9, frame.pending_playback)
            with TemporaryDirectory(dir=Path(__file__).parent) as directory:
                path = Path(directory) / "voice.ogg"
                path.write_bytes(b"test")
                played = []

                class FakePlayer:
                    def play(self, *args):
                        played.append(args)

                    def stop(self):
                        played.append("stop")

                frame.audio_player = FakePlayer()
                frame._download_progress({"id": 9, "local": {
                    "is_downloading_completed": True, "path": str(path)}})
                self.assertEqual(played[0][0], str(path))
                self.assertEqual(frame.playing_file_id, 9)
                frame._play_message(voice)
                self.assertEqual(played[-1], "stop")
                self.assertEqual(frame.playing_file_id, 0)
        finally:
            frame.Destroy()


if __name__ == "__main__":
    unittest.main()
