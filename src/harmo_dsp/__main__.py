"""Harmo-Dsp entry point — launches modern GUI (light/dark)."""
import sys


def main() -> None:
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
