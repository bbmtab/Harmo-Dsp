"""Attach-plan tests on FAKE registries (no admin, no hardware)."""
from harmo_dsp.dsp import apo_attach as A


def _realtek_like():
    return {"LFX": None, "GFX": None,
            "SFX": "{DC253AB8-10DC-483c-AB5F-D6A4E189FD70}",
            "MFX": "{A296D363-EE83-4af9-9BE7-729C1296150A}",
            "EFX": None}


def test_plan_preserves_vendor_apo_as_child():
    plan = A.compute_attach_plan(_realtek_like(), {})
    assert plan["writes_fx"][f"{A.SLOT_PKEY},5"] == A.PRE_MIX
    assert plan["writes_fx"][f"{A.SLOT_PKEY},7"] == A.POST_MIX
    assert f"{A.SLOT_PKEY},1" in plan["deletes_fx"]  # LFX cleared (SFX/EFX mode)
    assert plan["child_pre"] == "{DC253AB8-10DC-483c-AB5F-D6A4E189FD70}"
    assert plan["child_backup"]["SFX"] == "{DC253AB8-10DC-483c-AB5F-D6A4E189FD70}"
    assert plan["version"] == "2"


def test_plan_idempotent_when_attached():
    cur = {"LFX": None, "GFX": None, "SFX": A.PRE_MIX, "MFX": None,
           "EFX": A.POST_MIX}
    plan = A.compute_attach_plan(cur, {})
    assert plan["child_pre"] is None  # APO GUIDs never chained as child
    assert plan["writes_fx"][f"{A.SLOT_PKEY},5"] == A.PRE_MIX


def test_detach_restores_originals():
    backup = {"LFX": None, "GFX": None,
              "SFX": "{DC253AB8-10DC-483c-AB5F-D6A4E189FD70}",
              "MFX": "{A296D363-EE83-4af9-9BE7-729C1296150A}", "EFX": None}
    plan = A.compute_detach_plan(backup)
    assert plan["writes_fx"][f"{A.SLOT_PKEY},5"] == backup["SFX"]
    assert f"{A.SLOT_PKEY},1" in plan["deletes_fx"]  # was absent -> removed


def test_guid_constants_wellformed():
    import re
    pat = re.compile(r"^\{[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}\}$")
    assert pat.match(A.PRE_MIX) and pat.match(A.POST_MIX)
    assert A.PRE_MIX != A.POST_MIX


def test_reg_backup_shape():
    txt = A.reg_backup_text("{GUID}", _realtek_like())
    assert txt.startswith("Windows Registry Editor Version 5.00")
    assert "FxProperties" in txt and "{DC253AB8" in txt
