"""Super Surf modul bekötése a SuperDL menüjébe."""

_state = {}


def register(core):
    from .window import SuperSurfFrame

    opener = core.register_window(
        "supersurf_module", lambda parent: SuperSurfFrame(parent, core))
    submenu = getattr(core, "add_submenu", None)
    menu = submenu("&Eszközök", "&Super Surf") if submenu else core.add_menu("&Super Surf")
    _state["item"] = core.add_menu_item(
        menu, "&Super Surf – Kutatás és olvasás", opener,
        help="Wikipédia, cikkolvasó, időjárás, árfolyam és angol szótár")


def unregister(core):
    item = _state.pop("item", None)
    if item is not None:
        core.remove_menu_item(item)
