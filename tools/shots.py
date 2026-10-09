"""Render GUI pages headless -> docs/screens/*.png (Fase 2 evidence).

Run: python tools/shots.py   (no window appears; PNGs are the output)
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from harmo_dsp.ui.main_window import MainWindow  # noqa: E402

NAMES = ["1-import", "2-target", "3-autocorrect", "4-finetune", "5-export"]

FONTS = [r"C:\Windows\Fonts\segoeui.ttf",
         r"C:\Windows\Fonts\arial.ttf",
         r"C:\Windows\Fonts\tahoma.ttf"]


def main() -> None:
    app = QApplication.instance() or QApplication([])
    for fp in FONTS:
        fid = QFontDatabase.addApplicationFont(fp)
        if fid >= 0:
            print("font loaded:", fp)
            break
    out = os.path.join(os.path.dirname(__file__), "..", "docs", "screens")
    os.makedirs(out, exist_ok=True)
    w = MainWindow()
    w.resize(1280, 800)
    w.show()
    app.processEvents()
    for row, name in enumerate(NAMES):
        w.nav.setCurrentRow(row)
        app.processEvents()
        pix = w.grab()
        path = os.path.join(out, f"step-{name}.png")
        pix.save(path)
        print("saved", path)
    # light-theme variant of the EQ page
    w.theme.apply("light")
    w.nav.setCurrentRow(3)
    app.processEvents()
    path = os.path.join(out, "step-4-finetune-light.png")
    w.grab().save(path)
    print("saved", path)


if __name__ == "__main__":
    main()
