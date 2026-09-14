# -*- coding: utf-8 -*-
"""Super Edit kiprobalasa forrasbol, a Core elindítása nélkül."""
import os, sys
GY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, GY)
sys.path.insert(0, os.path.join(GY, "modules_src", "superedit"))
import wx
from superedit_mod.szerkesztowin import SuperEditFrame

app = wx.App()
frame = SuperEditFrame(None)
frame.Show()
frame.Raise()
frame.szerk.SetFocus()
app.MainLoop()
