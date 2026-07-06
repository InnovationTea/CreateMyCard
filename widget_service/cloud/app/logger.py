# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from core.logger import DesensitizedErrorTool, get_logger

# 统一业务 logger 入口。业务代码统一使用 `from app.logger import logger`。
logger = get_logger("genui-agent-service")

__all__ = ["DesensitizedErrorTool", "logger"]
