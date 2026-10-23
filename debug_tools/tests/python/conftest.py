"""调试工具与微服务集成测试的公共导入环境。"""

from importlib import import_module

# 模型 SDK 会临时加入自己的同名 core 目录，预先绑定云侧基础包，避免收集顺序影响。
import_module("core")
