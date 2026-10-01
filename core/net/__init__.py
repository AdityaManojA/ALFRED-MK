"""core/net — Network transport guards and connection lifecycle utilities."""
from core.net.loop_guard import install_transport_guard, WINSOCK_CONNRESET

__all__ = ["install_transport_guard", "WINSOCK_CONNRESET"]
