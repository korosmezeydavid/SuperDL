_item = None

def register(core):
    global _item
    from .window import LinkFrame
    opener = core.register_window('linkek_module', LinkFrame)
    menu = core.add_submenu('&Eszközök', '&Super Link')
    _item = core.add_menu_item(menu, '&Super Link…', opener,
        help='Linkrövidítés, mentett linkek és QR-kód készítése')

def unregister(core):
    global _item
    if _item is not None: core.remove_menu_item(_item)
    _item = None

