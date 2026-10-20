"""真机截图插件的兼容导入。"""

from ..postprocess_plugins.device_capture import (
    DeviceCaptureManager,
    DeviceRenderer,
)

__all__ = ["DeviceCaptureManager", "DeviceRenderer"]
