"""FastMCP wiring (fastmcp package, MIT — same framework the example
rew-mcp-server acknowledges). Run: python -m harmo_dsp.mcp_server
"""
from __future__ import annotations
import sys

from . import tools


def build_server():
    from fastmcp import FastMCP
    mcp = FastMCP("harmo-dsp")

    mcp.tool(tools.check_backend)
    mcp.tool(tools.list_audio_devices)
    mcp.tool(tools.get_output_meter)
    mcp.tool(tools.import_measurement)
    mcp.tool(tools.push_ir_to_rew)
    mcp.tool(tools.save_graph)
    mcp.tool(tools.analyze_measurement)
    mcp.tool(tools.get_eq)
    mcp.tool(tools.set_eq)
    mcp.tool(tools.auto_eq)
    mcp.tool(tools.verify_config)
    mcp.tool(tools.check_levels)
    mcp.tool(tools.measure_sweep)
    mcp.tool(tools.time_align)
    mcp.tool(tools.design_fir)
    return mcp


EXAMPLE = """Add to your MCP client config (e.g. Claude Desktop):

  "mcpServers": {
    "harmo-dsp": {
      "command": "python",
      "args": ["-m", "harmo_dsp.mcp_server"]
    }
  }
"""


def main() -> None:
    if "--example" in sys.argv:
        print(EXAMPLE)
        return
    try:
        mcp = build_server()
    except ImportError:
        print("fastmcp missing — pip install fastmcp", file=sys.stderr)
        sys.exit(2)
    mcp.run()


if __name__ == "__main__":
    main()
