"""Harmo-Dsp entry point — launches modern GUI (light/dark)."""
import sys


def check() -> int:
    """Self-check WITHOUT showing any window (for.launch diagnostics).

    Creates the real MainWindow offscreen; any import/widget error raises.
    Prints OK + versions. Return code 0 = GUI will start on your desktop.
    """
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    import PySide6
    import numpy, scipy
    from harmo_dsp.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    assert w.stack.count() == 5
    print(f"OK: Harmo-Dsp GUI starts (Qt {PySide6.__version__}, "
          f"numpy {numpy.__version__}, scipy {scipy.__version__})")
    try:
        import sounddevice  # optional (guided measurement only)
        print(f"OK: measurement audio backend present ({sounddevice.__version__})")
    except ImportError:
        print("INFO: sounddevice missing — guided measurement disabled, "
              "everything else works (pip install sounddevice)")
    return 0


def main() -> None:
    if "--check" in sys.argv:
        sys.exit(check())
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Harmo-Dsp")
    app.setOrganizationName("Harmo-Dsp")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
