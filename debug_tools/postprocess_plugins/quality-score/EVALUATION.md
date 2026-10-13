# 单批 Web 质量评估方案

本文件的参数块是评分器与页面的唯一参数来源。修改后须重启服务并重新评分；历史结果及其参数快照不改写。
页面把同一个参数块展开为权重与规则表，以下 JSON 可供离线审阅和编辑。

## 参数与规则

<!-- scoring-policy:start -->
```json
{
  "version": "consequence-comparison-v2",
  "weights": {
    "function": 0.5,
    "visibility": 0.3,
    "layout": 0.15,
    "style": 0.05
  },
  "degrees": {
    "severe": 1,
    "medium": 0.5,
    "minor": 0.2
  },
  "non_deducting_rules": {
    "event.phone_target_unresolved": "informational on both sides",
    "review.confirmed_missing_recipient": "informational only when evidence.requirement == phone_target"
  },
  "formula": "100 * (1 - sum(weight * min(1, sum(deduplicated impact))))",
  "reject_score": 0,
  "parameters_origin": "user_approved_provisional_policy",
  "rules": {
    "input.query_missing": [
      "function",
      "severe",
      true
    ],
    "binding.schema_type": [
      "function",
      "medium",
      true
    ],
    "event.phone_target_unresolved": [
      "function",
      "severe",
      false
    ],
    "review.confirmed_missing_recipient": [
      "function",
      "severe",
      true
    ],
    "review.confirmed_missing_declaration": [
      "function",
      "severe",
      true
    ],
    "review.confirmed_unsupported_capability": [
      "function",
      "severe",
      true
    ],
    "review.confirmed_missing_binding": [
      "function",
      "severe",
      true
    ],
    "review.confirmed_incorrect_target": [
      "function",
      "severe",
      true
    ],
    "content.integration_placeholder": [
      "function",
      "severe",
      true
    ],
    "content.development_note": [
      "function",
      "medium",
      true
    ],
    "semantic.required_action_unproven": [
      "function",
      "severe",
      false
    ],
    "semantic.required_display_unproven": [
      "function",
      "severe",
      false
    ],
    "semantic.upstream_degradation": [
      "function",
      "medium",
      false
    ],
    "event.argument_schema": [
      "function",
      "medium",
      false
    ],
    "protocol.profile_diagnostics": [
      "function",
      "medium",
      false
    ],
    "protocol.check_failed": [
      "function",
      "medium",
      false
    ],
    "runtime.renderer_diagnostic": [
      "function",
      "medium",
      false
    ],
    "content.preview_state_needs_context": [
      "function",
      "medium",
      false
    ],
    "content.state_needs_context": [
      "function",
      "medium",
      false
    ],
    "content.static_pending_state": [
      "function",
      "medium",
      false
    ],
    "text.capacity_exceeded": [
      "visibility",
      "medium",
      false
    ],
    "text.clipped": [
      "visibility",
      "medium",
      true
    ],
    "text.overflow": [
      "visibility",
      "medium",
      true
    ],
    "text.wrapped_row_budget": [
      "visibility",
      "medium",
      false
    ],
    "layout.clipped_content": [
      "visibility",
      "medium",
      true
    ],
    "layout.zero_area": [
      "visibility",
      "severe",
      true
    ],
    "layout.overflow": [
      "visibility",
      "medium",
      true
    ],
    "layout.severe_overlap": [
      "visibility",
      "severe",
      true
    ],
    "layout.row_gap_overflow": [
      "visibility",
      "medium",
      true
    ],
    "layout.list_gap_overflow": [
      "visibility",
      "medium",
      false
    ],
    "layout.list_viewport_insufficient": [
      "visibility",
      "medium",
      false
    ],
    "layout.list_host_budget_insufficient": [
      "visibility",
      "medium",
      false
    ],
    "resource.missing_asset": [
      "visibility",
      "medium",
      false
    ],
    "resource.missing_build_asset": [
      "visibility",
      "medium",
      false
    ],
    "resources.missing_build_asset": [
      "visibility",
      "medium",
      false
    ],
    "visual.aspect_ratio": [
      "visibility",
      "medium",
      true
    ]
  },
  "uncertainty": "confirmed score + interval including unresolved suspected findings",
  "severity_note": "Old P1/P2 are retained for provenance, not directly equated to the three impact levels.",
  "prefix_rules": [
    {
      "prefixes": [
        "ACTION.",
        "BUTTON.",
        "SCENE."
      ],
      "category": "function"
    },
    {
      "prefixes": [
        "COPY.",
        "TYPE.",
        "CONTRAST.",
        "ICON.",
        "ASSET.",
        "VISUAL.CONTRAST",
        "GEOMETRY.CLIP",
        "GEOMETRY.OVER"
      ],
      "category": "visibility"
    },
    {
      "prefixes": [
        "SPACING.",
        "SLOT.",
        "DENSITY.",
        "AREA.",
        "LAYOUT2X4.",
        "GEOMETRY.",
        "RECONCILE.DIMENSION_"
      ],
      "category": "layout"
    },
    {
      "prefixes": [
        "COLOR.",
        "GRADIENT.",
        "SHAPE.",
        "VISUAL.",
        "RECONCILE.COLOR_",
        "RECONCILE.OPACITY_"
      ],
      "category": "style"
    }
  ]
}
```
<!-- scoring-policy:end -->

## 计算步骤

1. 将检查记录按明确规则或有序前缀映射到维度与严重程度；未映射记录保留待评。
2. 同根因优先合并，否则按类别、问题族与组件合并，避免重复扣分。每组取影响最大项。
3. 类别风险为组内严重程度之和，累计上限为 1；扣分为 100 × 类别权重 × 类别风险。
4. 得分为 100 减去各类扣分。上界仅计算确认问题，下界额外计入待确认问题。这不是统计置信区间。

## 淘汰与待评

确认的结构或 Web 渲染硬失败得 0 分；疑似硬失败只影响下界，不伪装成确认淘汰。
缺少最终 DSL、证据不完整、DSL 或渲染上下文发生变化、截图哈希不匹配时一律待评。
拨号没有提供号码沿用不扣分口径，不代表已验证真实拨号成功。

## 批次与子集

进入页面和选择批次不会触发评分。先选择并确认样本，再显式运行；每次运行保存独立 execution。
count 表示批次原始顺序前 N 条，sampleIds 表示明确 ID 子集，二者互斥。空集、重复或未知 ID 拒绝。
画廊依赖仍可能采集整批或复用历史，但只有所选样本进入评分与汇总。

## 对比口径

默认读取两边最新已落盘终态的评分结果，也可明确选择历史执行。读取结果不会触发评分。
相同样本 ID 只有在 query、size 快照和评分方案均一致时才计算分差；缺失侧和待评分数不是 0 分。
问题频次按每张卡每个规则 code 去重统计，并分别统计确认和待确认记录；不把日志行数当成缺陷个数。
通过率仅指无确认/待确认问题、上下界都为满分且证据完整的样本数除以所选总数，待评不计通过。
只有两边样本集合、query/size 和评分口径均一致才展示总体通过率差；否则展示各自指标与限制。

## 检查边界

当前自动检查包括 Web 文字截断/省略、画布越界、文字矩形重叠候选、图片加载及解析诊断。
文字矩形相交只是待确认问题；滚动区域与隐藏状态不推断为内容错误。
不证明真实 Intent 执行、完整 Query 语义、设备权限、端侧一致性、品牌色板或整体审美。
100 分只是已声明范围内未扣分，不代表训练数据验收；插件 success 只是程序执行成功。
