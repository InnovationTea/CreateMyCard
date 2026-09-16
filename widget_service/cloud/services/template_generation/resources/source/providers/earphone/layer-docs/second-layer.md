# 第二层业务模板使用规则

- Provider：`com.huawei.earphone.cli`；业务领域为 `BluetoothDeviceOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
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
  - `BluetoothDeviceOverviewStatusHero@1`：耳机仓充电状态 Hero，只表达单个焦点面板内容；顶部为
    “耳机仓”标签行，右侧可选 20vp 充电盒图标，下方以 20vp 大字展示 `/chargingStatusDesc`，副标签为
    “充电状态”。主数据：/chargingStatusDesc；次要数据：无；可选数据：无。用于 `WideTwoFocus` 系列
    左右双焦点布局的一个 Hero 槽位；`deviceIcon` 为可选参数，仅在本轮存在匹配的充电盒素材时传入。
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
  - `deviceIcon`：EarbudsSupport 与 ConnectionSupport 只接受整副或成对耳机本体，
    ChargeSupport 与 StatusHero 只接受耳机收纳盒或充电盒；同名参数必须按具体模板语义匹配，不得使用
    单侧耳塞或通用音乐图标。
  - `musicIcon`：EarbudsChargingWideFull 的每日歌单入口图标，只接受音乐语义素材（音符、歌单），
    与耳机硬件语义素材互斥；输入无音乐素材时省略。
- 必填素材没有合适候选时不得选择该模板；可选素材没有合适候选时省略。
- `BluetoothDeviceOverviewTripleBatteryWideHalf@1`：横向三块耳机仓、左耳、右耳电量，适用于 WideHalf 槽位；只覆盖三项电量，不覆盖连接状态，不含动作。deviceIcon 为耳机仓，左右耳图标按语义选择，输入无对应素材时省略，不能自行增加素材候选。
- `BluetoothDeviceOverviewEarbudsChargingWideFull@1`：Q073 完整 2x4，要求名称、连接状态、左右耳和耳机仓的电量及充电状态共八字段，内置每日歌单 actionId。左侧三列各显示图标、电量、充电状态，不加进度环；deviceIcon 为充电盒，左右耳图标不可互换。两侧面板使用主题底色，外侧安全边距由骨架提供。
- `BluetoothDeviceOverviewCaseConnectionHero@1`：展示耳机仓电量环、百分比及连接状态，只需 isConnected 和 batteryLevel，deviceIcon 使用充电盒素材；通过既有 Hero 布局组合操作，保持 Q060 充电状态模板独立。
- `BluetoothDeviceOverviewCaseSettingsHero@1`：2x2 耳机仓充电状态 Hero，只需 chargingStatusDesc，不要求电量或素材；不内置操作按钮，通过既有 HeroActionLayout 与 PillAction 组合。内容尺寸跟随父槽位，底色和安全边距交由骨架处理。画廊使用示例充电状态展示，不改变输入字段、现有布局或检索分支。
- `BluetoothDeviceOverviewMusicFull@1` 用于 Q059 耳机名称、连接状态、耳机盒电量及更新时间。2x4 单业务双操作时，使用 WideFullTwoCompactLayout，依次组合本 Full、蓝牙设置 CompactAction、每日歌单 CompactAction；布局设置 compactRows=true（右侧按钮高 57vp，间距 12vp），两个动作使用 prominent=true，文案沿用批准的“蓝牙设置”和“每日推荐”。素材仅使用输入批准的候选；缺少蓝牙标志时可使用对应耳机设备图标。

- `BluetoothDeviceOverviewEarbudChargingWideFull@1`：左右两列等宽，间距 12vp，高度撑满骨架内容区，外侧安全边距由骨架统一提供 12vp。左侧音乐面板内边距 8vp、底部按钮高 36vp；右侧两个耳机面板等分可用高度，间距 12vp，电量字体 16vp，环直径 44vp。通过规划器分配的 actionId 承担收藏歌单操作，不额外组合底部按钮。
