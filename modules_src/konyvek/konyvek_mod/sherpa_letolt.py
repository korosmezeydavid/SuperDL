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


def _run(parent, offer_ids: list[str]) -> bool:
    cancel = threading.Event()
    outcome = {"error": None}
    dlg = wx.ProgressDialog(
        "Hangok letöltése", "Indul a letöltés…", 100, parent,
        wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME
        | wx.PD_REMAINING_TIME | wx.PD_AUTO_HIDE)

    def progress(percent: int, message: str) -> None:
        wx.CallAfter(_tick, dlg, cancel, percent, message)

    def work():
        try:
            sherpa_voices.install(offer_ids, progress, cancel)
        except Exception as exc:
            outcome["error"] = exc
        wx.CallAfter(_finish, dlg)

    wx.CallAfter(lambda: threading.Thread(target=work, daemon=True).start())
    dlg.ShowModal()
    dlg.Destroy()
    if outcome["error"] and not cancel.is_set():
        wx.MessageBox(str(outcome["error"]), "A letöltés megállt",
                      wx.OK | wx.ICON_WARNING, parent)
        return False
    if cancel.is_set():
        return True
    wx.MessageBox(
        "A hangok a gépeden vannak. A lista most frissül, és a Hang "
        "meghallgatása gombbal ki lehet próbálni őket.",
        "Sherpa hangok", wx.OK | wx.ICON_INFORMATION, parent)
    return True


def _tick(dlg, cancel, percent, message):
    if not dlg:
        return
    try:
        keep = dlg.Update(max(0, min(100, int(percent))), message)
    except RuntimeError:
        return
    if not keep:
        cancel.set()


def _finish(dlg):
    try:
        if dlg.IsShown():
            dlg.EndModal(wx.ID_OK)
    except RuntimeError:
        pass
