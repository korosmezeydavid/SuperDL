"""Windowsos Telegram alapműveletek: titkos bejelentkezés és szöveg."""

from pathlib import Path

import pytest

from modules_src.supergram.supergram_mod import protocol


def test_login_code_is_only_in_request_not_error():
    request = protocol.login_request("authorizationStateWaitCode", "123456")
    assert request == {"@type": "checkAuthenticationCode", "code": "123456"}
    with pytest.raises(ValueError, match="nem lehet üres"):
        protocol.login_request("authorizationStateWaitCode", " ")


def test_unhandled_auth_state_does_not_send_arbitrary_data():
    with pytest.raises(ValueError, match="még nem kezelhető"):
        protocol.login_request("authorizationStateWaitRegistration", "secret")


def test_send_text_requires_chat_and_keeps_formatted_text():
    with pytest.raises(ValueError):
        protocol.text_message(0, "hello")
    request = protocol.text_message(123, "Árvíztűrő tükörfúrógép")
    assert request["input_message_content"]["text"]["text"] == "Árvíztűrő tükörfúrógép"


def test_file_is_announced_as_file():
    message = {"date": 0, "content": {"@type": "messageAudio",
                                  "audio": {"file_name": "hang.mp3"}}}
    assert "Fájl: hang.mp3" in protocol.message_label(message)


def test_voice_note_uses_local_ogg_and_rejects_missing_recording(tmp_path):
    recording = tmp_path / "note.ogg"
    with pytest.raises(ValueError):
        protocol.voice_message(7, recording, 2)
    recording.write_bytes(b"OggS" + b"a" * 20)
    request = protocol.voice_message(7, recording, 2)
    content = request["input_message_content"]
    assert request["chat_id"] == 7
    assert content["@type"] == "inputMessageVoiceNote"
    assert content["voice_note"] == {
        "@type": "inputFileLocal", "path": str(recording.resolve())}
    assert content["duration"] == 2


def test_local_credentials_are_read_without_exposure(tmp_path):
    (tmp_path / "telegram.local.properties").write_text(
        "telegram.api_id=123\ntelegram.api_hash=" + "a" * 32, encoding="utf-8")
    assert protocol.load_credentials(Path(tmp_path)) == (123, "a" * 32)


def test_public_credentials_are_used_only_without_local_override(monkeypatch, tmp_path):
    package = tmp_path / "supergram_mod"
    package.mkdir()
    (package / "telegram.public.properties").write_text(
        "telegram.api_id=456\ntelegram.api_hash=" + "b" * 32,
        encoding="utf-8")
    monkeypatch.setattr(protocol, "__file__", str(package / "protocol.py"))
    user_root = tmp_path / "user"
    user_root.mkdir()
    assert protocol.load_credentials(user_root) == (456, "b" * 32)
    (user_root / "telegram.local.properties").write_text(
        "telegram.api_id=123\ntelegram.api_hash=" + "a" * 32,
        encoding="utf-8")
    assert protocol.load_credentials(user_root) == (123, "a" * 32)


def test_history_pages_and_live_message_merge_without_duplicate_or_reordering():
    latest = [{"id": 30, "date": 3}, {"id": 20, "date": 2}]
    older = [{"id": 20, "date": 2}, {"id": 10, "date": 1}]
    live = {"id": 40, "date": 4}
    result = protocol.merge_messages(latest, older + [live])
    assert [item["id"] for item in result] == [10, 20, 30, 40]
    assert protocol.history_request(7, 9)["from_message_id"] == 9


def test_read_receipt_targets_only_selected_message():
    request = protocol.view_message_request(7, 42)
    assert request == {"@type": "viewMessages", "chat_id": 7,
                       "message_ids": [42], "source": None, "force_read": True}


def test_document_send_uses_local_file_and_disables_media_type_conversion(tmp_path):
    attachment = tmp_path / "hang.mp3"
    attachment.write_bytes(b"example")
    request = protocol.document_message(7, attachment)
    content = request["input_message_content"]
    assert content["@type"] == "inputMessageDocument"
    assert content["document"] == {
        "@type": "inputDocument",
        "document": {"@type": "inputFileLocal", "path": str(attachment.resolve())},
        "thumbnail": None,
        "disable_content_type_detection": True,
    }
    with pytest.raises(ValueError, match="Üres fájl"):
        attachment.write_bytes(b"")
        protocol.document_message(7, attachment)


def test_received_document_and_voice_have_safe_save_names():
    document = {"id": 100, "content": {"@type": "messageDocument",
                "document": {"file_name": "..\\hang.mp3",
                             "document": {"id": 77, "local": {}}}}}
    assert protocol.message_attachment(document) == (
        {"id": 77, "local": {}}, "hang.mp3")
    voice = {"id": 101, "content": {"@type": "messageVoiceNote",
             "voice_note": {"voice": {"id": 78}}}}
    assert protocol.message_attachment(voice) == ({"id": 78}, "telegram-101.ogg")
    assert protocol.message_attachment({"content": {"@type": "messageText"}}) is None


def test_reactions_are_chosen_from_server_options_without_premium():
    assert protocol.available_reaction_request(7, 9) == {
        "@type": "getMessageAvailableReactions", "chat_id": 7,
        "message_id": 9, "row_size": 8}
    response = {"top_reactions": [
        {"type": {"@type": "reactionTypeEmoji", "emoji": "👍"}, "needs_premium": False},
        {"type": {"@type": "reactionTypeEmoji", "emoji": "⭐"}, "needs_premium": True}],
        "recent_reactions": [
            {"type": {"@type": "reactionTypeEmoji", "emoji": "👍"}},
            {"type": {"@type": "reactionTypeEmoji", "emoji": "❤️"}}]}
    choices = protocol.reaction_choices(response)
    assert [item["emoji"] for item in choices] == ["👍", "❤️"]
    assert protocol.add_reaction_request(7, 9, choices[0]) == {
        "@type": "addMessageReaction", "chat_id": 7, "message_id": 9,
        "reaction_type": choices[0], "is_big": False,
        "update_recent_reactions": True}
    with pytest.raises(ValueError):
        protocol.add_reaction_request(7, 9, {"@type": "reactionTypePaid"})


def test_bot_copy_and_url_actions_require_valid_data():
    assert protocol.bot_button_action({"type": {
        "@type": "inlineKeyboardButtonTypeCopyText", "text": "kód"}}) == ("copy", "kód")
    assert protocol.bot_button_action({"type": {
        "@type": "inlineKeyboardButtonTypeUrl", "url": "https://example.org/"}}) == (
            "url", "https://example.org/")
    with pytest.raises(ValueError):
        protocol.bot_button_action({"type": {
            "@type": "inlineKeyboardButtonTypeUrl", "url": "file:///secrets"}})
    assert protocol.bot_button_action({"type": {
        "@type": "inlineKeyboardButtonTypeCallback", "data": "abc"}}) == ("callback", "")
