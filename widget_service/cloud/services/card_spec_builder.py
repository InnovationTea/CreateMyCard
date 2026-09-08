# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
from pathlib import Path

from models.generation import (
    CandidateDataBinding,
    CardSpec,
    CardSpecDataBinding,
    WidgetSize,
)

_ASSET_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "validator_rules" / "config" / "asset.json"
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
        # imageDomainWhitelist 来自 asset.json 的 allowedRemoteHosts，端侧据此放行外部图片域名。
        image_domain_whitelist = self._load_asset_domain_whitelist()
        # title/description 来自第三个生成接口，事件能力不进入 CardSpec。
        if not effective_bindings:
            return CardSpec(
                title=title,
                description=description,
                suggestSize=size,
                imageDomainWhitelist=image_domain_whitelist,
            )
        return CardSpec(
            title=title,
            description=description,
            suggestSize=size,
            imageDomainWhitelist=image_domain_whitelist,
            dataBindings=[
                CardSpecDataBinding(
                    capabilityId=item.capabilityId,
                    arguments=item.arguments,
                    writeResultTo=item.writeResultTo,
                )
                for item in effective_bindings
            ],
        )

    @staticmethod
    def _load_asset_domain_whitelist() -> list[str]:
        """读取 asset.json 的 allowedRemoteHosts 作为卡片外部图片域名白名单。"""
        try:
            asset_config = json.loads(_ASSET_CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        allowed_hosts = asset_config.get("allowedRemoteHosts", [])
        return allowed_hosts if isinstance(allowed_hosts, list) else []
