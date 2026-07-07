# 04-scoring-rules.md: Aesthetic Scoring Rules

## Scoring Dimensions & Weights
| Dimension | Weight | Pass Threshold |
|---|---|---|
| 基础可用性 (Basic Usability) | 25% | >=15 |
| 视觉一致性 (Visual Consistency) | 20% | >=12 |
| 信息层级 (Information Hierarchy) | 20% | >=12 |
| 交互合理性 (Interaction Reasonability) | 15% | >=9 |
| 原创性&设计感 (Originality & Design) | 20% | >=12 |
| **Total** | **100%** | **>=60** |

## Dimension Definitions
1. **基础可用性**: UI功能完整，没有损坏元素，文字清晰可读，没有重叠、截断、显示错误
2. **视觉一致性**: 颜色搭配和谐，字体、字号、间距统一，设计风格一致，没有突兀元素
3. **信息层级**: 视觉层次清晰，核心内容突出，信息组织逻辑符合用户使用习惯
4. **交互合理性**: 可点击区域大小合适，操作流程直观，反馈清晰明确
5. **原创性&设计感**: 设计有原创性，视觉吸引力强，符合现代UI设计规范

## Scoring Rules
- Score range: 0-100 points
- Any dimension score below its threshold → overall score unqualified (<60)
- Any critical issue (text overlap, broken elements, unreadable content) → automatic score <60
- All scoring results include detailed reasoning and improvement suggestions
