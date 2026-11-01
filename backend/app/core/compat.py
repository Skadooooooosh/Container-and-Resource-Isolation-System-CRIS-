import os
import sys
from typing import Optional, Tuple

class PlatformNotSupported(Exception):
    """Raised when a Linux-specific feature is accessed on a non-Linux platform."""
    pass

def get_euid() -> Optional[int]:
    """Returns the effective user ID on Linux, or None on other platforms."""
    if sys.platform == "linux":
        try:
            return os.geteuid()
        except AttributeError:
            return None
    return None

def sysconf(name: str) -> Optional[int]:
    """Returns system configuration values on Linux, or None on other platforms."""
    if sys.platform == "linux":
        try:
            return os.sysconf(name)
        except (AttributeError, ValueError):
            return None
    return None

def get_loadavg() -> Optional[Tuple[float, float, float]]:
    """Returns system load average on Linux, or None on other platforms."""
    if sys.platform == "linux":
        try:
            return os.getloadavg()
        except AttributeError:
            return None
    return None
