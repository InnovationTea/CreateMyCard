"""真机截图插件的兼容导入。"""

from ..postprocess_plugins.device_capture import (
    DeviceCaptureConfig,
    DeviceCaptureManager,
    DeviceRenderer,
)

__all__ = ["DeviceCaptureConfig", "DeviceCaptureManager", "DeviceRenderer"]
