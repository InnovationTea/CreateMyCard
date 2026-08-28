# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    """读取 JSON 文件。

    入参：
    - path：JSON 文件路径。
    出参：反序列化后的 Python 对象。
    """
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
