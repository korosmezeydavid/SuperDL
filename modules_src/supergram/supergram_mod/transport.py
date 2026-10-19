"""TDLib JSON eseményhíd: egyetlen fogadószál, párosított válaszok.

A callbackek a fogadószálon futnak; a wx felületnek wx.CallAfter-rel kell
átadnia őket. Üzenetet, kódot és jelszót nem naplózunk.
"""

import json
import threading
from itertools import count


class TdTransport:
    def __init__(self, lib, on_update, on_response):
        self._lib = lib
        self._on_update = on_update
        self._on_response = on_response
        self._client_id = 0
        self._thread = None
        self._stop = threading.Event()
        self._send_lock = threading.Lock()
        self._serial = count(1)

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._client_id = self._lib.td_create_client_id()
        if not self._client_id:
            raise RuntimeError("A Telegram-munkamenet nem jött létre.")
        self._thread = threading.Thread(target=self._receive_loop, daemon=True,
                                        name="Supergram-TDLib")
        self._thread.start()

    def send(self, request: dict) -> str:
        if not self._client_id or self._stop.is_set():
            raise RuntimeError("A Telegram-kapcsolat nem aktív.")
        with self._send_lock:
            extra = f"supergram-{next(self._serial)}"
            payload = dict(request)
            payload["@extra"] = extra
            self._lib.td_send(self._client_id,
                              json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            return extra

    def _receive_loop(self):
        while not self._stop.is_set():
            try:
                raw = self._lib.td_receive(0.25)
                if not raw:
                    continue
                event = json.loads(bytes(raw).decode("utf-8"))
                if event.get("@client_id") not in (None, self._client_id):
                    continue
                if "@extra" in event:
                    self._on_response(event["@extra"], event)
                else:
                    self._on_update(event)
            except Exception as exc:
                if not self._stop.is_set():
                    self._on_update({"@type": "transportError", "message": str(exc)})
                break

    def stop(self):
        if not self._client_id:
            return
        try:
            if not self._stop.is_set():
                self.send({"@type": "close"})
        finally:
            self._stop.set()
            if self._thread and self._thread is not threading.current_thread():
                self._thread.join(timeout=2)
            self._thread = None
            self._client_id = 0
