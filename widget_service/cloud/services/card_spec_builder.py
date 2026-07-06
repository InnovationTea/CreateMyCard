# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from models.generation import CandidateDataBinding, CardSpec, WidgetSize


class CardSpecBuilder:
    def build(self, size: WidgetSize, effective_bindings: list[CandidateDataBinding]) -> CardSpec:
        """生成最终 CardSpec。

        入参：
        - size：最终建议卡片尺寸。
        - effective_bindings：能力过滤后仍可使用的数据绑定列表。
        出参：最终 CardSpec；没有有效数据能力时返回静态 CardSpec。
        """
        # 事件能力不进入 CardSpec；CardSpec 只携带运行时数据绑定。
        if not effective_bindings:
            return CardSpec(suggestSize=size)
        return CardSpec(suggestSize=size, dataBindings=effective_bindings)
