"""Offscreen smoke test — runs in GHA (no window shown)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_main_window_creates():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    assert w.stack.count() == 5
    # theme toggle works both ways
    assert w.theme.toggle() in ("light", "dark")
    assert w.theme.toggle() in ("light", "dark")
    # channel defaults to stereo 2.0
    assert w.channels.mode() == "stereo20"
    # session + FIR panel wired (phase path needs IRs, refuses without)
    assert isinstance(w.session, dict)
    assert w.page_auto.fir_strength.value() == 30  # conservative default
    assert w.page_export.conv_edit.text() == ""
    w.close()


def test_all_pages_have_guidance():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.pages import (
        ImportPage, TargetPage, AutoCorrectPage, FineTunePage, ExportPage,
    )

    app = QApplication.instance() or QApplication([])
    for cls in (ImportPage, TargetPage, AutoCorrectPage, FineTunePage, ExportPage):
        p = cls()
        assert p is not None
        p.close()
