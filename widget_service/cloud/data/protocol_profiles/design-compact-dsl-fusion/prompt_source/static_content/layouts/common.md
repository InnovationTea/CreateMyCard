---
name: static-layouts
description: 固定标题区与内容区的结构；不提供模型可调几何或排版变体。
---

# 固定卡片外框

## 总表
| 角色 | 适用条件 | 承载内容 | 使用边界 |
|---|---|---|---|
| header | 三项TextList以外的全部正文形态 | SingleLineTitle | 必填，左上对齐 |
| body | 必要正文 | 本尺寸正文组件 | 必填，按所选组件由Runtime排列 |

根使用本尺寸唯一的Layout ID，children按[header,body]排列，引用完整定义的组件ID；仅三项TextList用[body]。
标题使用SingleLineTitle，固定普通字重的小标题样式，位于左上安全区；标题区与正文区分别占用容量。
Runtime负责安全区、标题与内容区间距和背景；内容区占剩余空间。
列表和对比默认靠下；EmphasisText主结论靠左上，辅助位置由该组件合同确定。
组件内部依自身合同排列；列表不会被均分拉伸，背板由对应组件负责。
标题和内容相互独立，Runtime按组件形态保留适当留白。
