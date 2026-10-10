"""Measurement-device pickers + refresh (UMIK-1 aware)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_pick_prefers_umik_over_generic_usb():
    from harmo_dsp.io.audio import pick_measurement_mic
    ins = ["0: Microsoft Sound Mapper - Input",
           "1: Microphone (Umik-1  Gain: 18dB",
           "2: Microphone (3- USB Audio Device",
           "3: Microphone (DroidCam Virtual Au"]
    assert "Umik" in pick_measurement_mic(ins)


def test_pick_falls_back_to_usb_then_any_mic():
    from harmo_dsp.io.audio import pick_measurement_mic
    assert "USB" in pick_measurement_mic(
        ["0: Sound Mapper", "1: Microphone (3- USB Audio Device)"])
    assert "Microphone" in pick_measurement_mic(
        ["0: Sound Mapper", "1: Microphone Array"])


def test_pick_output_digital_realtek():
    from harmo_dsp.io.audio import pick_measurement_out
    outs = ["3: Sound Mapper", "4: Realtek Digital Output (Realtek(R) Audio)",
            "5: LG TV (NVIDIA)"]
    assert "Digital" in pick_measurement_out(outs)


def test_gui_panel_refresh_rescans_and_preselects_umik(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.pages import ImportPage
    from harmo_dsp.io import audio as A

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(A, "available", lambda: True)

    def fake_devs():
        return (["3: Sound Mapper",
                 "4: Realtek Digital Output (Realtek(R) Audio)"],
                ["0: Sound Mapper In",
                 "1: Microphone (Umik-1  Gain: 18dB",
                 "2: Microphone (3- USB Audio Device)"])

    monkeypatch.setattr(A, "devices", fake_devs)
    p = ImportPage()
    assert "Umik" in p.m_in.currentText()      # UMIK-1 preselected
    assert "Digital" in p.m_out.currentText()
    # re-scan button picks up a NEW device without app restart
    def fake_devs2():
        return (["3: Sound Mapper",
                 "4: Realtek Digital Output (Realtek(R) Audio)"],
                ["0: Sound Mapper In",
                 "9: Microphone (NEW-USB-TOY)",
                 "2: Microphone (3- USB Audio Device)"])

    monkeypatch.setattr(A, "devices", fake_devs2)
    p.m_refresh.click()
    assert "NEW-USB-TOY" in p.m_in.currentText()  # rescan picks up new usb mic
    p.close()
