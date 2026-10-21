# 本轮标准 A2UI 编辑协议

参考《鸿蒙桌面卡片A2UI协议完整规范》的 Form 子集。此处只说明编辑所需写法，运行时注入的
editContract 是当前支持范围；不因完整规范提供某能力就擅自新增。字段与枚举取交集。
editContract.editableStyleValueRules 提供本轮编辑字段值的类型、对象结构与范围合同，
与程序检查共用；未改变的历史兼容字段原样保留，不能从历史写法推断本轮新增值合法。

1. Form 不接受组件树的流式增量更新。patch 是云侧内部编辑协议，服务会合成完整产物；layout
   直接输出原卡对应的 createSurface、updateComponents、updateDataModel 三条完整消息。
   每条 version、surfaceId、catalogId 和原 root 保持；createSurface 不新增 theme。
2. 组件为 {id, component, ...业务属性, styles}。content、children、onClick 是组件顶层字段；
   Row/Column.itemMargin、List.space 也是顶层属性。不要把间距顶层字段放进 styles。
   Row 主轴水平、Column 主轴垂直；spaceBetween/spaceAround/spaceEvenly 下 itemMargin 不生效。
   Stack 后面的子节点位于上层，改 children 时保护背景与内容的层级关系和点击归属。
3. children 可为 ID 数组，也可能为包含 componentId/path 等信息的列表模板对象。
   原模板对象、动态表达式、循环上下文和事件对象须逐字段原样保留，不展开为首帧静态列表。
   不新增表达式，不把动态值、图标或状态固化成静态值。
   原样保留动态样式所在组件、属性及对象内部路径。替换整个样式对象时，允许修改获准的静态
   兄弟字段，但动态子字段必须逐字保留，不删除或移动。容器也不能重复引用或多父挂载；
   动态列表的模板 componentId 是一条结构引用，不为首帧数据复制模板。新增容器必须从 root 可达。
4. fontSize/minFontSize/maxFontSize 为数值，单位 fp；常规布局数值默认为 vp，百分比相对父区。
   云侧不知道 fp 与 vp 的端侧缩放关系和真实宿主尺寸，不能据此承诺实际像素无裁切。
   自适应字号需有效的最小/最大字号组合及行数或布局约束；仅改一个边界不保证生效。
   不新增 lineHeight 等 editContract 没有开放的属性；原卡已有但本轮不可编辑的属性保持原样。
5. 当前编辑尺寸使用正数、正百分比或 matchParent；不要从 2x2/2x4 推算真实宽高。
   间距、圆角本轮修改使用非负有限数值；不使用数组。分边 padding/margin 用 top/right/bottom/left，
   分角 borderRadius 用 topLeft/topRight/bottomLeft/bottomRight。对象中保留未涉及的原字段。
6. 颜色优先 #AARRGGBB，不能使用颜色名或 CSS rgb()。linearGradient 为对象，colors 是
   [["#FF81D8D0",0],["#FFE6F7F3",1]]，位置在 0..1 内递增；direction/angle/repeating
   使用端侧规范的写法。设置纯色时移除获准的冲突渐变或背景图，保留业务图标。
7. shadow 可为协议枚举（如 outerDefaultSM）或含非负 radius 的对象，可选 offsetX/offsetY、
   color、fill、type。不使用 CSS box-shadow 字符串；没有需要时不新增阴影。
   constraintSize 原对象保持合法且不新增矛盾上下界，不通过 minHeight 与固定 height 冲突腾空间。
   修改 constraintSize 时保留 minWidth/maxWidth/minHeight/maxHeight 四个必填字段，使用非负数值
   或带 vp/fp/% 的合法尺寸字符串。同单位上下界必须有序，不猜测不同单位的换算；clip 必须为布尔值。
8. 不新增网络图片、emoji、字体文件、事件函数或素材地址。禁止增加 Form 不支持的组件。
   root 与资源、数据授权由程序保护，不能靠重建协议消息绕开。
