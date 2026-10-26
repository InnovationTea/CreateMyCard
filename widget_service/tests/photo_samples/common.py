"""图片主题样例的公共展开入口。"""

import json
from types import SimpleNamespace

from services import post_layout_theme as themes
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.theme_style_roles import layout_phase


def expanded(rows, task):
    compact = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with layout_phase(True, task):
        source = convert_compact_dsl_to_a2ui(compact, size=task.get("size"))
    nodes = themes.components(themes.decode(source))
    return SimpleNamespace(compact=compact, source=source, nodes=nodes, task=task)
