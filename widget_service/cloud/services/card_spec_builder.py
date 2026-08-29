# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from models.generation import (
    CandidateDataBinding,
    CardSpec,
    CardSpecDataBinding,
    WidgetSize,
)


class CardSpecBuilder:
    def build(
        self,
        size: WidgetSize,
        effective_bindings: list[CandidateDataBinding],
        title: str,
        description: str,
    ) -> CardSpec:
        """生成最终 CardSpec。

        入参：
        - size：最终建议卡片尺寸。
        - effective_bindings：能力过滤后仍可使用的数据绑定列表。
        - title：第三个生成接口传入的卡片标题。
        - description：第三个生成接口传入的卡片说明。
        出参：最终 CardSpec；没有有效数据能力时返回静态 CardSpec。
        """
        # title/description 来自第三个生成接口，事件能力不进入 CardSpec。
        if not effective_bindings:
            return CardSpec(
                title=title,
                description=description,
                suggestSize=size,
            )
        return CardSpec(
            title=title,
            description=description,
            suggestSize=size,
            dataBindings=[
                CardSpecDataBinding(
                    capabilityId=item.capabilityId,
                    arguments=item.arguments,
                    writeResultTo=item.writeResultTo,
                )
                for item in effective_bindings
            ],
        )
