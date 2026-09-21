# 第二层业务模板使用规则

- Provider：`com.huawei.earphone.cli`；业务领域为 `BluetoothDeviceOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BluetoothDeviceOverviewEarbudTripleFull@1`：固定小标题“蓝牙耳机”、大字耳机名称，左右耳与盒电量；
    不要求连接状态；用于无动作 SingleFocusLayout，盒与左右耳图标可选。
  - `BluetoothDeviceOverviewEarbudTripleHero@1`：耳机名称、三处电量和充电状态；从左到右为左耳、右耳、盒，
    每列从上到下依次为图标、电量、对应充电状态，间距分别4vp、2vp；图标可选，缺失显示左/右/盒；
    用于 HeroActionLayout 搭配一个 PillAction，不使用角落 IconAction。
  - `BluetoothDeviceOverviewEarbudPairHero@1`：主行展示耳机名称，下方 12px 左右图标与 10fp 电量百分比并排；
    名称和左右电量必需，不要求连接状态或仓电量。图标可选，缺失显示左/右文字；用于 HeroActionLayout 加一个按钮。
  - `BluetoothDeviceOverviewHero@1`：展示连接状态、设备名，左右耳电量可选；可选左右耳图标；用于
    `HeroActionLayout@1` 加一个 `PillAction@1`。
  - `BluetoothDeviceOverviewEarbudsSupport@1`：展示左右耳电量；`deviceIcon` 必填；Planner 可将其用于
    `TwoSupportLayout@1`，并传入 `actionId` 将事件绑定在 Support 根节点内部。
  - `BluetoothDeviceOverviewConnectionSupport@1`：主行加粗展示连接状态，可选次行展示仓电量，
    右侧 40vp 电量环，环内图标为 16vp，无电量时为 24vp 耳机图标；
    用于 `TwoSupportLayout@1`。`deviceIcon` 必填，且必须表达耳机本体。
  - `BluetoothDeviceOverviewChargeSupport@1`：左侧两行文本展示盒或整体电量及充电状态，
    右侧 40vp 电量环，环内图标为 16vp；
    次要数据 /chargingStatusDesc 必需；/batteryLevel 为可选数据，存在时展示“电量 N%”文本与电量环，
    缺失时两者同时省略、只保留充电状态行；`deviceIcon` 必填且必须表达充电盒。
    用于 `TwoSupportLayout@1`，支持可选根节点事件 `actionId`，不展示左右耳电量。
  - `BluetoothDeviceOverviewEarbudsFull@1`：展示左右耳电量，可选展示左右耳充电状态，左右耳图标可选；
    用于无 Action 的 Full。
  - `BluetoothDeviceOverviewEarphoneCaseHero@1`：展示耳机仓电量进度环和充电状态文本；`caseIcon`
    可选；用于 `HeroActionLayout@1` 加一个 `PillAction@1`。
  - `BluetoothDeviceOverviewEarphoneCaseCompact@1`：展示耳机仓电量和充电状态文本；`caseIcon`
    可选；用于 `CompactTwoActionLayout@1` 加两个 `PillAction@1`。
  - `BluetoothDeviceOverviewEarphoneHero@1`：展示耳机电量进度环和耳机名称文本；`earphoneIcon`
    可选；用于 `HeroActionLayout@1` 加一个 `PillAction@1`。
  - `BluetoothDeviceOverviewEarphoneCompact@1`：展示耳机电量和耳机名称文本；`earphoneIcon`
    可选；用于 `CompactTwoActionLayout@1` 加两个 `PillAction@1`。
  - `BluetoothDeviceOverviewEarbudPairFull@1`：展示连接状态、设备名、盒电量和左右耳电量；盒与左右耳
    图标均可选；左右耳与盒充电状态为可选字段，三个字段齐全时才在电量下同时增加状态层，缺任意字段则整层隐藏；用于无 Action 的 Full，或搭配一个 `IconAction@1`。
  - `BluetoothDeviceOverviewEarbudPairCompact@1`：展示设备名和左右耳电量，左右耳图标可选；用于
    `CompactTwoActionLayout@1` 加两个 `PillAction@1`。
  - `BluetoothDeviceOverviewEarbudsPhoneWideFull@1`、
    `BluetoothDeviceOverviewEarbudsDynamicWideFull@1`：宽版连接摘要，盒与左右耳电量均为可选数据。
  - `BluetoothDeviceOverviewCompleteWideFull@1`、
    `BluetoothDeviceOverviewCompletePhoneWideFull@1`：宽版完整电量摘要，盒与左右耳电量均为必选数据。
- 兼容路径中的 Support `actionId` 只在该业务有已批准事件时传入；没有对应事件时省略，根节点不生成
  `onClick`。
- Props 只能使用本轮 Prompt 下发的可信文本或素材，不得输出数据路径。
- 选择能够完整表达用户显式字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板；
  `optionalData` 缺失时必须按模板条件渲染规则省略对应内容。
- 素材参数不绑定固定素材 ID，只从本轮素材候选中按语义匹配：
  - `sourceIcon`：整副耳机、耳机产品或蓝牙音频设备；
  - `caseIcon`：耳机收纳盒或充电盒；
  - `earphoneIcon`：整副耳机、耳机产品或蓝牙音频设备；
  - `leftEarIcon`、`rightEarIcon`：对应左右耳塞，左右不可互换；
  - `deviceIcon`：EarbudsSupport 与 ConnectionSupport 只接受整副或成对耳机本体，
    ChargeSupport 只接受耳机收纳盒或充电盒；同名参数必须按具体模板语义匹配，不得使用单侧耳塞或
    通用音乐图标。
- 必填素材没有合适候选时不得选择该模板；可选素材没有合适候选时省略。

EarbudPairCompact 现可选展示连接状态和仓电量。双动作需求包含连接状态时，无需回退；
输入仍只需名称和左右耳电量，连接状态或仓电量缺失不影响原模板使用。
明确要求电量和连接状态时应同时保留这两类需求，不能只保留连接状态。
连接状态紧跟名称，盒电量紧跟左右耳电量；不添加第三个按钮。

耳机融球主题的操作按钮使用主题背景白色 #33FFFFFF、20%不透明度，单按钮和双按钮一致；非融球主题保留原有配色和模板透明度覆盖，不应用融球按钮规则。
