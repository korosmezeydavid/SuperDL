"""TDLib-kérések és beszélő címkék a Windowsos Supergramhoz."""

import os
import re
from pathlib import Path


def parameters(api_id: int, api_hash: str, root: Path) -> dict:
    if api_id <= 0 or not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        raise ValueError("Hiányzó Telegram API-azonosító vagy hash.")
    return {
        "@type": "setTdlibParameters", "use_test_dc": False,
        "database_directory": str(root / "db"),
        "files_directory": str(root / "files"),
        "database_encryption_key": "", "use_file_database": True,
        "use_chat_info_database": True, "use_message_database": True,
        "use_secret_chats": False, "api_id": api_id, "api_hash": api_hash,
        "system_language_code": "hu", "device_model": "SuperDL Windows",
        "system_version": os.name, "application_version": "Supergram 0.3.12",
    }


def load_credentials(root: Path) -> tuple[int, str]:
    """Helyi beállítás elsőbbséggel; kiadott modulnál projektazonosító."""
    props = {}
    path = root / "telegram.local.properties"
    if not path.is_file():
        path = Path(__file__).resolve().parent / "telegram.public.properties"
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            props[key.strip()] = value.strip()
    api_id = (props.get("TELEGRAM_API_ID") or props.get("telegram.api_id")
              or props.get("telegram.api.id") or props.get("api_id"))
    api_hash = (props.get("TELEGRAM_API_HASH") or props.get("telegram.api_hash")
                or props.get("telegram.api.hash") or props.get("api_hash"))
    return int(api_id), str(api_hash)


def login_request(state: str, value: str) -> dict:
    value = value.strip()
    if not value:
        raise ValueError("A mező nem lehet üres.")
    if state == "authorizationStateWaitPhoneNumber":
        if not value.startswith("+") or not value[1:].isdigit():
            raise ValueError("A telefonszám országkóddal kezdődjön, például +36.")
        return {"@type": "setAuthenticationPhoneNumber", "phone_number": value,
                "settings": None}
    if state == "authorizationStateWaitCode":
        return {"@type": "checkAuthenticationCode", "code": value}
    if state == "authorizationStateWaitPassword":
        return {"@type": "checkAuthenticationPassword", "password": value}
    if state == "authorizationStateWaitEmailAddress":
        if "@" not in value:
            raise ValueError("Érvényes e-mail-címet adj meg.")
        return {"@type": "setAuthenticationEmailAddress", "email_address": value}
    if state == "authorizationStateWaitEmailCode":
        return {"@type": "checkAuthenticationEmailCode", "code": {
            "@type": "emailAddressAuthenticationCode", "code": value}}
    raise ValueError("Ez a belépési lépés itt még nem kezelhető.")


def text_message(chat_id: int, text: str, reply_to_message_id: int = 0) -> dict:
    if not chat_id or not text.strip():
        raise ValueError("Címzett és szöveg szükséges.")
    return {"@type": "sendMessage", "chat_id": chat_id,
            "topic_id": None, "reply_to": ({"@type": "inputMessageReplyToMessage",
                "message_id": reply_to_message_id, "quote": None, "checklist_task_id": 0}
                if reply_to_message_id else None), "options": None,
            "reply_markup": None, "input_message_content": {
                "@type": "inputMessageText", "text": {
                    "@type": "formattedText", "text": text, "entities": []},
                "link_preview_options": None, "clear_draft": False}}


def edit_text_message(chat_id: int, message_id: int, text: str) -> dict:
    if not chat_id or not message_id or not text.strip():
        raise ValueError("Saját üzenet és új szöveg szükséges.")
    return {"@type": "editMessageText", "chat_id": chat_id,
            "message_id": message_id, "reply_markup": None,
            "input_message_content": {"@type": "inputMessageText",
                "text": {"@type": "formattedText", "text": text, "entities": []},
                "link_preview_options": None, "clear_draft": False}}


def search_chat_messages(chat_id: int, query: str) -> dict:
    if not chat_id or not query.strip():
        raise ValueError("Nyitott beszélgetés és keresőszó szükséges.")
    return {"@type": "searchChatMessages", "chat_id": chat_id,
            "topic_id": None, "query": query.strip(), "sender_id": None,
            "from_message_id": 0, "offset": 0, "limit": 50, "filter": None}


def document_message(chat_id: int, path: Path) -> dict:
    path = Path(path)
    if not chat_id or not path.is_file():
        raise ValueError("Címzett és olvasható helyi fájl szükséges.")
    if path.stat().st_size == 0:
        raise ValueError("Üres fájl nem küldhető.")
    return {"@type": "sendMessage", "chat_id": chat_id,
            "topic_id": None, "reply_to": None, "options": None,
            "reply_markup": None, "input_message_content": {
                "@type": "inputMessageDocument", "document": {
                    "@type": "inputDocument", "document": {
                        "@type": "inputFileLocal", "path": str(path.resolve())},
                    "thumbnail": None, "disable_content_type_detection": True},
                "caption": None}}


def voice_message(chat_id: int, path: Path, duration: int) -> dict:
    path = Path(path)
    if not chat_id or duration <= 0 or path.suffix.lower() != ".ogg" or not path.is_file():
        raise ValueError("Címzett és elkészült OGG/Opus hangfelvétel szükséges.")
    if path.stat().st_size == 0:
        raise ValueError("Üres hangfelvétel nem küldhető.")
    return {"@type": "sendMessage", "chat_id": chat_id, "topic_id": None,
            "reply_to": None, "options": None, "reply_markup": None,
            "input_message_content": {"@type": "inputMessageVoiceNote",
                "voice_note": {"@type": "inputVoiceNote",
                    "voice_note": {"@type": "inputFileLocal", "path": str(path.resolve())},
                    "duration": duration, "waveform": ""}, "caption": None,
                "self_destruct_type": None}}


def history_request(chat_id: int, from_message_id: int = 0) -> dict:
    if not chat_id or from_message_id < 0:
        raise ValueError("Érvényes beszélgetés és üzenetazonosító szükséges.")
    return {"@type": "getChatHistory", "chat_id": chat_id,
            "from_message_id": from_message_id, "offset": 0,
            "limit": 50, "only_local": False}


def view_message_request(chat_id: int, message_id: int) -> dict:
    if not chat_id or not message_id:
        raise ValueError("Nincs kijelölt üzenet.")
    return {"@type": "viewMessages", "chat_id": chat_id,
            "message_ids": [message_id], "source": None, "force_read": True}


def merge_messages(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """TDLib oldalakat és élő frissítéseket egyesít azonosító szerint."""
    by_id = {int(item["id"]): item for item in existing if item.get("id")}
    by_id.update({int(item["id"]): item for item in incoming if item.get("id")})
    return sorted(by_id.values(), key=lambda item: int(item["id"]))


def message_attachment(message: dict) -> tuple[dict, str] | None:
    """A menthető TDLib-fájlt és javasolt nevét adja vissza."""
    content = message.get("content") or {}
    kind = content.get("@type")
    media_key, file_key, extension = {
        "messageDocument": ("document", "document", ".bin"),
        "messageAudio": ("audio", "audio", ".mp3"),
        "messageVideo": ("video", "video", ".mp4"),
        "messageVoiceNote": ("voice_note", "voice", ".ogg"),
        "messageAnimation": ("animation", "animation", ".mp4"),
    }.get(kind, (None, None, None))
    if kind == "messagePhoto":
        sizes = (content.get("photo") or {}).get("sizes") or []
        file = sizes[-1].get("photo") if sizes else None
        extension = ".jpg"
        name = None
    elif media_key:
        media = content.get(media_key) or {}
        file = media.get(file_key)
        name = media.get("file_name")
    else:
        return None
    if not isinstance(file, dict) or not int(file.get("id") or 0):
        return None
    safe_name = Path(name or "").name
    if not safe_name or safe_name in (".", ".."):
        safe_name = f"telegram-{int(message.get('id') or file['id'])}{extension}"
    return file, safe_name


def inline_buttons(message: dict) -> list[dict]:
    """A TDLib inline billentyűzetének sorrendben olvasható gombjai."""
    markup = message.get("reply_markup") or {}
    if markup.get("@type") != "replyMarkupInlineKeyboard":
        return []
    return [button for row in markup.get("rows") or [] for button in row
            if isinstance(button, dict) and button.get("text")]


def callback_button_request(chat_id: int, message_id: int, button: dict) -> dict:
    kind = button.get("type") or {}
    if kind.get("@type") != "inlineKeyboardButtonTypeCallback":
        raise ValueError("Ez a botgomb-típus még nem kezelhető.")
    if not chat_id or not message_id or not isinstance(kind.get("data"), str):
        raise ValueError("A botgomb adatai hiányosak.")
    return {"@type": "getCallbackQueryAnswer", "chat_id": chat_id,
            "message_id": message_id,
            "payload": {"@type": "callbackQueryPayloadData", "data": kind["data"]}}


def bot_button_action(button: dict) -> tuple[str, str]:
    """Az egyszerű helyi botgombok adatait ellenőrzi; nincs automatikus megnyitás."""
    kind = button.get("type") or {}
    button_type = kind.get("@type")
    if button_type == "inlineKeyboardButtonTypeCopyText" and kind.get("text"):
        return "copy", kind["text"]
    if button_type == "inlineKeyboardButtonTypeUrl":
        from urllib.parse import urlsplit
        url = kind.get("url") or ""
        parsed = urlsplit(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return "url", url
        raise ValueError("A botgomb hivatkozása nem nyitható meg biztonságosan.")
    return "callback", ""


def available_reaction_request(chat_id: int, message_id: int) -> dict:
    if not chat_id or not message_id:
        raise ValueError("Nincs kijelölt üzenet a reakcióhoz.")
    return {"@type": "getMessageAvailableReactions", "chat_id": chat_id,
            "message_id": message_id, "row_size": 8}


def reaction_choices(response: dict) -> list[dict]:
    """Csak a válaszban felajánlott, nem prémium emoji reakciók."""
    seen = set()
    choices = []
    for group in ("top_reactions", "recent_reactions", "popular_reactions"):
        for item in response.get(group) or []:
            kind = item.get("type") or {}
            emoji = kind.get("emoji")
            if (kind.get("@type") == "reactionTypeEmoji" and emoji
                    and not item.get("needs_premium") and emoji not in seen):
                seen.add(emoji)
                choices.append(kind)
    return choices


def add_reaction_request(chat_id: int, message_id: int, reaction: dict) -> dict:
    if (not chat_id or not message_id or
            reaction.get("@type") != "reactionTypeEmoji" or not reaction.get("emoji")):
        raise ValueError("Érvénytelen reakció vagy üzenet.")
    return {"@type": "addMessageReaction", "chat_id": chat_id,
            "message_id": message_id, "reaction_type": reaction,
            "is_big": False, "update_recent_reactions": True}


def message_label(message: dict) -> str:
    from datetime import datetime
    stamp = datetime.fromtimestamp(int(message.get("date") or 0)).strftime("%Y-%m-%d %H:%M")
    sender = "Én" if message.get("is_outgoing") else "Másik fél"
    content = message.get("content") or {}
    kind = content.get("@type")
    if kind == "messageText":
        body = (content.get("text") or {}).get("text") or "Üres szöveg"
    elif kind == "messageVoiceNote":
        body = "Hangüzenet; Enter: lejátszás vagy leállítás"
    elif kind in ("messageDocument", "messageAudio", "messageVideo", "messagePhoto"):
        media = content.get("document") or content.get("audio") or content.get("video") or {}
        body = ("Fénykép" if kind == "messagePhoto" else
                "Fájl: " + (media.get("file_name") or "név nélkül"))
        if kind == "messageAudio":
            body += "; Enter: lejátszás vagy leállítás"
    elif kind == "messageSticker":
        body = "Matrica"
    elif kind == "messageVideoNote":
        body = "Videóüzenet"
    elif kind == "messageAnimation":
        body = "Animáció"
    elif kind == "messageLocation":
        body = "Megosztott helyzet"
    elif kind == "messageContact":
        body = "Megosztott névjegy"
    elif kind == "messagePoll":
        question = (content.get("poll") or {}).get("question") or ""
        if isinstance(question, dict):
            question = question.get("text") or ""
        body = "Szavazás: " + str(question or "kérdés nélkül")
    else:
        body = "Nem támogatott üzenettípus" if kind else "Üres üzenetadat"
    buttons = inline_buttons(message)
    if buttons:
        body += f"; {len(buttons)} botgomb, Enterrel megnyitható"
    return f"{stamp}, {sender}: {body}"
