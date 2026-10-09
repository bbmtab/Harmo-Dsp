"""Central help texts for uncommon functions.

Each entry: key -> (short tooltip, long popup explanation).
Shown via InfoButton (?) + tooltips so users know what to do.
"""
HELP: dict[str, tuple[str, str]] = {
    "smoothing": (
        "Smoothing: average nearby points",
        "Smoothing merges nearby frequency points so the graph is easier to read.\n"
        "1/3 octave = general view. 1/12 = more detail.\n"
        "It does not change the correction, only the display.",
    ),
    "tilt": (
        "Tilt: slope of the target",
        "Tilt makes treble slightly lower than bass (e.g. -1 dB/octave).\n"
        "Many listeners prefer a small downward slope over perfectly flat.",
    ),
    "q_factor": (
        "Q: width of a filter band",
        "High Q = narrow, precise cut (good for bass peaks).\n"
        "Low Q = wide, gentle change (use above ~500 Hz).\n"
        "Drag with mouse wheel on the graph to change Q.",
    ),
    "boost_limit": (
        "Boost limit: max allowed lift",
        "Never boost deep narrow dips (nulls) — they come from the room,\n"
        "not the speaker, and boosting only wastes power.\n"
        "Default +6 dB is safe. Cutting peaks is always preferred.",
    ),
    "preamp": (
        "Preamp: automatic anti-clipping",
        "If filters add gain, the app lowers overall volume\n"
        "by the same amount so sound never distorts (clips).",
    ),
    "null": (
        "Null: dip that must not be boosted",
        "A null is a deep narrow valley caused by room reflections.\n"
        "It changes when you move the mic, so correction is skipped there.",
    ),
    "multi_pos": (
        "Multi-position average",
        "Measure at 2-3 head positions, the app averages them.\n"
        "Areas that differ a lot between positions get less correction.",
    ),
    "group_delay": (
        "Group delay: timing vs frequency",
        "Shows if some frequencies arrive later than others.\n"
        "Only shown when you import impulse (.wav). Lower is better.",
    ),
    "pre_ringing": (
        "Pre-ringing risk of FIR filters",
        "Sharp phase correction can create a faint echo BEFORE a sound.\n"
        "Keep 'phase strength' low to stay safe.",
    ),
    "apo_include": (
        "Include line for Equalizer APO",
        "Equalizer APO reads C:\\Program Files\\EqualizerAPO\\config\\config.txt.\n"
        "The app writes its own file and only adds an Include line\n"
        "after backup + your confirmation.",
    ),
    "hp_protect": (
        "Protective high-pass (default OFF)",
        "Cuts very low bass to protect small PC speakers.\n"
        "Turn on only if your speakers distort on bass.",
    ),
    "channel_21": (
        "2.1 channels: stereo + subwoofer",
        "Left + Right + one sub (LFE). Crossover frequency sets\n"
        "where bass moves from speakers to the sub.",
    ),
}
