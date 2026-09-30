"""macOS integration: system control, browsers, Apple apps and the alfredd bridge.

Everything here is imported lazily by the mac_* actions; nothing in this
package is loaded on Windows or Linux.
"""
import sys

IS_MAC = sys.platform == "darwin"


def require_mac() -> None:
    """Call at the top of a mac-only action so the loader skips it quietly elsewhere."""
    if not IS_MAC:
        raise ImportError("only supported on macOS")
