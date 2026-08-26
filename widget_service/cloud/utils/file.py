# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from pathlib import Path


def save_txt_file(file_path: str | Path, content: str) -> None:
    """将文本内容保存到指定文件。

    入参：
    - file_path：目标文件路径；父目录不存在时自动创建。
    - content：需要写入的 UTF-8 文本。
    出参：无。
    """
    target_path = Path(file_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8", newline="\n")


def delete_file(file_path: str | Path) -> None:
    """删除指定文件。

    入参：
    - file_path：待删除文件路径。
    出参：无；文件不存在时按已删除处理。
    """
    Path(file_path).unlink(missing_ok=True)
