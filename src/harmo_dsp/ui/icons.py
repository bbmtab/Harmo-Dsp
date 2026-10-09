"""Icon provider — no binary assets, uses QStyle + emoji/unicode symbols."""
from PySide6.QtWidgets import QApplication, QStyle


# Logical name -> (QStyle.StandardPixmap, fallback unicode symbol)
_MAP = {
    "import": (QStyle.SP_DialogOpenButton, "📂"),
    "target": (QStyle.SP_ArrowUp, "🎯"),
    "auto": (QStyle.SP_MediaPlay, "✨"),
    "tune": (QStyle.SP_FileDialogDetailedView, "🎚"),
    "export": (QStyle.SP_DialogSaveButton, "💾"),
    "theme": (QStyle.SP_TitleBarShadeButton, "🌗"),
    "help": (QStyle.SP_DialogHelpButton, "❓"),
    "channel": (QStyle.SP_MediaVolume, "🔊"),
    "check": (QStyle.SP_DialogApplyButton, "✓"),
    "warn": (QStyle.SP_MessageBoxWarning, "⚠"),
    "back": (QStyle.SP_ArrowBack, "◀"),
    "next": (QStyle.SP_ArrowForward, "▶"),
}


def symbol(name: str) -> str:
    """Unicode fallback symbol, used in nav buttons and headers."""
    return _MAP.get(name, (None, "•"))[1]


def icon(name: str):
    """QIcon from QStyle, with graceful fallback to empty icon."""
    app = QApplication.instance()
    pix, _ = _MAP.get(name, (None, ""))
    if app is None or pix is None:
        from PySide6.QtGui import QIcon
        return QIcon()
    style = app.style()
    return style.standardIcon(pix)
