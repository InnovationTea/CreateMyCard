# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""蓝区构建使用的多步骤生成桥接占位实现。"""


class JsxA2UIBridge:
    """保留绿区桥接类接口，避免关闭功能时导入失败。"""

    async def generate(self, task_spec: object, size: object) -> None:
        """在蓝区明确拒绝执行未部署的多步骤生成逻辑。"""
        del task_spec, size
        raise RuntimeError("multi-step generation is unavailable in this deployment")
