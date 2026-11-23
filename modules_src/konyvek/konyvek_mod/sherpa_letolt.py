"""A Sherpa hangok letöltésének felajánlása.

A Könyvek modul a hangfájlokat nem csomagolja be. Ha a gépen nincs Piper vagy
Supertonic hang, a program megkérdezi, és a hivatalos sherpa-onnx kiadásból
letölti a kiválasztottakat, a motorral együtt.
"""

import threading

import wx

from . import sherpa_voices


def offer(parent) -> bool:
    """Párbeszéd, aztán letöltés. Igaz, ha utána érdemes újratölteni a listát."""
    chosen = _choose(parent)
    if not chosen:
        return False
    return _run(parent, chosen)


def _choose(parent) -> list[str]:
    dlg = wx.Dialog(parent, title="Sherpa hangok letöltése")
    dlg.SetName("Sherpa hangok letöltése")
    v = wx.BoxSizer(wx.VERTICAL)
    text = wx.StaticText(
        dlg,
        label=("A Sherpa felolvasó a gépeden lévő nyílt hangokat használja, "
               "és a modul ezeket nem hozza magával. Letölthetem a hivatalos "
               "sherpa-onnx kiadásból. Anna egyedül is elég a könyvolvasáshoz. "
               "A motor és a magyar kiejtés adata ehhez jön, ha még nincs meg."))
    text.Wrap(520)
    v.Add(text, 0, wx.ALL, 10)
    box = wx.CheckListBox(
        dlg, choices=[item.label for item in sherpa_voices.OFFERS])
    box.SetName("Letölthető hangok")
    for i, item in enumerate(sherpa_voices.OFFERS):
        box.Check(i, item.checked)
    v.Add(box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
    buttons = dlg.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
    ok = dlg.FindWindowById(wx.ID_OK)
    if ok:
        ok.SetLabel("Letöltés")
    v.Add(buttons, 0, wx.EXPAND | wx.ALL, 8)
    dlg.SetSizerAndFit(v)
    dlg.CentreOnParent()
    if dlg.ShowModal() != wx.ID_OK:
        dlg.Destroy()
        return []
    picked = [sherpa_voices.OFFERS[i].offer_id
              for i in range(box.GetCount()) if box.IsChecked(i)]
    dlg.Destroy()
    if not picked:
        wx.MessageBox("Jelölj be legalább egy hangot.", "Sherpa hangok",
                      wx.OK | wx.ICON_INFORMATION, parent)
    return picked


def remove(parent) -> bool:
    installed = sherpa_voices.installed_offers()
    if not installed:
        wx.MessageBox("Nincs eltávolítható, SuperDL-lel letöltött hang.",
                      "Sherpa hangok", wx.OK | wx.ICON_INFORMATION, parent)
        return False
    with wx.SingleChoiceDialog(parent, "Melyik hangot távolítod el?",
                               "Sherpa hang eltávolítása",
                               [item.label for item in installed]) as dlg:
        if dlg.ShowModal() != wx.ID_OK:
            return False
        item = installed[dlg.GetSelection()]
    if wx.MessageBox(f"Eltávolítod ezt a hangcsomagot? {item.label}",
                     "Eltávolítás megerősítése",
                     wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, parent) != wx.YES:
        return False
    return _run(parent, [item.offer_id], removing=True)


def _run(parent, offer_ids: list[str], *, removing=False) -> bool:
    cancel = threading.Event()
    done = threading.Event()
    outcome = {"error": None, "progress": (0, "Kapcsolat ellenőrzése…")}
    title = "Hang eltávolítása" if removing else "Hangok letöltése"
    with wx.Dialog(parent, title=title) as dlg:
        layout = wx.BoxSizer(wx.VERTICAL)
        status = wx.TextCtrl(dlg, value="Eltávolítás folyamatban…" if removing else
                             "Kapcsolat ellenőrzése…", style=wx.TE_READONLY, size=(450, -1))
        status.SetName("Sherpa művelet állapota")
        layout.Add(status, 0, wx.EXPAND | wx.ALL, 10)
        gauge = wx.Gauge(dlg, range=100)
        gauge.SetName("Sherpa művelet előrehaladása")
        layout.Add(gauge, 0, wx.EXPAND | wx.ALL, 10)
        button = wx.Button(dlg, label="&Megszakítás")
        button.Enable(not removing)
        layout.Add(button, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        dlg.SetSizerAndFit(layout)

        def request_cancel(event):
            if event.GetEventType() == wx.EVT_CLOSE.typeId:
                event.Veto()
            if not removing:
                cancel.set()
                button.Disable()
                status.ChangeValue("Megszakítás folyamatban…")

        button.Bind(wx.EVT_BUTTON, request_cancel)
        dlg.Bind(wx.EVT_CLOSE, request_cancel)
        dlg.SetEscapeId(wx.ID_NONE)

        def progress(percent, message):
            outcome["progress"] = (percent, message)

        def work():
            try:
                if removing:
                    sherpa_voices.remove_voice(offer_ids[0])
                else:
                    sherpa_voices.check_connection(offer_ids[0])
                    if not cancel.is_set():
                        sherpa_voices.install(offer_ids, progress, cancel)
            except Exception as exc:
                outcome["error"] = exc
            finally:
                done.set()

        timer = wx.Timer(dlg)

        def tick(event):
            if done.is_set():
                dlg.EndModal(wx.ID_OK)
                return
            if not cancel.is_set() and not removing:
                percent, message = outcome["progress"]
                gauge.SetValue(max(0, min(100, int(percent))))
                if status.GetValue() != message:
                    status.ChangeValue(message)

        dlg.Bind(wx.EVT_TIMER, tick, timer)
        timer.Start(100)
        try:
            threading.Thread(target=work, daemon=True).start()
            dlg.ShowModal()
        finally:
            timer.Stop()

    if cancel.is_set():
        return True
    if outcome["error"]:
        wx.MessageBox(str(outcome["error"]), title + " – hiba",
                      wx.OK | wx.ICON_WARNING, parent)
        return False
    wx.MessageBox("A hangot eltávolítottuk." if removing else
                  "A hangok a gépeden vannak. A hanglista frissül.",
                  "Sherpa hangok", wx.OK | wx.ICON_INFORMATION, parent)
    return True
