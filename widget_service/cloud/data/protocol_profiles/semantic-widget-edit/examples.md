# 编辑决策示例

仅理解方法。所有 ID、值和色号都需以实际原卡和用户要求为准，不把示例样式套到原卡。
意图阶段只输出 EditIntent，执行阶段只输出对应模式结果，两者不混合。

## 标题字号改为 20，其它不变

原 title 为静态 Text，fontSize=14；父 titleRow 固定 height=14。
意图关键字段：mode=patch，dimensions=[typography,layout]，targets=[title]，
linkedTargets=[titleRow]，expectations=[{componentId:title,property:styles.fontSize,
operator:equal,value:20}]。不要把包含 title 的 root 整体列入 protectedTargets。
执行需要两项补丁：title.fontSize 从 14 到 20；titleRow 在获准范围内调整固定高度，
并复核更上层限制。其它文字、数据和颜色保持。只改字号而不考虑承载不算完成。
一个真实的单属性补丁形状是：
{"sourceDigest":"输入摘要","changes":[{"componentId":"title","property":"styles.fontSize",
"before":{"exists":true,"value":14},"operation":"set","value":20}]}。
有父容器联动时在同一个 changes 中追加真实原值补丁，不照抄本例一个补丁就提交。

## 标题再大一点，正文颜色保持

targets=[title]；需要的父容器逐个加入 linkedTargets。
expectations=[{componentId:title,property:styles.fontSize,operator:increase},
{componentId:body,property:styles.fontColor,operator:preserve}]。
从原字号适度增加，不硬编码成 20；正文所在子树无需修改，不放进 targets 扩大范围。

## 背景从渐变改为白色

原 root.styles 有 linearGradient。targets=[root]，dimensions=[palette]，mode=patch。
expectations 对 backgroundColor 登记 equal #FFFFFFFF，对 linearGradient 登记 remove。
执行移除原 linearGradient（before 精确复制完整渐变），再设置背景色；不要仅叠加纯色保留冲突。
若是独立满屏背景 Image，改用 layout，登记该 Image 与必要父节点，不删除天气图标或动作图标。

## 2x4 改为 2x2，保留全部指标和按钮

mode=layout，targetSize=2x2，dimensions 包含 layout、必要 spacing，targets=[root]。
结合原内容重组承载、间距与排列，保留每个原业务组件和完整点击对象。
输出完整三条原协议消息；不能只改 root 宽高或颜色，也不能按示例猜一个 160px 的画布。

## 改得柔和一点 / 文字变长 / 动态列表

柔和风格可沿用原层次，协调背景、文字和面板，按实际变化选择 palette/shape/spacing；
不为了显得“改过”而改写标题、压低透明度隐藏文字，或创建未授权装饰节点。
静态标题改为较长文案时登记准确 textChanges，适度调整必要承载与换行，不直接截断新文案。
列表只调整原模板节点样式，children 模板对象及循环变量保持，不把当前数据展开成几个静态 Text。

## 修改对象中的静态字段

若原 title.styles.shadow 为 {radius:4,color:原动态表达式}，用户只调整阴影半径，
在获准 shape 范围内提交整个 shadow 对象，radius 使用新合法值，color 保持原表达式和位置。
不将 color 换成首帧色值，也不为消除检查错误删除动态字段。需要新增包装容器时，
将原节点移动到新容器并由原父引用新容器，每个节点仍只挂载一次，不保留重复引用或孤立新容器。

## 已满足、澄清或不支持

标题已为 20、用户要求设为 20且没有其它变化：可 unchanged，并保留该 equal 目标供程序复核。
“恢复更早那个字号”且输入未提供历史值：needs_clarification，询问想恢复的字号。
“蓝色但保持原来红色不变”若明确指同一属性：needs_clarification，不静默选择其一。
“删除天气数据，换成运动步数”：unsupported，引导重新创建，不伪造能力或偷偷走模板。
