"""Harmo-Dsp MCP server: AI assistants drive OUR OWN DSP core (no REW wrap).

Design differs from the MIT example rew-mcp-server (which proxies REW's
REST API): here the tools call harmo_dsp's own measurement/FIR/EQ/APO
modules directly. Headless — no Qt, no GUI dependency. Session state
(measurements, IRs, EQ) lives in this process only.
"""
