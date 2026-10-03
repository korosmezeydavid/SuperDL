"""AUD-001 címszűrés és AUD-003 HELLO-visszhang regresszió."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules_src" / "tavsegitseg"))
from tavsegitseg_mod.p2phalozat import P2PHalozat

PEER = ("192.0.2.20", 22222)
FOREIGN = ("192.0.2.30", 33333)


def receive(packets, candidates=(PEER,)):
    received, ready, sent = [], [], []
    net = P2PHalozat(received.append, lambda: ready.append(True))
    net.tars_jeloltek(candidates)
    net._fut = True
    queue = iter(packets)

    class Socket:
        def recvfrom(self, size):
            try:
                return next(queue)
            except StopIteration:
                net._fut = False
                return b"", PEER

        def sendto(self, data, addr):
            sent.append((data, addr))

    net._sock = Socket()
    net._fogado()
    return net, received, ready, sent


def test_foreign_data_before_and_after_handshake_is_dropped():
    net, data, ready, _ = receive([
        (b"\x01foreign-first", FOREIGN), (b"\x00", PEER),
        (b"\x01foreign-later", FOREIGN), (b"\x01valid", PEER),
        (b"\x01wrong-port", (PEER[0], PEER[1] + 1)),
    ])
    assert data == [b"valid"]
    assert net._peer == PEER
    assert ready == [True]


def test_unannounced_hello_cannot_pin_peer():
    net, data, ready, sent = receive([(b"\x00", FOREIGN), (b"\x01x", FOREIGN)])
    assert net._peer is None
    assert (data, ready, sent) == ([], [], [])


def test_repeated_hello_has_no_echo_and_only_one_ready_callback():
    _, _, ready, sent = receive([(b"\x00", PEER)] * 20)
    assert ready == [True]
    assert sent == []


def test_announced_data_can_complete_handshake():
    net, data, ready, _ = receive([(b"\x01first", PEER)])
    assert net._peer == PEER
    assert data == [b"first"]
    assert ready == [True]


def test_no_candidates_does_not_accept_data():
    net, data, ready, _ = receive([(b"\x01x", PEER)], candidates=())
    assert net._peer is None
    assert data == ready == []


def test_closing_transport_rejects_peer():
    net = P2PHalozat()
    net._fut = True
    net._closing = True
    net.tars_jeloltek([PEER])
    assert net._peer_rogzit(PEER) is False
