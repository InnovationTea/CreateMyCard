# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass


@dataclass(frozen=True)
class IDSSTSConfig:
    """IDS 调用所需的 STS 配置。

    入参：
    - access_key：IDS 签名使用的访问标识。
    - secret_key：IDS 签名使用的密钥。
    - dev_fake_id：IDS 请求头使用的设备调试标识。
    出参：不可变的 IDS STS 配置对象。
    """

    access_key: str
    secret_key: str
    dev_fake_id: str


class STSConfig:
    """安全配置读取入口。

    当前返回 mock 数据，后续接入安全区真实 STS 服务时，只需替换本类实现，
    IDSClient 无需感知配置来源变化。
    """

    def get_ids_config(self) -> IDSSTSConfig:
        """获取 IDS 使用的 STS 配置。

        入参：无。
        出参：IDS 签名和请求头所需的 mock 配置。
        """
        return IDSSTSConfig(
            access_key="23232323232",
            secret_key="22222",
            dev_fake_id="123**********postmantestdevFakeId",
        )
