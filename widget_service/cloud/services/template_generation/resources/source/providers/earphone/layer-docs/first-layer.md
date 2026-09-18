# 蓝牙耳机第一层意图规则

## BluetoothDeviceOverview

本节只适用于 `GetEarphoneInfo`。根据实际 `userQuery` 筛选回答主要问题所需的最少字段；
输入候选集合是可用范围，不是必须展示的清单。不要从样例数据、标题、说明或模板所需字段扩展用户意图。
允许参考下列真实模板覆盖收敛耳机字段，但最终模板选择和布局可用性仍由后续 Search/Planner 判断。

### 决策顺序（先执行，优先于下方字段解释）

先牢记仓电量场景的完整决策：明确“耳机盒电量和充电状态”时，核心是
`/batteryLevel`、`/chargingStatusDesc`，不能只输出字段就结束，必须继续完成后面的动作决策。
即使输入还提供名称、左右耳电量、左右耳充电状态，也不能转成左右耳概览。
`EarbudsFull` 不展示仓字段，`EarbudPairFull` 不展示仓充电状态，不能因为有左右耳候选就认为 Full 可用。
以本轮启用模板参考为准；无可用 Full、仓 Hero 可用且候选包含蓝牙设置、用户未要求或禁止动作时，
输出一个蓝牙设置动作。此条件下 `action=[]` 是遗漏，不是遵从“用户没要求操作”。

同一仓电量需求的输出对照（均以本轮实际候选和启用模板为前提）：
- 有仓电量、仓充电状态和蓝牙设置候选，仓 Hero 可用、无 Full、用户没有动作要求：
  `{"requiredOutputFieldsByCapability":{"GetEarphoneInfo":["/batteryLevel","/chargingStatusDesc"]},"action":["event.open.settings.bluetooth"]}`。
- 上述输入明确追加“不要按钮、不要跳转”：
  `{"requiredOutputFieldsByCapability":{"GetEarphoneInfo":["/batteryLevel","/chargingStatusDesc"]},"action":[]}`。
第二种允许后续报告无法组成布局，不能为了命中而违反否定要求；没有合法动作候选时也不能照抄第一种。

1. 提取用户强调“必须、都要、全部、不能省略”的硬要求，始终保留。
2. 有具体问题时只保留回答该问题的核心字段和硬要求，例如“哪只耳朵没电”只需左右耳电量。
3. 没有具体问题、只有三个或更多类别的普通概览枚举时：若含连接状态，以连接为核心，
   输出 `/isConnected`；否则若含左右耳电量，输出 `/leftBatteryLevel`、`/rightBatteryLevel`。
   名称、电量、充电状态等剩余普通项降为辅助并省略。左右耳电量算一个类别，左右耳充电状态算一个类别。
   本步中“显示、查看、用于查看”不表示必须保留枚举中的每一项，不应回退到通用的逐项抽取规则。
4. 其余简短明确需求按其独立目标保留。最后核对模板覆盖；不丢核心、不补输入候选外字段或动作。

### 核心与辅助字段

- “哪只耳机没电”“一只耳机听不了，看看电量”：核心为 `/leftBatteryLevel` 和 `/rightBatteryLevel`。
  名称、仓电量、充电状态、更新时间只是辅助，用户未将其作为独立目标时省略。
- “耳机连上没”“查看连接状态”：核心为 `/isConnected`；不能因为通常需要显示设备名就补 `/earphoneName`。
- “耳机盒还有多少电”：核心为 `/batteryLevel`；同时问“充着没/是否在充电”时保留 `/chargingStatusDesc`。
- 独立询问“耳机叫什么”或简短需求“显示名字和电量”：名称是核心，保留 `/earphoneName`。
  仓/整体电量对应 `/batteryLevel`；明确“左右耳”时同时保留 `/leftBatteryLevel`、`/rightBatteryLevel`。
  未限定部位的“名称和电量”使用仓/整体电量语义，不自动展开左右耳及充电状态。
- 普通并列字段不自动成为硬要求。先确定核心问题，名称、其它部位电量、充电说明、更新时间可作为辅助省略。
  “哪只耳朵没电”即使附带“耳机名称、电量、充电状态”等概览说明，也只取左右耳电量。
  只有单独询问“充着没/充电状态”或强调必须显示时，充电字段才是核心；不要把充电状态当成剩余电量。
- 对没有具体问题、包含多个状态的概览枚举：包含连接状态时优先连接概览，保留 `/isConnected`，
  可省略名称、电量和充电说明；否则包含左右耳电量时以左右耳电量为核心，可省略名称与充电说明。
  例如“创建蓝牙耳机卡片，查看耳机名称、左右耳机电量和充电状态”取左右耳电量，
  “创建耳机卡片，查看耳机名称、连接状态、左右耳机电量及充电状态”取连接状态。
- 简短且没有概览语义的独立需求仍保留：例如“连接状态和名称”“名称和电量”“名称和左右耳电量”
  “仓电量和充电状态”；不得为了匹配而把仓电量替换成左右耳电量。
- “必须、都要、全部、不能省略”等硬要求必须保留；不得为模板命中删除核心字段，
  也不得把核心字段改成其它部位。动作仅按下述耳机专用规则选择。
- 候选中出现 `/updatedAt`、充电状态等不表示用户要求展示；只在 query 明确要求或其为回答主要问题不可缺少时选择。
- 原始意图只能来自本轮实际 query；不能推测上游改写前的问法，不能根据文件名、编号或历史样例纠正当前 query。

### 2×2 模板覆盖参考

按“完整回答核心问题、满足硬要求、所选辅助字段最少”的顺序比较以下模板，不以保留字段最多为目标。
这里的必需字段指模板自身输入依赖，不能因此加入用户需求；候选中缺少模板依赖时不得假设数据存在。
普通辅助字段阻碍核心匹配时可从输出需求中删除，不能删除核心或硬要求。无可行模板时保留核心并允许后续报告未命中。

- `BluetoothDeviceOverviewEarbudsFull@1`：必需左右耳电量；可选左右耳充电状态。哪只没电对应左右耳电量，不要求名称。
- `BluetoothDeviceOverviewEarbudPairFull@1`：必需连接状态、名称、仓电量、左右耳电量。适合连接或整体概览；只问连接时需求只取连接状态，不补其余需求。
- `BluetoothDeviceOverviewHero@1`：必需连接状态、名称；可选左右耳电量。
- `BluetoothDeviceOverviewEarbudPairHero@1`：必需名称、左右耳电量；不要求连接状态或仓电量，适合名称与左右电量的单按钮卡片。
- `BluetoothDeviceOverviewEarphoneCaseHero@1`：必需仓电量、仓充电状态。
- `BluetoothDeviceOverviewEarphoneHero@1`：必需名称、仓电量。
- `BluetoothDeviceOverviewEarbudPairCompact@1`：必需名称、左右耳电量。
- `BluetoothDeviceOverviewEarphoneCaseCompact@1`：必需仓电量、仓充电状态。
- `BluetoothDeviceOverviewEarphoneCompact@1`：必需名称、仓电量。

单业务无动作需要 Full；Hero/Compact 有字段覆盖并不保证布局可用。禁止删除核心字段迁就布局。
“哪只耳朵没电”的输出示例：
`{"requiredOutputFieldsByCapability":{"GetEarphoneInfo":["/leftBatteryLevel","/rightBatteryLevel"]},"action":[]}`。
此时两耳同等重要，不设置唯一主焦点。不输出模板 ID，也不修改输入候选数据本身。

### 字段与动作边界

字段必须逐字来自本次 `candidateOutputFieldsByCapability.GetEarphoneInfo`，同时能从当前 schema 推导。
支持的字段语义如下（列举不是授权全部选择）：

- `{{dataRoot:GetEarphoneInfo}}/isConnected`：连接状态。
- `{{dataRoot:GetEarphoneInfo}}/earphoneName`：设备名称。
- `{{dataRoot:GetEarphoneInfo}}/batteryLevel`：仓或整体电量。
- `{{dataRoot:GetEarphoneInfo}}/chargingStatusDesc`：仓或整体充电状态。
- `{{dataRoot:GetEarphoneInfo}}/leftBatteryLevel`、`{{dataRoot:GetEarphoneInfo}}/rightBatteryLevel`：左右耳电量。
- `{{dataRoot:GetEarphoneInfo}}/leftChargingStatusDesc`、`{{dataRoot:GetEarphoneInfo}}/rightChargingStatusDesc`：左右耳充电状态。
- `{{dataRoot:GetEarphoneInfo}}/updatedAt`：更新时间。

不支持手表、车机、键鼠、音箱、播放状态、曲目或播放进度；缺少所需合法字段时不得伪造。
用户明确请求动作时选择对应已批准动作；无动作时仅允许下面的耳机专用例外。
只输出第一层约定的 JSON，不输出模板、布局或判断理由。

### 耳机专用动作回退（字段筛选完成后执行）

仅适用于 size 为 2x2、candidateDataBindings 只有 GetEarphoneInfo 的单业务请求。
其它业务及混合业务不自动增加动作。优先级按顺序执行：

1. 用户明确不要按钮、不要跳转、不需要入口、只展示不要操作时，action 保持空数组。
   即使没有 Full 也不使用带动作 Hero；不能把这些否定词误识别成请求动作。
2. 先保留用户明确请求的合法动作，不删除或替换；候选存在不表示动作已经选中。
   已有一个动作先考虑可用 Hero，已有两个动作直接考虑双按钮 Compact，不再自动追加。
3. 用户未请求动作时，先检查上述 Full：既能覆盖全部核心字段，又有本次候选提供的全部模板必需字段，
   才算可用。Full 可用就输出 action=[]，即使 Hero 也匹配仍优先 Full。
4. Full 不可用时检查 Hero。同样必须覆盖全部核心字段且其全部必需字段均在本次输入候选中。
   若存在可用 Hero，且 actionCandidates 含 event.open.settings.bluetooth，则输出
   action=["event.open.settings.bluetooth"]，用于生成可点击的“蓝牙设置”按钮。
   本条是用户已授权的耳机场景自动入口规则，优先于通用“未明确请求就不能选择动作”。
5. Full/Hero 无法形成满足核心字段、输入依赖和已选动作的可用方案时，继续判断 Compact。
   Compact 必须覆盖全部核心字段且本次输入提供全部必需字段，不能为适配它删除核心字段。
6. Compact 可用时，保留已选动作，按双按钮要求计算缺少的数量：
   - 已有两个不同的合法动作：不追加。
   - 缺一个：优先追加候选中尚未选中的 `event.open.settings.bluetooth`；如果它已经选中或不在候选中，
     从剩余候选里选择与用户 query 和耳机场景最相关的一个动作。
   - 缺两个：从候选中选择两个不同动作；优先尚未选中的蓝牙设置，其余按用户 query 和耳机场景相关性选择。
   不固定第二个动作名称或 ID；相关性相同时按候选顺序选择，用户明确排除的动作不选择。
   “已有”指 action 已选集合，不是 actionCandidates 候选集合。每个追加动作必须真实存在于 actionCandidates。
7. 缺少任一所需候选时保持补齐前的 action，不伪造或只补一半；不补字段、不重复动作、不超过两个动作。
   用户禁止按钮或跳转时以上所有自动补动作都禁止，包括 Compact；允许后续报告未命中。

为避免误把“覆盖用户字段”当作“Full可用”，按如下字段集合逐项核对：
- EarbudsFull：输入必须含 `/leftBatteryLevel`、`/rightBatteryLevel`，且筛选后的需求只能来自
  `/leftBatteryLevel`、`/rightBatteryLevel`、`/leftChargingStatusDesc`、`/rightChargingStatusDesc`。
  需求含名称、仓电量或连接状态时，此 Full 不可用。
- EarbudPairFull：输入必须同时含 `/isConnected`、`/earphoneName`、`/batteryLevel`、
  `/leftBatteryLevel`、`/rightBatteryLevel`；缺任何一项即不可用，即使该项不属于用户要显示的字段。
  需求含任何充电状态时，此 Full 也不能覆盖。
- 两个 Full 均不可用且提供蓝牙设置候选时，以下满足条件的 Hero 回退是必须执行的规则，不是可选建议：
  名称＋仓电量，输入含 `/earphoneName`、`/batteryLevel` → EarphoneHero，输出蓝牙设置动作；
  仓电量＋仓充电状态，输入含 `/batteryLevel`、`/chargingStatusDesc` → EarphoneCaseHero，输出蓝牙设置动作；
  连接状态＋名称，输入含 `/isConnected`、`/earphoneName` → Hero，输出蓝牙设置动作。
  名称＋左右耳电量，输入含 `/earphoneName`、`/leftBatteryLevel`、`/rightBatteryLevel`
  → EarbudPairHero，输出蓝牙设置动作；此时不因旧 Hero 缺连接状态而回退 Compact。
  用户禁止按钮或跳转时以上规则不执行。模板仅供分析，JSON 仍只输出字段和 action。

例如：输入仅有名称和仓电量且提供蓝牙设置候选，无禁用按钮要求时，EarphoneHero 可用，补一个蓝牙设置动作；
输入有名称、连接状态、仓电量、左右耳电量且 Full 能覆盖需求时，不补动作；
输入仅有名称和左右耳电量时，EarbudPairHero 已可覆盖，优先使用单按钮 Hero；
已有两个明确动作则使用 EarbudPairCompact，不删除用户动作。其它仅 Compact 可用的情况仍按候选补齐规则处理。
若此场景已经明确选择蓝牙设置，只从其余候选补一个相关动作；已有其它动作时优先补候选中的蓝牙设置。
所选动作的含义与参数以本次候选为准，不通过按钮文案改变动作语义。
动作参数由现有候选绑定，不在第一层生成；按钮只在用户点击后打开设置，不自动执行或连接耳机。

- `2x4` 多业务场景中，用户要求展示耳机仓充电状态且 `chargingStatusDesc` 可用时，可以选择
  `BluetoothDeviceOverviewStatusHero@1`；该模板占据 `WideTwoFocus` 系列左右双焦点布局的一个
  Hero 槽位，充电状态为硬必选。
