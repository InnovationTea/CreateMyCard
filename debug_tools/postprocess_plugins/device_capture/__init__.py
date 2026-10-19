"""真机截图插件。"""

from ...device_debug.runner import DeviceRenderer
from .plugin import DeviceCaptureManager, run_builtin

__all__ = ["DeviceCaptureManager", "DeviceRenderer", "run_builtin"]
