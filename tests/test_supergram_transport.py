"""A TDLib-események sorrendjét és az @extra válaszpárosítást őrizzük."""

import importlib.util
import json
import threading
from pathlib import Path


_PATH = Path(__file__).resolve().parents[1] / "modules_src" / "supergram" / "supergram_mod" / "transport.py"
_SPEC = importlib.util.spec_from_file_location("supergram_transport_test", _PATH)
transport = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(transport)


class FakeTdlib:
    def __init__(self):
        self.sent = []
        self.incoming = []
        self.lock = threading.Lock()

    def td_create_client_id(self):
        return 7

    def td_send(self, client_id, payload):
        assert client_id == 7
        self.sent.append(json.loads(payload))

    def td_receive(self, _timeout):
        with self.lock:
            return self.incoming.pop(0) if self.incoming else None


def test_ordered_updates_and_correlated_response():
    fake = FakeTdlib()
    got = []
    done = threading.Event()

    def capture(kind, event):
        got.append((kind, event["value"]))
        if len(got) == 3:
            done.set()

    client = transport.TdTransport(fake, lambda e: capture("update", e),
                                   lambda extra, e: capture(extra, e))
    client.start()
    extra = client.send({"@type": "getMe"})
    with fake.lock:
        fake.incoming.extend(json.dumps(e).encode("utf-8") for e in [
            {"@client_id": 7, "@type": "updateUser", "value": 1},
            {"@client_id": 7, "@type": "user", "@extra": extra, "value": 2},
            {"@client_id": 7, "@type": "updateNewMessage", "value": 3},
        ])
    assert done.wait(2)
    client.stop()
    assert got == [("update", 1), (extra, 2), ("update", 3)]
    assert fake.sent[0]["@type"] == "getMe"
    assert fake.sent[-1]["@type"] == "close"
