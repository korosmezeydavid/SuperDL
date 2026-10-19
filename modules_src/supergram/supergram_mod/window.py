"""Akadálymentes Windowsos Telegram-alap: belépés, chat és szöveg."""

import os
import shutil
import threading
import uuid
import winsound
from pathlib import Path

import wx

from . import protocol
from .recording import VoiceRecorder
from .tdlib_loader import TdlibUnavailable, load_tdlib
from .transport import TdTransport


class SupergramFrame(wx.Frame):
    def __init__(self, parent, core):
        super().__init__(parent, title="Supergram – Telegram", size=(720, 620))
        self.core = core
        self.root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "SuperDL" / "Telegram"
        self.transport = None
        self.state = ""
        self.chats = {}
        self.chat_ids = []
        self.all_chat_ids = []
        self.archive_chat_ids = []
        self.folder_chat_ids = {}
        self.chat_folders = {}
        self.chat_scope = "main"
        self.chat_folder_id = 0
        self.notifications_enabled = bool(core.store.load("notification_sound", True)) if core else True
        self.notified_message_ids = set()
        self.recorder = None
        self.recorded_voice = None
        self.recorded_voice_chat_id = 0
        self.search_chat_ids = None
        self.unread_chats_only = False
        self.chat_search_generation = 0
        self._announced_chat_count = -1
        self.chat_id = 0
        self.chat_drafts = {}
        self.messages = []
        self.message_search_active = False
        self.message_search_generation = 0
        self.reply_to_message_id = 0
        self.history_generation = 0
        self.history_loading = False
        self.history_exhausted = False
        self.initial_history_target = 50
        self.focus_draft_after_open = False
        self.viewed_message_ids = set()
        self.pending_downloads = {}
        self.pending_playback = set()
        self.audio_player = None
        self.playing_file_id = 0
        self.pending = {}
        self.sending = False
        self.sending_kind = ""
        self.sending_chat_id = 0
        self.sending_text = ""
        self.pending_message_id = 0
        self.terminal_sends = {}
        self.closing = False
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(panel, label="Supergram – független Telegram-kliens"), 0, wx.ALL, 8)
        self.status = wx.StaticText(panel, label="")
        self.status.SetName("Supergram állapota")
        layout.Add(self.status, 0, wx.EXPAND | wx.ALL, 8)
        login = wx.BoxSizer(wx.HORIZONTAL)
        self.login_label = wx.StaticText(panel, label="Belépés:")
        self.login = wx.TextCtrl(panel)
        self.secret = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        self.login.SetName("Telefonszám vagy e-mail-cím")
        self.secret.SetName("Telegram belépési kód vagy jelszó")
        self.login_button = wx.Button(panel, label="&Belépési adat elküldése")
        self.login_button.Bind(wx.EVT_BUTTON, self._submit_login)
        for control in (self.login_label, self.login, self.secret, self.login_button):
            login.Add(control, 1 if control in (self.login, self.secret) else 0,
                      wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
        layout.Add(login, 0, wx.EXPAND | wx.ALL, 8)
        lists = wx.BoxSizer(wx.HORIZONTAL)
        self.chat_list = wx.ListBox(panel)
        self.message_list = wx.ListBox(panel)
        self.chat_search = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.chat_search.Hide()
        self.message_search = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.message_search.Hide()
        self.chat_list.SetName("Beszélgetések; Enter: megnyitás; Ctrl U: olvasatlan szűrő")
        self.message_list.SetName("Üzenetek; fel és le nyíllal olvashatók")
        self.chat_list.Bind(wx.EVT_LISTBOX_DCLICK, self._open_chat)
        self.chat_list.Bind(wx.EVT_KEY_DOWN, self._chat_key)
        self.chat_list.Bind(wx.EVT_RIGHT_DOWN, self._chat_right_down)
        self.chat_list.Bind(wx.EVT_CONTEXT_MENU, self._chat_menu)
        self.message_list.Bind(wx.EVT_LISTBOX, self._message_selected)
        self.message_list.Bind(wx.EVT_KEY_DOWN, self._message_key)
        self.message_list.Bind(wx.EVT_CHAR_HOOK, self._message_char_hook)
        self.message_list.Bind(wx.EVT_LISTBOX_DCLICK, self._message_activated)
        self.message_list.Bind(wx.EVT_CONTEXT_MENU, self._message_menu)
        self.message_list.Bind(wx.EVT_RIGHT_DOWN, self._message_right_down)
        self.Bind(wx.EVT_CHAR_HOOK, self._shortcuts)
        chats_column = wx.BoxSizer(wx.VERTICAL)
        chats_column.Add(wx.StaticText(panel, label="Beszélgetések – Enter vagy jobbra: megnyitás"),
                         0, wx.BOTTOM, 4)
        self.chat_search_button = wx.Button(panel, label="Beszélgetés keresése…")
        self.chat_search_button.Bind(wx.EVT_BUTTON, self._prompt_chat_search)
        chats_column.Add(self.chat_search_button, 0, wx.EXPAND | wx.BOTTOM, 4)
        chats_column.Add(self.chat_list, 1, wx.EXPAND)
        messages_column = wx.BoxSizer(wx.VERTICAL)
        messages_column.Add(wx.StaticText(panel, label="Üzenetek – fel/le: olvasás, balra: beszélgetések"),
                            0, wx.BOTTOM, 4)
        self.message_search_button = wx.Button(panel, label="Üzenet keresése…")
        self.message_search_button.Bind(wx.EVT_BUTTON, self._prompt_message_search)
        messages_column.Add(self.message_search_button, 0, wx.EXPAND | wx.BOTTOM, 4)
        messages_column.Add(self.message_list, 1, wx.EXPAND)
        lists.Add(chats_column, 1, wx.EXPAND | wx.RIGHT, 8)
        lists.Add(messages_column, 2, wx.EXPAND)
        layout.Add(lists, 1, wx.EXPAND | wx.ALL, 8)
        self.older_button = wx.Button(panel, label="&Régebbi üzenetek betöltése")
        self.older_button.SetName("Régebbi üzenetek betöltése a kijelölt beszélgetésben")
        self.older_button.Bind(wx.EVT_BUTTON, self._load_older)
        layout.Add(self.older_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.save_button = wx.Button(panel, label="Kijelölt &fájl mentése…")
        self.save_button.SetName("Kijelölt üzenet fájljának letöltése és mentése")
        self.save_button.Bind(wx.EVT_BUTTON, self._save_attachment)
        layout.Add(self.save_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        compose = wx.BoxSizer(wx.HORIZONTAL)
        self.draft = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.draft.SetName("Új Telegram-üzenet. Enter: küldés, Shift Enter: új sor, Shift Tab: előzmények")
        self.draft.SetHelpText("Enter küld; Shift Enter új sort ír; Shift Tab az előzményekre lép.")
        self.draft.Bind(wx.EVT_KEY_DOWN, self._draft_key)
        self.send_button = wx.Button(panel, label="&Küldés")
        self.send_button.Bind(wx.EVT_BUTTON, self._send_text)
        compose.Add(self.draft, 1, wx.EXPAND | wx.RIGHT, 8)
        compose.Add(self.send_button, 0, wx.ALIGN_BOTTOM)
        layout.Add(compose, 0, wx.EXPAND | wx.ALL, 8)
        self.file_button = wx.Button(panel, label="&Fájl küldése…")
        self.file_button.SetName("Fájl kiválasztása és küldése jóváhagyással")
        self.file_button.Bind(wx.EVT_BUTTON, self._send_document)
        layout.Add(self.file_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.voice_button = wx.Button(panel, label="Hangüzenet rögzítése")
        self.voice_button.SetName("Hangüzenet rögzítése; újabb aktiválásra leáll")
        self.voice_button.Bind(wx.EVT_BUTTON, self._voice_button)
        layout.Add(self.voice_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.connect = wx.Button(panel, label="&Telegram-kapcsolat indítása")
        self.connect.Bind(wx.EVT_BUTTON, self._connect)
        layout.Add(self.connect, 0, wx.ALL, 8)
        self.panel = panel
        self.main_layout = layout
        self.login_row = login
        self.lists = lists
        self.chats_column = chats_column
        self.messages_column = messages_column
        self.compose_row = compose
        panel.SetSizer(layout)
        self.Bind(wx.EVT_CLOSE, self._close)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._destroyed)
        self._login_state("")
        self._ready(False)
        if self._diagnose():
            # A tárolt munkamenet felélesztése nem igényel külön gombnyomást.
            wx.CallAfter(self._connect, None)
        else:
            self.connect.SetFocus()

    def _status(self, text):
        if not self.closing:
            self.status.SetLabel(text)
            self.panel.Layout()

    def _set_view(self):
        """Csak a használható nézet vezérlői legyenek láthatók és fókuszolhatók."""
        ready = self.state == "authorizationStateReady"
        opened = ready and bool(self.chat_id)
        login_needed = self.state in {
            "authorizationStateWaitPhoneNumber", "authorizationStateWaitEmailAddress",
            "authorizationStateWaitCode", "authorizationStateWaitEmailCode",
            "authorizationStateWaitPassword"}
        self.main_layout.Show(self.login_row, login_needed, recursive=True)
        secret_needed = self.state in {
            "authorizationStateWaitCode", "authorizationStateWaitEmailCode",
            "authorizationStateWaitPassword"}
        self.login.Show(login_needed and not secret_needed)
        self.secret.Show(login_needed and secret_needed)
        self.main_layout.Show(self.lists, ready, recursive=True)
        self.lists.Show(self.chats_column, ready and not opened, recursive=True)
        self.lists.Show(self.messages_column, opened, recursive=True)
        self.main_layout.Show(self.older_button, opened)
        self.main_layout.Show(self.save_button, opened)
        self.main_layout.Show(self.compose_row, opened, recursive=True)
        self.main_layout.Show(self.file_button, opened)
        self.main_layout.Show(self.voice_button, opened)
        self.main_layout.Show(self.connect, not ready and not login_needed)
        self.panel.Layout()
        self.Layout()

    def _diagnose(self):
        try:
            load_tdlib()
            protocol.load_credentials(self.root)
        except TdlibUnavailable as exc:
            self._status(str(exc))
            self.connect.Enable(False)
        except (OSError, ValueError, TypeError):
            self._status("A helyi Telegram API-konfiguráció hiányzik vagy hibás.")
            self.connect.Enable(False)
        else:
            self._status("Telegram-motor és konfiguráció elérhető. Kapcsolódás…")
            return True
        return False

    def _ready(self, enabled):
        for control in (self.chat_search_button, self.message_search_button,
                        self.chat_list, self.message_list, self.older_button,
                        self.save_button,
                        self.draft, self.send_button, self.file_button, self.voice_button):
            control.Enable(enabled)
        if enabled:
            self._update_older_button()

    def _request(self, request, context):
        extra = self.transport.send(request)
        self.pending[extra] = context

    def _connect(self, _event):
        if self.transport and self.transport.running:
            return
        try:
            self.transport = TdTransport(load_tdlib(),
                lambda e: wx.CallAfter(self._event, e),
                lambda x, e: wx.CallAfter(self._response, x, e))
            self.transport.start()
            self._request({"@type": "getAuthorizationState"}, "auth")
            self.connect.Enable(False)
            self._status("Kapcsolódás…")
        except (TdlibUnavailable, RuntimeError) as exc:
            self._status(str(exc))
            self.connect.Enable(True)

    def _login_state(self, state):
        self.state = state
        fields = {
            "authorizationStateWaitPhoneNumber": ("Telefonszám országkóddal:", False),
            "authorizationStateWaitEmailAddress": ("E-mail-cím:", False),
            "authorizationStateWaitCode": ("Telegram-kód:", True),
            "authorizationStateWaitEmailCode": ("E-mail-kód:", True),
            "authorizationStateWaitPassword": ("Kétlépcsős jelszó:", True),
        }
        label, secret = fields.get(state, ("Belépés:", False))
        self.login_label.SetLabel(label)
        self.login.Show(state in fields and not secret)
        self.secret.Show(state in fields and secret)
        self.login_button.Enable(state in fields)
        self._set_view()
        if state in fields:
            self._status(label)
            (self.secret if secret else self.login).SetFocus()

    def _submit_login(self, _event):
        ctrl = self.secret if self.secret.IsShown() else self.login
        try:
            self._request(protocol.login_request(self.state, ctrl.GetValue()), "login")
            ctrl.Clear()
            self._status("Belépési adat elküldve; válaszra várunk.")
        except (ValueError, RuntimeError) as exc:
            self._status(str(exc))

    def _auth(self, event):
        state = event.get("@type", "")
        if state == "authorizationStateWaitTdlibParameters":
            try:
                api_id, api_hash = protocol.load_credentials(self.root)
                self.root.mkdir(parents=True, exist_ok=True)
                self._request(protocol.parameters(api_id, api_hash, self.root), "parameters")
            except (OSError, ValueError, TypeError):
                self._status("Nem olvasható a helyi Telegram API-konfiguráció.")
        elif state == "authorizationStateReady":
            if self.state == state:
                return
            self._login_state("")
            self.state = state
            self._announced_chat_count = -1
            self._ready(True)
            self._set_view()
            # A kód/jelszó mező elrejtése után a fókusz egy láthatatlan
            # vezérlőn maradhat; a lista akkor is fókuszt kap, ha még üres.
            self.chat_list.SetFocus()
            self._status("Bejelentkezve. Beszélgetések betöltése…")
            self._request({"@type": "loadChats", "chat_list": None, "limit": 50}, "load")
        elif state == "authorizationStateWaitOtherDeviceConfirmation":
            self._login_state("")
            self._status("Hagyd jóvá a bejelentkezést a másik Telegram-eszközön.")
        elif state.startswith("authorizationStateWait"):
            self._login_state(state)
            if not self.login_button.IsEnabled():
                self._status("A Telegram egyelőre nem támogatott belépési lépést kér.")
        elif state in ("authorizationStateClosed", "authorizationStateClosing"):
            self.chat_id = 0
            self.messages = []
            self.message_list.Clear()
            self._ready(False)
            self._login_state("")
            self._status("Telegram-kapcsolat lezárva.")
            self.connect.Enable(True)

    def _event(self, event):
        if self.closing:
            return
        kind = event.get("@type")
        if kind == "updateAuthorizationState":
            self._auth(event.get("authorization_state") or {})
        elif kind == "transportError":
            self.chat_id = 0
            self.messages = []
            self.message_list.Clear()
            self._ready(False)
            self._login_state("")
            self._status("A Telegram-kapcsolat megszakadt.")
            self.connect.Enable(True)
        elif kind == "updateNewChat":
            self._put_chat(event.get("chat") or {})
        elif kind == "updateChatFolders":
            folders = event.get("chat_folders") or []
            self.chat_folders = {int(folder["id"]): folder for folder in folders
                                 if int(folder.get("id") or 0) > 0}
            self.folder_chat_ids = {folder_id: self.folder_chat_ids.get(folder_id, [])
                                    for folder_id in self.chat_folders}
            if self.chat_scope == "folder" and self.chat_folder_id not in self.chat_folders:
                self.chat_scope, self.chat_folder_id = "main", 0
            self._apply_chat_filter()
        elif kind in ("updateChatPosition", "updateChatAddedToList", "updateChatRemovedFromList"):
            chat_id = int(event.get("chat_id") or 0)
            if chat_id:
                self._request({"@type": "getChat", "chat_id": chat_id}, "chat")
        elif kind in ("updateChatTitle", "updateChatReadInbox", "updateChatLastMessage"):
            chat_id = int(event.get("chat_id") or 0)
            if chat_id:
                self._request({"@type": "getChat", "chat_id": chat_id}, "chat")
        elif kind == "updateNewMessage":
            msg = event.get("message") or {}
            self._notify_message(msg)
            new_chat_id = int(msg.get("chat_id") or 0)
            if new_chat_id and new_chat_id != self.chat_id:
                self._request({"@type": "getChat", "chat_id": new_chat_id}, "chat")
            if int(msg.get("chat_id") or 0) == self.chat_id and not self.message_search_active:
                self.messages = protocol.merge_messages(self.messages, [msg])
                self._render_messages(keep_focus=True)
                self._update_older_button()
        elif kind == "updateMessageContent" and not self.message_search_active:
            message_id = int(event.get("message_id") or 0)
            if int(event.get("chat_id") or 0) == self.chat_id:
                for message in self.messages:
                    if int(message.get("id") or 0) == message_id:
                        message["content"] = event.get("new_content") or message.get("content")
                        self._render_messages(keep_focus=True)
                        break
        elif kind == "updateFile":
            self._download_progress(event.get("file") or {})
        elif kind == "updateMessageSendSucceeded":
            old_id = int(event.get("old_message_id") or 0)
            if self.sending and old_id:
                if old_id == self.pending_message_id:
                    self._complete_send(True)
                else:
                    self.terminal_sends[old_id] = True
        elif kind == "updateMessageSendFailed":
            old_id = int(event.get("old_message_id") or 0)
            if self.sending and old_id:
                if old_id == self.pending_message_id:
                    self._complete_send(False)
                else:
                    self.terminal_sends[old_id] = False

    def _complete_send(self, success):
        self.sending = False
        self.pending_message_id = 0
        self.terminal_sends.clear()
        self.send_button.Enable(True)
        self.file_button.Enable(True)
        self.voice_button.Enable(True)
        if success:
            if self.sending_kind == "text":
                if (self.chat_id == self.sending_chat_id and
                        self.draft.GetValue() == self.sending_text):
                    self.draft.Clear()
                    self.reply_to_message_id = 0
                if self.chat_drafts.get(self.sending_chat_id) == self.sending_text:
                    self.chat_drafts[self.sending_chat_id] = ""
            if self.sending_kind == "voice" and self.recorded_voice:
                self.recorded_voice[0].unlink(missing_ok=True)
                self.recorded_voice = None
                self.recorded_voice_chat_id = 0
            self._status("A hangüzenet elküldve." if self.sending_kind == "voice" else
                         "A fájl elküldve." if self.sending_kind == "file" else
                         "Az üzenet elküldve.")
        else:
            self._status("A hangüzenet küldése sikertelen. A felvétel újrapróbálható." if
                         self.sending_kind == "voice" else
                         "A fájlküldés sikertelen. A helyi fájl megmaradt." if
                         self.sending_kind == "file" else
                         "A küldés sikertelen. A szöveg megmaradt újrapróbáláshoz.")
        self.sending_kind = ""
        self.sending_chat_id = 0
        self.sending_text = ""

    def _response(self, extra, event):
        if self.closing:
            return
        context = self.pending.pop(extra, None)
        if event.get("@type") == "error":
            if context == "load":
                # A TDLib a már teljesen betöltött listánál 404-et is adhat.
                self._request({"@type": "getChats", "chat_list": None, "limit": 50}, "chats")
                return
            if context == "load_archive":
                self._request({"@type": "getChats", "chat_list": {
                    "@type": "chatListArchive"}, "limit": 100}, "archive_chats")
                return
            if isinstance(context, tuple) and context[0] == "load_folder":
                folder_id = context[1]
                self._request({"@type": "getChats", "chat_list": {
                    "@type": "chatListFolder", "chat_folder_id": folder_id},
                    "limit": 100}, ("folder_chats", folder_id))
                return
            if isinstance(context, tuple) and context[0] == "history" and context[1] == self.chat_id:
                self.history_loading = False
                self._update_older_button()
            if isinstance(context, tuple) and context[0] == "open" and context[1] == self.chat_id:
                self.history_loading = False
                self._update_older_button()
            if isinstance(context, tuple) and context[0] == "download":
                self.pending_downloads.pop(context[1], None)
            if isinstance(context, tuple) and context[0] == "play_download":
                self.pending_playback.discard(context[1])
            if context == "send":
                self.sending = False
                self.send_button.Enable(True)
                self.file_button.Enable(True)
                self.voice_button.Enable(True)
                self.sending_kind = ""
                self.sending_chat_id = 0
                self.sending_text = ""
            if isinstance(context, tuple) and context[0] == "search_chats":
                self.chat_list.Enable(True)
            detail = event.get("message") or f"hibakód {event.get('code', '?')}"
            self._status("Telegram-hiba: " + str(detail))
        elif context == "auth":
            self._auth(event)
        elif context == "load":
            self._request({"@type": "getChats", "chat_list": None, "limit": 50}, "chats")
        elif context == "chats":
            self.all_chat_ids = [int(x) for x in event.get("chat_ids", [])]
            self._apply_chat_filter()
            if not self.chat_ids:
                self._status("Bejelentkezve. Nincs megjeleníthető beszélgetés.")
            for chat_id in self.chat_ids:
                self._request({"@type": "getChat", "chat_id": chat_id}, "chat")
        elif context == "load_archive":
            self._request({"@type": "getChats", "chat_list": {
                "@type": "chatListArchive"}, "limit": 100}, "archive_chats")
        elif context == "archive_chats":
            self.archive_chat_ids = [int(x) for x in event.get("chat_ids", [])]
            self._apply_chat_filter()
            for chat_id in self.archive_chat_ids:
                if chat_id not in self.chats:
                    self._request({"@type": "getChat", "chat_id": chat_id}, "chat")
            self.chat_list.SetFocus()
            self._status(f"Archívum: {len(self.chat_ids)} beszélgetés. Ctrl L: főlista.")
        elif isinstance(context, tuple) and context[0] == "load_folder":
            folder_id = context[1]
            self._request({"@type": "getChats", "chat_list": {
                "@type": "chatListFolder", "chat_folder_id": folder_id},
                "limit": 100}, ("folder_chats", folder_id))
        elif isinstance(context, tuple) and context[0] == "folder_chats":
            folder_id = context[1]
            if folder_id not in self.chat_folders:
                return
            self.folder_chat_ids[folder_id] = [int(x) for x in event.get("chat_ids", [])]
            if self.chat_scope == "folder" and self.chat_folder_id == folder_id:
                self._apply_chat_filter()
                self.chat_list.SetFocus()
                self._status(f"{self._folder_name(folder_id)}: {len(self.chat_ids)} beszélgetés.")
            for chat_id in self.folder_chat_ids[folder_id]:
                if chat_id not in self.chats:
                    self._request({"@type": "getChat", "chat_id": chat_id}, "chat")
        elif context == "chat":
            self._put_chat(event)
        elif isinstance(context, tuple) and context[0] == "search_chats":
            _, generation = context
            if generation != self.chat_search_generation:
                return
            self.search_chat_ids = [int(x) for x in event.get("chat_ids", [])]
            self._apply_chat_filter()
            for chat_id in self.search_chat_ids:
                if chat_id not in self.chats:
                    self._request({"@type": "getChat", "chat_id": chat_id}, "chat")
            self.chat_list.SetFocus()
            self._status(f"{len(self.chat_ids)} beszélgetés látható a szűrés után.")
        elif isinstance(context, tuple) and context[0] == "search_messages":
            _, chat_id, generation, search_generation = context
            if (chat_id != self.chat_id or generation != self.history_generation or
                    search_generation != self.message_search_generation):
                return
            self.message_search_active = True
            self.messages = protocol.merge_messages([], event.get("messages") or [])
            self._render_messages()
            self._update_older_button()
            if self.messages:
                self.message_list.SetFocus()
                self._status(f"{len(self.messages)} üzenettalálat. Esc: vissza az előzményekhez.")
            else:
                self._status("Nincs üzenettalálat. Esc: vissza az előzményekhez.")
        elif isinstance(context, tuple) and context[0] == "edit":
            _, chat_id, message_id = context
            if chat_id == self.chat_id:
                self.messages = protocol.merge_messages(self.messages, [event])
                self._render_messages(keep_focus=True)
            self._status("A módosított üzenetet a Telegram visszaigazolta.")
        elif isinstance(context, tuple) and context[0] == "open":
            _, chat_id, generation = context
            if chat_id == self.chat_id and generation == self.history_generation:
                self._request(protocol.history_request(chat_id),
                              ("history", chat_id, generation, 0))
        elif isinstance(context, tuple) and context[0] == "history":
            _, chat_id, generation, cursor = context
            if chat_id != self.chat_id or generation != self.history_generation:
                return
            page = event.get("messages") or []
            known = {int(item["id"]) for item in self.messages if item.get("id")}
            new_count = sum(1 for item in page if item.get("id") and int(item["id"]) not in known)
            self.messages = protocol.merge_messages(self.messages, page)
            self.history_loading = False
            # A TDLib rövid oldalt is adhat; csak üres vagy előrelépés nélküli
            # válasznál állunk meg.
            self.history_exhausted = not page or (cursor != 0 and new_count == 0)
            self._update_older_button()
            self._render_messages(keep_focus=cursor != 0)
            # A hálózati válasz nem veheti el a fókuszt az időközben már
            # használt szerkesztőtől vagy üzenetlistától.
            # TDLib egy rövid (akár egyetlen üzenetes) oldalt is adhat,
            # miközben vannak régebbi üzenetek. Az első megnyitáskor töltsünk
            # annyit, hogy az olvasó valóban kapjon használható előzményt.
            if (page and new_count and len(self.messages) < self.initial_history_target
                    and not self.history_exhausted):
                next_cursor = min(int(m["id"]) for m in self.messages)
                if next_cursor > 0:
                    self.history_loading = True
                    self._update_older_button()
                    self._request(protocol.history_request(chat_id, next_cursor),
                                  ("history", chat_id, generation, next_cursor))
        elif context == "send":
            self.pending_message_id = int(event.get("id") or 0)
            if not self.pending_message_id:
                self._complete_send(False)
            else:
                outcome = self.terminal_sends.pop(self.pending_message_id, None)
                if outcome is None:
                    self._status("A Telegram feldolgozza az üzenetet; küldési visszajelzésre várunk.")
                else:
                    self._complete_send(outcome)
        elif isinstance(context, tuple) and context[0] == "download":
            self._download_progress(event)
        elif isinstance(context, tuple) and context[0] == "play_download":
            self._download_progress(event)
        elif context == "bot_callback":
            answer = event.get("text") or "A botgomb műveletét a Telegram fogadta."
            self._status(answer)
        elif isinstance(context, tuple) and context[0] == "reactions":
            _, chat_id, message_id = context
            choices = protocol.reaction_choices(event)
            if not choices:
                self._status("Ehhez az üzenethez nincs választható ingyenes emoji-reakció.")
                return
            labels = [item["emoji"] for item in choices]
            with wx.SingleChoiceDialog(self, "Válassz reakciót:",
                                       "Telegram-reakciók", labels) as dialog:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                reaction = choices[dialog.GetSelection()]
            self._request(protocol.add_reaction_request(chat_id, message_id, reaction),
                          "reaction_sent")
        elif context == "reaction_sent":
            self._status("A reakciót a Telegram fogadta.")

    def _put_chat(self, chat):
        chat_id = int(chat.get("id") or 0)
        if not chat_id:
            return
        selected = self.chat_list.GetSelection()
        old_id = self.chat_ids[selected] if 0 <= selected < len(self.chat_ids) else None
        self.chats[chat_id] = chat
        positions = chat.get("positions")
        if positions is not None:
            main = any(p.get("list", {}).get("@type") == "chatListMain" and
                       int(p.get("order") or 0) > 0 for p in positions)
            archive = any(p.get("list", {}).get("@type") == "chatListArchive" and
                          int(p.get("order") or 0) > 0 for p in positions)
            for ids, present in ((self.all_chat_ids, main),
                                 (self.archive_chat_ids, archive)):
                if present and chat_id not in ids:
                    ids.append(chat_id)
                elif not present and chat_id in ids:
                    ids.remove(chat_id)
            for folder_id, ids in self.folder_chat_ids.items():
                present = any((p.get("list") or {}).get("@type") == "chatListFolder" and
                              int((p.get("list") or {}).get("chat_folder_id") or 0) == folder_id and
                              int(p.get("order") or 0) > 0 for p in positions)
                if present and chat_id not in ids:
                    ids.append(chat_id)
                elif not present and chat_id in ids:
                    ids.remove(chat_id)
                self._sort_chat_ids(ids, "chatListFolder", folder_id)
            self._sort_chat_ids(self.all_chat_ids, "chatListMain")
            self._sort_chat_ids(self.archive_chat_ids, "chatListArchive")
        elif chat_id not in self.all_chat_ids and chat_id not in self.archive_chat_ids:
            self.all_chat_ids.append(chat_id)
        self._apply_chat_filter(old_id)

    def _sort_chat_ids(self, ids, list_type, folder_id=0):
        def order(chat_id):
            positions = self.chats.get(chat_id, {}).get("positions") or []
            return max((int(p.get("order") or 0) for p in positions
                        if (p.get("list") or {}).get("@type") == list_type and
                        (list_type != "chatListFolder" or
                         int((p.get("list") or {}).get("chat_folder_id") or 0) == folder_id)), default=0)
        ids.sort(key=lambda chat_id: (order(chat_id), chat_id), reverse=True)

    def _apply_chat_filter(self, old_id=None):
        source = (self.search_chat_ids if self.search_chat_ids is not None else
                  self.archive_chat_ids if self.chat_scope == "archive" else
                  self.folder_chat_ids.get(self.chat_folder_id, []) if self.chat_scope == "folder"
                  else self.all_chat_ids)
        self.chat_ids = [cid for cid in source if
                         not self.unread_chats_only or
                         int(self.chats.get(cid, {}).get("unread_count") or 0) > 0]
        self._render_chats(old_id)

    def _toggle_unread_chats(self):
        self.unread_chats_only = not self.unread_chats_only
        self._apply_chat_filter()
        self.chat_list.SetFocus()
        self._status(("Csak olvasatlan" if self.unread_chats_only else "Minden") +
                     f" beszélgetés: {len(self.chat_ids)} látható. Ctrl U: váltás.")

    def _toggle_archive(self):
        self.chat_scope = "main" if self.chat_scope == "archive" else "archive"
        self.chat_folder_id = 0
        self.search_chat_ids = None
        self.chat_search.Clear()
        self._apply_chat_filter()
        self.chat_list.SetFocus()
        if self.chat_scope == "archive":
            self._request({"@type": "loadChats", "chat_list": {
                "@type": "chatListArchive"}, "limit": 100}, "load_archive")
            self._status("Archivált beszélgetések betöltése…")
        else:
            self._status(f"Főlista: {len(self.chat_ids)} beszélgetés. Ctrl L: archívum.")

    def _folder_name(self, folder_id):
        name = (self.chat_folders.get(folder_id, {}).get("name") or {}).get("text") or {}
        return name.get("text") if isinstance(name, dict) else str(name)

    def _show_main_chats(self):
        self.chat_scope, self.chat_folder_id = "main", 0
        self.search_chat_ids = None
        self.chat_search.Clear()
        self._apply_chat_filter()
        self.chat_list.SetFocus()
        self._status(f"Főlista: {len(self.chat_ids)} beszélgetés.")

    def _choose_folder(self):
        if not self.chat_folders:
            self._status("Nincsenek Telegram-beszélgetésmappák. Ctrl L: archívum.")
            return
        folder_ids = list(self.chat_folders)
        labels = [self._folder_name(folder_id) or f"Mappa {folder_id}"
                  for folder_id in folder_ids]
        with wx.SingleChoiceDialog(self, "Válassz Telegram-mappát:",
                                   "Beszélgetésmappák", labels) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            folder_id = folder_ids[dialog.GetSelection()]
        self.chat_scope, self.chat_folder_id = "folder", folder_id
        self.search_chat_ids = None
        self.chat_search.Clear()
        self._apply_chat_filter()
        self.chat_list.SetFocus()
        self._request({"@type": "loadChats", "chat_list": {
            "@type": "chatListFolder", "chat_folder_id": folder_id},
            "limit": 100}, ("load_folder", folder_id))
        self._status(f"{self._folder_name(folder_id)} mappa betöltése…")

    def _notify_message(self, message):
        message_id = int(message.get("id") or 0)
        if (not message_id or message.get("is_outgoing") or
                not self.notifications_enabled or self.recorder is not None):
            return
        if message_id in self.notified_message_ids:
            return
        if len(self.notified_message_ids) >= 500:
            self.notified_message_ids.clear()
        self.notified_message_ids.add(message_id)
        sound = Path(__file__).resolve().parents[2] / "csevej" / "csevej_mod" / "hang" / "incoming.wav"
        try:
            if sound.is_file():
                winsound.PlaySound(str(sound), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            else:
                winsound.MessageBeep()
        except RuntimeError:
            pass

    def _toggle_notifications(self):
        self.notifications_enabled = not self.notifications_enabled
        if self.core:
            self.core.store.save("notification_sound", self.notifications_enabled)
        self._status("Telegram-értesítési hang bekapcsolva." if self.notifications_enabled
                     else "Telegram-értesítési hang némítva.")

    def _render_chats(self, old_id=None):
        if old_id is None:
            selected = self.chat_list.GetSelection()
            old_id = self.chat_ids[selected] if 0 <= selected < len(self.chat_ids) else None
        self.chat_list.Set([f"{self.chats.get(cid, {}).get('title') or 'Beszélgetés'}; "
                            f"{self.chats.get(cid, {}).get('unread_count', 0)} olvasatlan"
                            for cid in self.chat_ids])
        if old_id in self.chat_ids:
            self.chat_list.SetSelection(self.chat_ids.index(old_id))
        elif self.chat_ids:
            self.chat_list.SetSelection(0)
        if (self.state == "authorizationStateReady" and
                self._announced_chat_count != len(self.all_chat_ids)):
            self._announced_chat_count = len(self.all_chat_ids)
            self._status(f"Bejelentkezve. {len(self.all_chat_ids)} beszélgetés. "
                         "Fel/le: választás, Enter vagy jobbra: megnyitás.")

    def _chat_key(self, event):
        if event.GetKeyCode() in (wx.WXK_MENU, wx.WXK_F10) and (
                event.GetKeyCode() == wx.WXK_MENU or event.ShiftDown()):
            self._chat_menu(event)
        elif event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER,
                                  wx.WXK_RIGHT):
            self._open_chat(event)
        else:
            event.Skip()

    def _shortcuts(self, event):
        key = event.GetKeyCode()
        focused = wx.Window.FindFocus()
        if key == wx.WXK_ESCAPE and self.chat_id and not self.message_search_active:
            self._back_to_chats()
        elif focused is self.chat_list and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER,
                                                  wx.WXK_RIGHT):
            self._open_chat(event)
        elif focused is self.message_list and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._activate_selected_message()
        elif focused is self.draft and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if event.ShiftDown():
                self.draft.WriteText("\n")
            else:
                self._send_text(None)
        elif focused is self.draft and key == wx.WXK_TAB and event.ShiftDown():
            self._focus_messages()
        elif focused is self.message_list and key == wx.WXK_TAB and not event.ShiftDown():
            self.draft.SetFocus()
        elif focused is self.chat_list and event.ControlDown() and key in (ord("U"), ord("u")):
            self._toggle_unread_chats()
        elif focused is self.chat_list and event.ControlDown() and key in (ord("L"), ord("l")):
            self._toggle_archive()
        elif focused is self.chat_list and event.ControlDown() and key in (ord("G"), ord("g")):
            self._choose_folder()
        elif event.ControlDown() and key in (ord("M"), ord("m")):
            self._toggle_notifications()
        elif event.ControlDown() and key in (ord("E"), ord("e")):
            self._prompt_chat_search(None)
        elif event.ControlDown() and key in (ord("F"), ord("f")) and self.chat_id:
            self._prompt_message_search(None)
        else:
            event.Skip()

    def _focus_messages(self):
        if self.message_list.GetCount() == 0:
            self._status("Még nincs betöltött üzenet ebben a beszélgetésben.")
            return
        if self.message_list.GetSelection() == wx.NOT_FOUND:
            self.message_list.SetSelection(self.message_list.GetCount() - 1)
        self.message_list.SetFocus()
        self._mark_selected_message()

    def _draft_key(self, event):
        key = event.GetKeyCode()
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if event.ShiftDown():
                self.draft.WriteText("\n")
            else:
                self._send_text(None)
        elif key == wx.WXK_TAB and event.ShiftDown():
            self._focus_messages()
        else:
            event.Skip()

    def _prompt_chat_search(self, _event):
        with wx.TextEntryDialog(self, "Név vagy felhasználónév; üresen minden beszélgetés:",
                                "Beszélgetés keresése", self.chat_search.GetValue()) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            self.chat_search.SetValue(dialog.GetValue())
        self._search_chats(None)

    def _search_chats(self, _event):
        query = self.chat_search.GetValue().strip()
        self.chat_search_generation += 1
        if not query:
            self.search_chat_ids = None
            self._apply_chat_filter()
            self.chat_list.SetFocus()
            self._status(f"{len(self.chat_ids)} beszélgetés.")
            return
        try:
            self._request({"@type": "searchChats", "query": query, "limit": 100},
                          ("search_chats", self.chat_search_generation))
            self._status("Beszélgetések keresése…")
        except RuntimeError as exc:
            self._status(str(exc))

    def _prompt_message_search(self, _event):
        if not self.chat_id:
            self._status("Előbb nyiss meg egy beszélgetést.")
            return
        with wx.TextEntryDialog(self, "Keresőszó; üresen vissza az előzményekhez:",
                                "Üzenet keresése", self.message_search.GetValue()) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            self.message_search.SetValue(dialog.GetValue())
        self._search_messages(None)

    def _search_messages(self, _event):
        query = self.message_search.GetValue().strip()
        if not self.chat_id:
            self._status("Előbb nyiss meg egy beszélgetést.")
            return
        if not query:
            self._clear_message_search()
            return
        try:
            self.message_search_generation += 1
            self._request(protocol.search_chat_messages(self.chat_id, query),
                          ("search_messages", self.chat_id, self.history_generation,
                           self.message_search_generation))
            self._status("Üzenetek keresése…")
        except (RuntimeError, ValueError) as exc:
            self._status(str(exc))

    def _clear_message_search(self):
        self.message_search_generation += 1
        self.message_search.Clear()
        if not self.message_search_active:
            self.message_list.SetFocus()
            return
        self.message_search_active = False
        self.messages = []
        self.message_list.Clear()
        self.history_generation += 1
        self.history_loading = True
        self.history_exhausted = False
        self._request(protocol.history_request(self.chat_id),
                      ("history", self.chat_id, self.history_generation, 0))
        self._status("Beszélgetés visszatöltése…")

    def _chat_menu(self, _event):
        index = self.chat_list.GetSelection()
        if not (0 <= index < len(self.chat_ids)):
            self._status("Előbb válassz egy beszélgetést.")
            return
        chat_id = self.chat_ids[index]
        menu = wx.Menu()
        opening = menu.Append(wx.ID_ANY, "Beszélgetés megnyitása\tEnter")
        compose = menu.Append(wx.ID_ANY, "Üzenet írása")
        send_file = menu.Append(wx.ID_ANY, "Fájl küldése…")
        record = menu.Append(wx.ID_ANY, "Hangüzenet rögzítése…")
        info = menu.Append(wx.ID_ANY, "Beszélgetés adatai")
        read = menu.Append(wx.ID_ANY, "Olvasottnak jelölés")
        scope = menu.Append(wx.ID_ANY, "Főlista megnyitása\tCtrl+L" if
                            self.chat_scope == "archive" else "Archívum megnyitása\tCtrl+L")
        folders = menu.Append(wx.ID_ANY, "Beszélgetésmappák…\tCtrl+G")
        main = menu.Append(wx.ID_ANY, "Főlista")
        mute = menu.Append(wx.ID_ANY, "Értesítési hang némítása\tCtrl+M" if
                           self.notifications_enabled else "Értesítési hang bekapcsolása\tCtrl+M")
        menu.Bind(wx.EVT_MENU, self._open_chat, opening)
        menu.Bind(wx.EVT_MENU, lambda e: self._compose_chat(), compose)
        menu.Bind(wx.EVT_MENU, lambda e: self._file_to_chat(), send_file)
        menu.Bind(wx.EVT_MENU, lambda e: self._record_to_chat(), record)
        menu.Bind(wx.EVT_MENU, lambda e: self._chat_info(chat_id), info)
        menu.Bind(wx.EVT_MENU, lambda e: self._mark_chat_read(chat_id), read)
        menu.Bind(wx.EVT_MENU, lambda e: self._toggle_archive(), scope)
        menu.Bind(wx.EVT_MENU, lambda e: self._choose_folder(), folders)
        menu.Bind(wx.EVT_MENU, lambda e: self._show_main_chats(), main)
        menu.Bind(wx.EVT_MENU, lambda e: self._toggle_notifications(), mute)
        try:
            self.PopupMenu(menu)
        finally:
            menu.Destroy()

    def _chat_right_down(self, event):
        index = self.chat_list.HitTest(event.GetPosition())
        if index != wx.NOT_FOUND:
            self.chat_list.SetSelection(index)
        event.Skip()

    def _compose_chat(self):
        self.focus_draft_after_open = True
        self._open_chat(None)

    def _file_to_chat(self):
        self._open_chat(None)
        self._send_document(None)

    def _record_to_chat(self):
        self._open_chat(None)
        self._voice_button(None)

    def _chat_info(self, chat_id):
        chat = self.chats.get(chat_id) or {}
        kind = (chat.get("type") or {}).get("@type") or "nem megadott"
        kinds = {"chatTypePrivate": "Személyes beszélgetés",
                 "chatTypeBasicGroup": "Csoport",
                 "chatTypeSupergroup": "Csoport vagy csatorna",
                 "chatTypeSecret": "Titkos beszélgetés"}
        wx.MessageBox(f"{chat.get('title') or 'Beszélgetés'}\n"
                      f"{kinds.get(kind, kind)}\n"
                      f"{chat.get('unread_count', 0)} olvasatlan üzenet",
                      "Beszélgetés adatai", wx.OK | wx.ICON_INFORMATION, self)

    def _mark_chat_read(self, chat_id):
        latest = (self.chats.get(chat_id) or {}).get("last_message") or {}
        message_id = int(latest.get("id") or 0)
        if not message_id:
            self._status("Ehhez a beszélgetéshez nincs jelölhető üzenet.")
            return
        self._request(protocol.view_message_request(chat_id, message_id), "view")
        self._status("Olvasottnak jelölés elküldve a Telegramnak.")

    def _message_key(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE and self.message_search_active:
            self._clear_message_search()
        elif event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if not self._activate_selected_message():
                event.Skip()
        elif event.GetKeyCode() in (wx.WXK_LEFT, wx.WXK_ESCAPE):
            self._back_to_chats()
        elif event.GetKeyCode() in (wx.WXK_MENU, wx.WXK_F10) and (
                event.GetKeyCode() == wx.WXK_MENU or event.ShiftDown()):
            self._message_menu(event)
        else:
            event.Skip()

    def _message_char_hook(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._activate_selected_message()
        else:
            event.Skip()

    def _message_activated(self, _event):
        self._activate_selected_message()

    def _selected_message(self):
        index = self.message_list.GetSelection()
        return self.messages[index] if 0 <= index < len(self.messages) else None

    def _activate_selected_message(self):
        message = self._selected_message()
        if message and (message.get("content") or {}).get("@type") in (
                "messageVoiceNote", "messageAudio"):
            self._play_message(message)
            return True
        if message and protocol.inline_buttons(message):
            self._show_bot_buttons(message)
            return True
        return False

    def _message_right_down(self, event):
        index = self.message_list.HitTest(event.GetPosition())
        if index != wx.NOT_FOUND:
            self.message_list.SetSelection(index)
        event.Skip()

    def _message_menu(self, _event):
        message = self._selected_message()
        if not message:
            self._status("Előbb jelölj ki egy üzenetet.")
            return
        menu = wx.Menu()
        reply = menu.Append(wx.ID_ANY, "Válasz erre az üzenetre")
        copy = menu.Append(wx.ID_ANY, "Üzenetszöveg másolása")
        menu.Bind(wx.EVT_MENU, lambda e: self._reply_to_message(message), reply)
        menu.Bind(wx.EVT_MENU, lambda e: self._copy_message(message), copy)
        content = message.get("content") or {}
        if message.get("is_outgoing") and content.get("@type") == "messageText":
            edit = menu.Append(wx.ID_ANY, "Saját üzenet szerkesztése…")
            menu.Bind(wx.EVT_MENU, lambda e: self._edit_message(message), edit)
        if protocol.message_attachment(message):
            save = menu.Append(wx.ID_ANY, "Fájl mentése…")
            menu.Bind(wx.EVT_MENU, self._save_attachment, save)
        if content.get("@type") in ("messageVoiceNote", "messageAudio"):
            play = menu.Append(wx.ID_ANY, "Hang lejátszása vagy leállítása")
            menu.Bind(wx.EVT_MENU, lambda e: self._play_message(message), play)
        if protocol.inline_buttons(message):
            bot = menu.Append(wx.ID_ANY, "Botgombok…")
            menu.Bind(wx.EVT_MENU, lambda e: self._show_bot_buttons(message), bot)
        react = menu.Append(wx.ID_ANY, "Reakció hozzáadása…")
        menu.Bind(wx.EVT_MENU, lambda e: self._show_reactions(message), react)
        try:
            self.PopupMenu(menu)
        finally:
            menu.Destroy()

    def _reply_to_message(self, message):
        self.reply_to_message_id = int(message.get("id") or 0)
        self.draft.SetFocus()
        self._status("Válasz a kijelölt üzenetre. Írd meg, majd ellenőrizd küldés előtt.")

    def _show_bot_buttons(self, message):
        buttons = protocol.inline_buttons(message)
        labels = [button["text"] for button in buttons]
        with wx.SingleChoiceDialog(self, "Válassz botgombot:",
                                   "Telegram botgombok", labels) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            button = buttons[dialog.GetSelection()]
        try:
            action, value = protocol.bot_button_action(button)
            if action == "copy":
                if not wx.TheClipboard.Open():
                    self._status("A vágólap most nem elérhető.")
                    return
                try:
                    wx.TheClipboard.SetData(wx.TextDataObject(value))
                finally:
                    wx.TheClipboard.Close()
                self._status("A botgomb szövege a vágólapra került.")
                return
            if action == "url":
                if wx.MessageBox(f"Megnyitod ezt a hivatkozást?\n{value}",
                                 "Telegram botgomb", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
                    return
                if not wx.LaunchDefaultBrowser(value):
                    self._status("A hivatkozást nem sikerült megnyitni.")
                return
            request = protocol.callback_button_request(
                int(message.get("chat_id") or self.chat_id),
                int(message.get("id") or 0), button)
        except ValueError as exc:
            self._status(str(exc))
            return
        self._request(request, "bot_callback")
        self._status("Botgomb elküldve; válaszra várunk.")

    def _show_reactions(self, message):
        chat_id = int(message.get("chat_id") or self.chat_id)
        message_id = int(message.get("id") or 0)
        try:
            request = protocol.available_reaction_request(chat_id, message_id)
        except ValueError as exc:
            self._status(str(exc))
            return
        self._request(request, ("reactions", chat_id, message_id))
        self._status("Elérhető reakciók betöltése.")

    def _copy_message(self, message):
        content = message.get("content") or {}
        raw = (content.get("text") or {}).get("text") if content.get("@type") == "messageText" else ""
        if not raw:
            self._status("Ebben az üzenetben nincs másolható szöveg.")
            return
        if not wx.TheClipboard.Open():
            self._status("A vágólap most nem elérhető.")
            return
        try:
            wx.TheClipboard.SetData(wx.TextDataObject(raw))
        finally:
            wx.TheClipboard.Close()
        self._status("Az üzenetszöveg a vágólapra került.")

    def _edit_message(self, message):
        content = message.get("content") or {}
        original = (content.get("text") or {}).get("text") or ""
        if not message.get("is_outgoing") or content.get("@type") != "messageText":
            self._status("Csak saját szöveges üzenet szerkeszthető.")
            return
        with wx.TextEntryDialog(self, "Saját üzenet új szövege:",
                                "Üzenet szerkesztése", original) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            new_text = dialog.GetValue()
        if new_text == original:
            return
        try:
            request = protocol.edit_text_message(self.chat_id, int(message["id"]), new_text)
        except ValueError as exc:
            self._status(str(exc))
            return
        if wx.MessageBox("A saját üzenet szövege módosul a Telegramon. Mentjük?",
                         "Módosítás ellenőrzése", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        self._request(request, ("edit", self.chat_id, int(message["id"])))
        self._status("Az üzenet módosítására várunk…")

    def _open_chat(self, _event):
        index = self.chat_list.GetSelection()
        if index == wx.NOT_FOUND:
            self.focus_draft_after_open = False
            return
        previous_chat_id = self.chat_id
        next_chat_id = self.chat_ids[index]
        if previous_chat_id:
            self.chat_drafts[previous_chat_id] = self.draft.GetValue()
        self.chat_id = next_chat_id
        self.draft.SetValue(self.chat_drafts.get(next_chat_id, ""))
        if previous_chat_id and previous_chat_id != self.chat_id:
            self._request({"@type": "closeChat", "chat_id": previous_chat_id},
                          "close")
        self.messages = []
        self.focus_draft_after_open = False
        self.message_search_active = False
        self.message_search_generation += 1
        self.message_search.Clear()
        self.reply_to_message_id = 0
        self.history_generation += 1
        self.history_loading = True
        self.history_exhausted = False
        self.viewed_message_ids.clear()
        self.message_list.Clear()
        self._set_view()
        self._update_older_button()
        self._request({"@type": "openChat", "chat_id": self.chat_id},
                      ("open", self.chat_id, self.history_generation))
        self.draft.SetFocus()
        self._status("Üzenet írása. Shift Tab: előzmények. A beszélgetés betöltése folyamatban…")

    def _back_to_chats(self):
        if not self.chat_id:
            return
        old_chat_id = self.chat_id
        self.chat_drafts[old_chat_id] = self.draft.GetValue()
        self.draft.Clear()
        self.chat_id = 0
        self.reply_to_message_id = 0
        self.history_generation += 1
        self.message_search_generation += 1
        self.message_search_active = False
        self.messages = []
        self.message_list.Clear()
        self._set_view()
        if self.transport and self.transport.running:
            try:
                self._request({"@type": "closeChat", "chat_id": old_chat_id}, "close")
            except RuntimeError:
                pass
        self.chat_list.SetFocus()
        self._status("Beszélgetések. Fel/le: választás, Enter: megnyitás.")

    def _load_older(self, _event):
        if not self.chat_id or self.history_loading or self.history_exhausted or not self.messages:
            return
        cursor = min(int(message["id"]) for message in self.messages)
        if cursor <= 0:
            self.history_exhausted = True
            self._update_older_button()
            return
        self.history_loading = True
        self._update_older_button()
        self._request(protocol.history_request(self.chat_id, cursor),
                      ("history", self.chat_id, self.history_generation, cursor))
        self._status("Régebbi üzenetek betöltése…")

    def _update_older_button(self):
        self.older_button.Enable(bool(self.chat_id and self.messages and
                                      not self.message_search_active and not self.history_loading and
                                      not self.history_exhausted and
                                      self.state == "authorizationStateReady"))

    def _message_selected(self, event):
        self._mark_selected_message(event.GetSelection())

    def _mark_selected_message(self, index=None):
        if index is None:
            index = self.message_list.GetSelection()
        if not (0 <= index < len(self.messages)) or not self.chat_id:
            return
        msg = self.messages[index]
        message_id = int(msg.get("id") or 0)
        if not message_id or message_id in self.viewed_message_ids or msg.get("is_outgoing"):
            return
        self.viewed_message_ids.add(message_id)
        try:
            self._request(protocol.view_message_request(self.chat_id, message_id), "view")
        except RuntimeError:
            self.viewed_message_ids.discard(message_id)

    def _render_messages(self, keep_focus=False):
        old = self.message_list.GetSelection() if keep_focus else wx.NOT_FOUND
        old_id = int(self.message_list.GetClientData(old) or 0) if old != wx.NOT_FOUND else 0
        self.message_list.Set([protocol.message_label(msg) for msg in self.messages])
        for index, msg in enumerate(self.messages):
            self.message_list.SetClientData(index, int(msg["id"]))
        new_index = next((index for index, msg in enumerate(self.messages)
                          if int(msg["id"]) == old_id), wx.NOT_FOUND) if old_id else wx.NOT_FOUND
        if new_index != wx.NOT_FOUND:
            self.message_list.SetSelection(new_index)
        elif self.messages:
            self.message_list.SetSelection(len(self.messages) - 1)
        self._status(f"{len(self.messages)} üzenet a beszélgetésben.")

    def _send_text(self, _event):
        if self.sending:
            return
        try:
            request = protocol.text_message(self.chat_id, self.draft.GetValue(),
                                            self.reply_to_message_id)
        except ValueError as exc:
            self._status(str(exc))
            return
        self.sending = True
        self.sending_kind = "text"
        self.sending_chat_id = self.chat_id
        self.sending_text = self.draft.GetValue()
        self.send_button.Enable(False)
        self.file_button.Enable(False)
        try:
            self._request(request, "send")
        except RuntimeError as exc:
            self.sending = False
            self.sending_kind = ""
            self.sending_chat_id = 0
            self.sending_text = ""
            self.send_button.Enable(True)
            self.file_button.Enable(True)
            self._status(str(exc))
            return
        self._status("Üzenet küldése folyamatban…")

    def _send_document(self, _event):
        if self.sending or not self.chat_id:
            self._status("Előbb nyiss meg egy beszélgetést.")
            return
        with wx.FileDialog(self, "Küldendő fájl kiválasztása",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = Path(dialog.GetPath())
        try:
            request = protocol.document_message(self.chat_id, path)
            size = path.stat().st_size
        except (OSError, ValueError) as exc:
            self._status(str(exc))
            return
        title = self.chats.get(self.chat_id, {}).get("title") or "kijelölt beszélgetés"
        if wx.MessageBox(f"Címzett: {title}\nFájl: {path.name}\nMéret: {size} bájt\n\nElküldjük?",
                         "Fájlküldés ellenőrzése", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        self.sending = True
        self.sending_kind = "file"
        self.sending_chat_id = self.chat_id
        self.sending_text = ""
        self.send_button.Enable(False)
        self.file_button.Enable(False)
        try:
            self._request(request, "send")
        except RuntimeError as exc:
            self.sending = False
            self.sending_kind = ""
            self.sending_chat_id = 0
            self.sending_text = ""
            self.send_button.Enable(True)
            self.file_button.Enable(True)
            self._status(str(exc))
            return
        self._status("Fájl küldése folyamatban…")

    def _voice_button(self, _event):
        if not self.chat_id or self.sending:
            return
        if self.recorder is None:
            if self.recorded_voice:
                self._review_voice()
                return
            speaker = getattr(getattr(self.core, "voice", None), "_sv", None)
            if speaker:
                speaker.stop()
            try:
                winsound.Beep(880, 90)
            except RuntimeError:
                pass
            path = self.root / "recordings" / (uuid.uuid4().hex + ".wav")
            self.recorder = VoiceRecorder(path)
            self.recorder.start()
            self.voice_button.SetLabel("Felvétel leállítása")
            # Felvétel közben sem a SuperDL, sem a Telegram nem beszélhet bele.
            self.status.SetLabel("")
            return
        recorder = self.recorder
        self.recorder = None
        self.voice_button.Enable(False)
        self.voice_button.SetLabel("Hangüzenet rögzítése")
        from superdl.ffmpeg import find_ffmpeg
        def finish():
            try:
                result = recorder.stop(find_ffmpeg())
            except (RuntimeError, OSError) as exc:
                wx.CallAfter(self._voice_failed, str(exc))
            else:
                wx.CallAfter(self._voice_ready, result)
        threading.Thread(target=finish, daemon=True).start()

    def _voice_failed(self, message):
        self.voice_button.Enable(True)
        self._status(message)

    def _voice_ready(self, result):
        if self.closing:
            result[0].unlink(missing_ok=True)
            return
        self.recorded_voice = result
        self.recorded_voice_chat_id = self.chat_id
        self.voice_button.Enable(True)
        self.voice_button.SetLabel("Hangüzenet ellenőrzése…")
        self._status("A felvétel elkészült. Meghallgatható vagy elküldhető.")
        self._review_voice()

    def _review_voice(self):
        if not self.recorded_voice:
            return
        if self.chat_id != self.recorded_voice_chat_id:
            self._status("A felvétel másik beszélgetéshez készült. Térj vissza oda, vagy dobd el.")
            return
        path, duration = self.recorded_voice
        while True:
            with wx.SingleChoiceDialog(self, f"{duration} másodperces hangfelvétel.",
                                       "Hangüzenet ellenőrzése",
                                       ["Meghallgatás", "Elküldés", "Eldobás"]) as dialog:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                choice = dialog.GetSelection()
            if choice == 0:
                self._start_audio(path, 0)
                return
            if choice == 2:
                path.unlink(missing_ok=True)
                self.recorded_voice = None
                self.recorded_voice_chat_id = 0
                self.voice_button.SetLabel("Hangüzenet rögzítése")
                self._status("A hangfelvétel eldobva.")
                return
            break
        try:
            request = protocol.voice_message(self.chat_id, path, duration)
        except (OSError, ValueError) as exc:
            self._status(str(exc))
            return
        title = self.chats.get(self.chat_id, {}).get("title") or "kijelölt beszélgetés"
        if wx.MessageBox(f"{title} részére elküldjük a {duration} másodperces hangüzenetet?",
                         "Hangüzenet küldése", wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
            return
        if self.audio_player:
            self.audio_player.stop()
        self.sending = True
        self.sending_kind = "voice"
        self.sending_chat_id = self.chat_id
        self.send_button.Enable(False)
        self.file_button.Enable(False)
        self.voice_button.Enable(False)
        try:
            self._request(request, "send")
        except RuntimeError as exc:
            self.sending = False
            self.sending_kind = ""
            self.send_button.Enable(True)
            self.file_button.Enable(True)
            self.voice_button.Enable(True)
            self._status(str(exc))
            return
        self._status("Hangüzenet küldése folyamatban…")

    def _save_attachment(self, _event):
        index = self.message_list.GetSelection()
        if not (0 <= index < len(self.messages)):
            self._status("Előbb jelölj ki egy üzenetet.")
            return
        found = protocol.message_attachment(self.messages[index])
        if found is None:
            self._status("A kijelölt üzenetben nincs menthető fájl.")
            return
        file, suggested_name = found
        file_id = int(file["id"])
        if file_id in self.pending_downloads:
            self._status("A fájl letöltése már folyamatban van.")
            return
        with wx.FileDialog(self, "Érkező fájl mentése", defaultFile=suggested_name,
                           style=wx.FD_SAVE) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            destination = Path(dialog.GetPath())
        if destination.exists():
            self._status("A választott fájl már létezik. Válassz másik nevet; nem írjuk felül.")
            return
        self.pending_downloads[file_id] = destination
        self._download_progress(file)
        if file_id not in self.pending_downloads:
            return
        try:
            self._request({"@type": "downloadFile", "file_id": file_id,
                           "priority": 16, "offset": 0, "limit": 0,
                           "synchronous": False}, ("download", file_id))
        except RuntimeError as exc:
            self.pending_downloads.pop(file_id, None)
            self._status(str(exc))
            return
        self._status("Fájl letöltése folyamatban…")

    def _download_progress(self, file):
        file_id = int(file.get("id") or 0)
        if file_id in self.pending_playback:
            local = file.get("local") or {}
            if local.get("is_downloading_completed") and local.get("path"):
                self.pending_playback.discard(file_id)
                self._start_audio(Path(local["path"]), file_id)
        destination = self.pending_downloads.get(file_id)
        if destination is None:
            return
        local = file.get("local") or {}
        if local.get("is_downloading_completed") and local.get("path"):
            self.pending_downloads.pop(file_id, None)
            source = Path(local["path"])
            threading.Thread(target=self._copy_download,
                             args=(source, destination), daemon=True).start()

    def _play_message(self, message):
        attachment = protocol.message_attachment(message)
        if not attachment:
            self._status("Ebben az üzenetben nincs lejátszható hang.")
            return
        file, _ = attachment
        file_id = int(file.get("id") or 0)
        if self.playing_file_id == file_id:
            self.audio_player.stop()
            self.playing_file_id = 0
            self._status("Hang leállítva.")
            return
        local = file.get("local") or {}
        if local.get("is_downloading_completed") and local.get("path"):
            self._start_audio(Path(local["path"]), file_id)
            return
        self.pending_playback.clear()
        self.pending_playback.add(file_id)
        try:
            self._request({"@type": "downloadFile", "file_id": file_id,
                           "priority": 16, "offset": 0, "limit": 0,
                           "synchronous": False}, ("play_download", file_id))
        except RuntimeError as exc:
            self.pending_playback.discard(file_id)
            self._status(str(exc))
            return
        self._status("Hangüzenet letöltése…")

    def _start_audio(self, path, file_id):
        if not path.is_file():
            self._status("A letöltött hangfájl nem található.")
            return
        try:
            if self.audio_player is None:
                from superdl.audioengine import Player
                self.audio_player = Player()
                self.audio_player.on_state = lambda state: wx.CallAfter(
                    self._audio_state, state)
            self.playing_file_id = file_id
            self.audio_player.play(str(path), "Telegram-hangüzenet")
            self._status("Hang lejátszása. Enter: leállítás.")
        except Exception as exc:
            self.playing_file_id = 0
            self._status(f"A hang lejátszása sikertelen: {exc}")

    def _audio_state(self, state):
        if self.closing:
            return
        if state.lower().startswith(("vége", "hiba")):
            self.playing_file_id = 0
        self._status("Hang: " + state)

    def _copy_download(self, source, destination):
        created = False
        try:
            if source.resolve() == destination.resolve():
                raise OSError("A forrás és a cél azonos.")
            with source.open("rb") as input_file, destination.open("xb") as output_file:
                created = True
                shutil.copyfileobj(input_file, output_file)
        except OSError as exc:
            if created:
                try:
                    destination.unlink()
                except OSError:
                    pass
            wx.CallAfter(self._status, f"A fájl mentése sikertelen: {exc}")
        else:
            wx.CallAfter(self._status, f"Fájl elmentve: {destination}")

    def _close(self, event):
        if not self.closing:
            if self.recorder:
                self.recorder.cancel()
                self.recorder = None
                self.voice_button.SetLabel("Hangüzenet rögzítése")
            if self.audio_player:
                self.audio_player.stop()
            self.Hide()
            self._status("A Supergram a SuperDL futása közben a háttérben marad. Ctrl M: értesítési hang.")
            return
        event.Skip()

    def _destroyed(self, event):
        if event.GetEventObject() is not self:
            event.Skip()
            return
        self.closing = True
        if self.recorder:
            self.recorder.cancel()
        if self.recorded_voice:
            self.recorded_voice[0].unlink(missing_ok=True)
        if self.audio_player:
            self.audio_player.stop()
        if self.transport:
            if self.chat_id and self.transport.running:
                try:
                    self.transport.send({"@type": "closeChat", "chat_id": self.chat_id})
                except RuntimeError:
                    pass
            self.transport.stop()
        event.Skip()
