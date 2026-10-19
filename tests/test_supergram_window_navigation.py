"""A belépés után a beszélgetéslista nem maradhat kijelölés nélkül."""

import wx

from modules_src.supergram.supergram_mod.window import SupergramFrame


def test_ready_chat_list_has_selection_and_keyboard_open(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    frame.Show()
    try:
        requests = []
        frame._request = lambda request, context: requests.append((request, context))
        frame._auth({"@type": "authorizationStateReady"})
        frame._put_chat({"id": 42, "title": "Próba", "unread_count": 2})
        assert frame.chat_list.GetSelection() == 0
        assert "Próba" in frame.chat_list.GetString(0)
        assert "1 beszélgetés" in frame.status.GetLabel()
        assert requests[0][0]["@type"] == "loadChats"

        opened = []
        frame._open_chat = lambda event: opened.append(True)

        class RightArrow:
            def GetKeyCode(self):
                return wx.WXK_RIGHT

        frame._chat_key(RightArrow())
        assert opened == [True]
    finally:
        frame.Destroy()


def test_unread_chat_filter_tracks_new_messages_and_keeps_search(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    frame.Show()
    try:
        requests = []
        frame._request = lambda request, context: requests.append((request, context))
        frame._auth({"@type": "authorizationStateReady"})
        frame._put_chat({"id": 42, "title": "Olvasott", "unread_count": 0})
        frame._put_chat({"id": 77, "title": "Új", "unread_count": 2})
        frame.chat_list.SetFocus()
        wx.Yield()

        class CtrlU:
            def GetKeyCode(self):
                return ord("U")

            def ControlDown(self):
                return True

        frame._shortcuts(CtrlU())
        assert frame.chat_ids == [77]
        assert frame.chat_list.GetSelection() == 0
        frame._event({"@type": "updateNewMessage", "message": {"chat_id": 42, "id": 100}})
        assert requests[-1] == ({"@type": "getChat", "chat_id": 42}, "chat")
        frame._put_chat({"id": 42, "title": "Olvasott", "unread_count": 1})
        assert frame.chat_ids == [42, 77]
        frame._put_chat({"id": 77, "title": "Új", "unread_count": 0})
        assert frame.chat_ids == [42]
        frame.search_chat_ids = [77]
        frame._apply_chat_filter()
        assert frame.chat_ids == []
        frame._toggle_unread_chats()
        assert frame.chat_ids == [77]
        assert frame.chat_list.GetSelection() == 0
    finally:
        frame.Destroy()


def test_archive_switch_tracks_chat_positions_and_keeps_background_connection(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    frame.Show()
    try:
        requests = []
        frame._request = lambda request, context: requests.append((request, context))
        frame._auth({"@type": "authorizationStateReady"})
        frame._put_chat({"id": 42, "title": "Főlista", "positions": [
            {"list": {"@type": "chatListMain"}, "order": 100}]})
        frame._toggle_archive()
        assert requests[-1][0]["chat_list"]["@type"] == "chatListArchive"
        frame.pending["archive"] = "archive_chats"
        frame._response("archive", {"@type": "chats", "chat_ids": [77]})
        frame._put_chat({"id": 77, "title": "Archív", "positions": [
            {"list": {"@type": "chatListArchive"}, "order": 80}]})
        assert frame.chat_ids == [77]
        frame._put_chat({"id": 77, "title": "Visszahelyezve", "positions": [
            {"list": {"@type": "chatListMain"}, "order": 90}]})
        assert frame.chat_ids == []
        frame._toggle_archive()
        assert 42 in frame.chat_ids and 77 in frame.chat_ids
        frame.Close()
        assert not frame.IsShown()
        assert not frame.closing
    finally:
        frame.Destroy()


def test_folder_list_uses_tdlib_positions_and_returns_to_main(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    try:
        requests = []
        frame._request = lambda request, context: requests.append((request, context))
        frame._auth({"@type": "authorizationStateReady"})
        frame._event({"@type": "updateChatFolders", "chat_folders": [
            {"id": 5, "name": {"text": {"text": "Barátok"}}}]})
        assert frame._folder_name(5) == "Barátok"
        frame.chat_scope, frame.chat_folder_id = "folder", 5
        frame.pending["folder"] = ("folder_chats", 5)
        frame._response("folder", {"@type": "chats", "chat_ids": [42]})
        frame._put_chat({"id": 42, "title": "Próba", "positions": [
            {"list": {"@type": "chatListFolder", "chat_folder_id": 5},
             "order": 100}]})
        assert frame.chat_ids == [42]
        frame._put_chat({"id": 42, "title": "Próba", "positions": [
            {"list": {"@type": "chatListMain"}, "order": 90}]})
        assert frame.chat_ids == []
        frame._show_main_chats()
        assert frame.chat_ids == [42]
        frame._event({"@type": "updateChatFolders", "chat_folders": []})
        assert frame.chat_folders == {}
    finally:
        frame.Destroy()


def test_reaction_dialog_uses_selected_server_option(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    try:
        requests = []
        frame._request = lambda request, context: requests.append((request, context))
        frame.chat_id = 7
        frame._show_reactions({"id": 9, "chat_id": 7})
        assert requests[-1][0]["@type"] == "getMessageAvailableReactions"

        class Choice:
            def __init__(self, parent, prompt, title, labels):
                assert labels == ["👍"]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def GetSelection(self):
                return 0

        monkeypatch.setattr(wx, "SingleChoiceDialog", Choice)
        frame.pending["reaction"] = ("reactions", 7, 9)
        frame._response("reaction", {"@type": "availableReactions",
            "top_reactions": [{"type": {"@type": "reactionTypeEmoji", "emoji": "👍"}}]})
        assert requests[-1][0]["@type"] == "addMessageReaction"
        assert requests[-1][1] == "reaction_sent"
    finally:
        frame.Destroy()


def test_open_chat_loads_history_after_open_and_continues_short_page(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    try:
        requests = []
        frame._request = lambda request, context: requests.append((request, context))
        frame._auth({"@type": "authorizationStateReady"})
        frame._put_chat({"id": 42, "title": "Próba", "unread_count": 1})
        frame._open_chat(None)
        assert requests[-1][0] == {"@type": "openChat", "chat_id": 42}
        generation = frame.history_generation

        frame.pending["open"] = ("open", 42, generation)
        frame._response("open", {"@type": "ok"})
        assert requests[-1][0]["@type"] == "getChatHistory"

        frame.pending["history"] = ("history", 42, generation, 0)
        frame._response("history", {"@type": "messages", "messages": [
            {"id": 100, "chat_id": 42, "date": 1,
             "content": {"@type": "messageText", "text": {"text": "Próba"}}}]})
        assert frame.message_list.GetCount() == 1
        assert frame.message_list.GetSelection() == 0
        assert requests[-1][0]["@type"] == "getChatHistory"
        assert requests[-1][0]["from_message_id"] == 100
    finally:
        frame.Destroy()


def test_chat_search_and_message_actions_do_not_lose_selection(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    try:
        requests = []
        frame._request = lambda request, context: requests.append((request, context))
        frame._auth({"@type": "authorizationStateReady"})
        assert not frame.chat_search.IsShown()
        assert not frame.message_search.IsShown()
        assert frame.chat_search_button.GetLabel() == "Beszélgetés keresése…"
        assert frame.message_search_button.GetLabel() == "Üzenet keresése…"
        frame._put_chat({"id": 42, "title": "Próba", "unread_count": 0})
        frame._put_chat({"id": 77, "title": "Másik", "unread_count": 0})
        frame.chat_search.SetValue("Pró")
        frame._search_chats(None)
        assert requests[-1][0] == {"@type": "searchChats", "query": "Pró", "limit": 100}
        frame.pending["search"] = requests[-1][1]
        frame._response("search", {"@type": "chats", "chat_ids": [42]})
        assert frame.chat_ids == [42]
        assert frame.chat_list.GetSelection() == 0

        message = {"id": 123, "chat_id": 42, "date": 1, "is_outgoing": False,
                   "content": {"@type": "messageText", "text": {"text": "Szia"}}}
        frame.chat_id = 42
        frame.messages = [message]
        frame._render_messages()
        frame._reply_to_message(message)
        assert frame.reply_to_message_id == 123
        captured = []
        monkeypatch.setattr(SupergramFrame, "PopupMenu",
                            lambda self, menu: captured.extend(
                                item.GetItemLabelText() for item in menu.GetMenuItems()))
        frame._message_menu(None)
        assert "Válasz erre az üzenetre" in captured
        assert "Üzenetszöveg másolása" in captured
        assert "Saját üzenet szerkesztése…" not in captured
    finally:
        frame.Destroy()


def test_message_search_uses_tdlib_and_restores_history(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    try:
        requests = []
        frame._request = lambda request, context: requests.append((request, context))
        frame._auth({"@type": "authorizationStateReady"})
        frame.chat_id = 42
        frame.message_search.SetValue("találat")
        frame._search_messages(None)
        request, context = requests[-1]
        assert request["@type"] == "searchChatMessages"
        assert request["query"] == "találat"
        frame.pending["search"] = context
        frame._response("search", {"@type": "foundChatMessages", "messages": [
            {"id": 100, "chat_id": 42, "date": 1,
             "content": {"@type": "messageText", "text": {"text": "találat"}}}]})
        assert frame.message_search_active
        assert frame.message_list.GetCount() == 1
        frame._clear_message_search()
        assert not frame.message_search_active
        assert requests[-1][0]["@type"] == "getChatHistory"
    finally:
        frame.Destroy()


def test_open_focuses_editor_and_keyboard_moves_to_history_and_sends(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    frame.Show()

    class Key:
        def __init__(self, code, shift=False):
            self.code, self.shift = code, shift

        def GetKeyCode(self):
            return self.code

        def ShiftDown(self):
            return self.shift

        def ControlDown(self):
            return False

        def Skip(self):
            pass

    try:
        requests = []
        frame._request = lambda request, context: requests.append((request, context))
        frame._auth({"@type": "authorizationStateReady"})
        frame._put_chat({"id": 42, "title": "Próba", "unread_count": 0})
        frame.chat_list.SetFocus()
        wx.Yield()
        frame._shortcuts(Key(wx.WXK_RETURN))
        wx.Yield()
        assert wx.Window.FindFocus() is frame.draft
        assert requests[-1][0] == {"@type": "openChat", "chat_id": 42}
        frame.messages = [{"id": 100, "chat_id": 42, "date": 1,
                           "content": {"@type": "messageText", "text": {"text": "Helló"}}}]
        frame._render_messages()
        frame._shortcuts(Key(wx.WXK_TAB, shift=True))
        wx.Yield()
        assert wx.Window.FindFocus() is frame.message_list
        frame._shortcuts(Key(wx.WXK_TAB))
        wx.Yield()
        assert wx.Window.FindFocus() is frame.draft
        frame.draft.SetValue("Szia")
        frame.draft.SetInsertionPointEnd()
        frame._shortcuts(Key(wx.WXK_RETURN, shift=True))
        assert frame.draft.GetValue() == "Szia\n"
        frame._shortcuts(Key(wx.WXK_RETURN))
        assert requests[-1][0]["@type"] == "sendMessage"
        assert requests[-1][0]["input_message_content"]["text"]["text"] == "Szia\n"
    finally:
        frame.Destroy()


def test_enter_on_voice_message_plays_from_frame_shortcut(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    monkeypatch.setattr(SupergramFrame, "_diagnose", lambda self: None)
    frame = SupergramFrame(None, None)
    frame.Show()

    class Enter:
        def GetKeyCode(self):
            return wx.WXK_RETURN

        def ControlDown(self):
            return False

    try:
        voice = {"id": 7, "content": {"@type": "messageVoiceNote",
                 "voice_note": {"voice": {"id": 9}}}}
        frame.state = "authorizationStateReady"
        frame.chat_id = 42
        frame._set_view()
        frame._ready(True)
        frame.messages = [voice]
        frame._render_messages()
        frame.message_list.SetFocus()
        wx.Yield()
        played = []
        frame._play_message = lambda message: played.append(message)
        frame._shortcuts(Enter())
        assert played == [voice]
        frame._message_char_hook(Enter())
        assert played == [voice, voice]
    finally:
        frame.Destroy()
