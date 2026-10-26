"""次数接口服务端参考建表合同，不依赖数据库 JSON 能力。"""

import re
from pathlib import Path


def _schema() -> str:
    source = Path(__file__).resolve().parents[1] / "sql" / "daily_usage.sql"
    lines = source.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("--"))


def test_request_list_is_plain_text_and_count_is_writable_integer():
    schema = _schema()
    assert re.search(r"request_id_hashes\s+TEXT\b", schema)
    assert re.search(r"used_count\s+INT\s+NOT NULL\s+DEFAULT 0", schema)
    assert not re.search(r"\bJSON\b|\bJSON_\w+\s*\(|\bGENERATED\b", schema, re.IGNORECASE)


def test_daily_row_uniqueness_is_user_and_date():
    schema = _schema()
    assert re.search(r"UNIQUE KEY uk_uid_date\s*\(uid_hash,\s*usage_date\)", schema)
    assert not re.search(r"\brequest_id_hash\b", schema)
