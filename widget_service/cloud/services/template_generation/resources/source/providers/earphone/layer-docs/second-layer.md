# 第二层业务模板使用规则

- Provider：`com.huawei.earphone.cli`；业务领域为 `BluetoothDeviceOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BluetoothDeviceOverviewHero@1`：展示连接状态、设备名，左右耳电量可选；可选左右耳图标；用于
    `HeroActionLayout@1` 加一个 `PillAction@1`。
  - `BluetoothDeviceOverviewEarbudsSupport@1`：展示左右耳电量；`deviceIcon` 必填；Planner 可将其用于
    `TwoSupportLayout@1`，并传入 `actionId` 将事件绑定在 Support 根节点内部。
  - `BluetoothDeviceOverviewChargeSupport@1`：展示盒或整体电量及充电状态，32vp 环配两行文本；
    主数据 /batteryLevel、次要数据 /chargingStatusDesc 均必需；`deviceIcon` 必填且必须表达充电盒。
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
    图标均可选；用于无 Action 的 Full，或搭配一个 `IconAction@1`。
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
  - `deviceIcon`：EarbudsSupport 只接受整副或成对耳机本体，ChargeSupport 只接受耳机收纳盒或充电盒；
    两个同名参数的语义不能混用，也不得使用单侧耳塞或通用音乐图标。
- 必填素材没有合适候选时不得选择该模板；可选素材没有合适候选时省略。
