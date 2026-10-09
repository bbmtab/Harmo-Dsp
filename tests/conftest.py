"""Qt lifetime management: widgets must die BEFORE QApplication.

Without this, test-local `app`/`w` variables are garbage-collected in
arbitrary order at interpreter exit -> "Fatal Python error: Aborted"
after a green run (silent exit-1 in CI).
"""
import gc

import pytest


@pytest.fixture(scope="session", autouse=True)
def _qt_lifetime():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    for w in list(app.topLevelWidgets()):
        try:
            w.close()
            w.deleteLater()
        except RuntimeError:
            pass
    try:
        app.processEvents()
        app.quit()
    except RuntimeError:
        pass
    gc.collect()
