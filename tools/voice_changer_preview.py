"""Open the local Super Media voice changer for a headphone-only manual trial.

This preview does not touch an installed module or start the microphone until
the user activates the labelled Indítás button.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wx

from modules_src.supermedia.supermedia_mod.supervoicewin import VoiceChangerFrame


def main():
    app = wx.App(False)
    frame = VoiceChangerFrame(None)
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
