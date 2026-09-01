# 第二层业务模板使用规则

- Provider：`com.huawei.earphone.cli`；业务领域为 `BluetoothDeviceOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BluetoothDeviceOverviewHero@1`：展示连接状态、设备名和左右耳电量；可选左右耳图标；用于
    `HeroActionLayout@1` 加一个 `PillAction@1`。
  - `BluetoothDeviceOverviewCompleteWideHero@1`：用于 2x4 完整耳机状态；左上展示设备名和连接状态，
    居中按左耳、右耳、耳机盒顺序展示三个电量环及充电状态；用于 `WideSingleFocusLayout@1` 加一个
    `PillAction@1`。
  - `BluetoothDeviceOverviewCaseStatusCompact@1`：展示盒电量和充电状态，可选左右耳充电状态；
    `deviceIcon` 必填，`headerLabel` 可选；用于 `CompactTwoActionLayout@1` 加两个 `PillAction@1`。
  - `BluetoothDeviceOverviewEarbudsSupport@1`：展示左右耳电量；`deviceIcon` 必填；仅供兼容 LLM 路径
    与原子预览使用，当前 Search 不可达；兼容双业务场景中可传 `actionId`，事件绑定在 Support 根节点内部。
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
- `headerLabel` 只能逐字复用 `cardComposition.businessTitleCandidate`；没有可信标题时省略。
- Props 只能使用本轮 Prompt 下发的可信文本或素材，不得输出数据路径。
- 选择能够完整表达用户显式字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- 素材参数不绑定固定素材 ID，只从本轮素材候选中按语义匹配：
  - `sourceIcon`：整副耳机、耳机产品或蓝牙音频设备；
  - `caseIcon`：耳机收纳盒或充电盒；
  - `leftEarIcon`、`rightEarIcon`：对应左右耳塞，左右不可互换；
  - `deviceIcon`：整副耳机、成对耳机或耳机盒，不得使用单侧耳塞或通用音乐图标。
- 必填素材没有合适候选时不得选择该模板；可选素材没有合适候选时省略。
