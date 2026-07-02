"""SuperDL modul – Internetes rádió.

Élő rádióállomások keresése és hallgatása, felvétellel és időzített felvétellel.
Az ablak és a kereső-backend (radio.py) + a felvétel-dialógusok a modulban; a
FELVEVŐ-SZOLGÁLTATÁS (radiorec.RecordManager) a Core-ban marad háttér-szolgáltatás-
ként (a `main._record_mgr`-t a rádióablak getattr-rel éri el), ezért az időzített
felvételek a Core-ban ütemeződnek. A lejátszó és a tároló is a Core-ból jön.

register(core): „Internetes rádió" menü + a rádióablak (egyablakosan)."""

_state = {}


def register(core):
    from .radiowin import RadioFrame

    opener = core.register_window("radio_module", RadioFrame)
    _sub = getattr(core, "add_submenu", None)
    menu = _sub("&Média", "Internetes &rádió") if _sub else core.add_menu("Internetes &rádió")
    item = core.add_menu_item(
        menu, "Internetes &rádió\tCtrl+Shift+R", opener,
        help="Élő rádióállomások keresése és hallgatása, felvétellel")
    _state["item"] = item
    core.log.info("radio modul betöltve")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
    core.log.info("radio modul leszerelve")
