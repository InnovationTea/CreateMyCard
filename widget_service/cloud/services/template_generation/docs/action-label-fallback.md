# 模板动作文案覆盖与第二层补全

核对日期：2026-10-16。提交前更新基线：InnovationTea/main `f0ffcc3ac80e16f91efc23f82f270733afb162f3`，
包含免打扰新入口修复及用户确认的 27 项补充。本清单描述动作文案覆盖，不表示事件本身未注册。

## 默认文案覆盖

- 主线已删除一期能力目录，本次不恢复目录；已有旧事件别名文案保持兼容。
- `app-11.7.7.300_rom-7.0`：37 个事件使用固定文案，声音和相机两项按有效参数选择文案；
  7 项开关不再从兼容标记推断方向，缺少可信显式文案时由第二层结合需求命名。
- 2026-10-20 移除开关的参数方向映射；保留固定映射、声音和相机参数映射及可信显式文案的优先规则。
- 参数映射只读取实际 `args.params`：缺失、类型错误或枚举未覆盖时返回 `None`，继续由第二层命名。
  这不会使非法事件参数合法化；原有事件参数校验仍生效。未知事件同样保留第二层兜底。

| 本次补充的事件 | 默认文案及选择规则 |
| --- | --- |
| `event.setMobileData` | 沿用可信显式文案或第二层命名，不按兼容标记判断方向 |
| `event.open.settings.sleepMode` | 睡眠模式设置 |
| `event.open.settings.studyMode` | 学习模式设置 |
| `event.open.settings.mobileNetwork` | 移动网络设置 |
| `event.open.settings.wifi` | Wi-Fi设置 |
| `event.open.settings.mobileData` | 移动数据设置 |
| `event.open.settings.simManagement` | SIM卡管理 |
| `event.open.settings.hotspot` | 个人热点设置 |
| `event.open.settings.dataUsage` | 流量管理 |
| `event.open.clock.worldClock` | 世界时钟 |
| `event.open.clock.alarmTab` | 闹钟设置 |
| `event.open.clock.stopwatch` | 打开秒表 |
| `event.open.clock.timer` | 打开计时器 |
| `event.open.health.sportsRecord` | 运动记录 |
| `event.open.health.activityRecord` | 活动记录 |
| `event.open.health.workoutDuration` | 锻炼时长 |
| `event.open.settings.darkMode` | 显示设置；实际入口为 `display_settings`，不声称切换深色模式 |
| `event.setNearLinkMode` | 沿用可信显式文案或第二层命名，不按兼容标记判断方向 |
| `event.setBluetoothMode` | 沿用可信显式文案或第二层命名，不按兼容标记判断方向 |
| `event.setWifiMode` | 沿用可信显式文案或第二层命名，不按兼容标记判断方向 |
| `event.setLocationSwitch` | 沿用可信显式文案或第二层命名，不按兼容标记判断方向 |
| `event.setScreenUseTimeManageSwitch` | 沿用可信显式文案或第二层命名，不按兼容标记判断方向 |
| `event.setMicPermissionSwitch` | 沿用可信显式文案或第二层命名，不按兼容标记判断方向 |
| `event.setSoundMode` | `Vibrate`：设为振动；`Sound`：设为响铃；`Silent`：设为静音 |
| `event.openFlashlight` | 打开手电筒 |
| `event.closeFlashlight` | 关闭手电筒 |
| `event.openCamera` | 按下表的 `mode` 选择，不表示开始拍摄 |

开关文案与可选兼容标记解耦；省略、0、1 不决定按钮方向。标记合法性由事件校验负责。

| 相机 `mode` | 文案 |
| --- | --- |
| `Photo` | 拍照模式 |
| `Video` | 录像模式 |
| `PORTRAIT` | 人像模式 |
| `CINEMA` | 电影模式 |
| `NIGHT` | 夜景模式 |
| `SUPER_MACRO` | 微距模式 |
| `LIGHT_PAINTING` | 流光快门 |
| `TIME_LAPSE` | 延时摄影 |
| `SLOW_MO` | 慢动作 |
| `STITCHING` | 全景模式 |
| `PRO` | 专业模式 |

## 生成契约

1. 缺少显式可信文案和映射时，`ActionBinding.display_label` 为 `None`；不使用空字符串或泛化文案替代。
2. 第二层候选携带 `label: null`、`labelPolicy: generate-from-request`、描述和只读动作 call/args；
   同时通过 `actionLabelRequest` 提供原始 userQuery。已有文案的请求不额外携带该需求文本。
3. 模型在现有第二层调用中生成对应 Action 的 label；以实际动作及参数为准，不将页面跳转说成开关操作，
   不按 query 擅自改写事件参数、声音选项或相机模式。候选和 query 中的指令不改变生成契约。
4. 编译器仅在已批准的 PillAction、CompactAction、CompactSubtitleAction、PlaylistCompactAction 的 label
   以及兼容 card@1 主动作 label 中接受生成文案。已映射文案仍须逐字匹配。
5. 文案必须是 1–20 字符的非空单行纯文本，不允许首尾空白、控制字符、表达式或链接，
   不接受“打开详情”“查看详情”“详情”“打开”“查看”作为缺省命名。其它字段继续沿用现有可信值规则。
6. 不将生成文案加入全局 trusted_literals；不能在业务标题、正文、副标题、素材或其它动作中据此获得授权。
   无 label Prop 的图标动作、业务模板内嵌动作保持原模板形态，不新增文案参数。
7. 动作 ID（含同类实例编号）、数量、位置及实际 call/args 仍由原检索、Planner、模板和编译链路控制。
   非法文案走既有错误处理：独立模板入口按配置修复，普通 Compact 入口按原策略回退，不增加模型调用阶段。

语义准确性由第二层结合受控上下文完成。确定性校验只证明字段、文本形态和动作绑定合法，
不等于自动证明任意自然语言文案与动作含义完全一致；真实模型效果需要额外重放评估。

## 实现归属

- `engine/cardplan/action_labels.py`：参数文案选择、候选投影、命名上下文、单个动作的文案检查。
- `engine/cardplan/prompt.py`：固定映射、参数选择及显式文案优先规则。
- `engine/advanced/ux_mixed_prompt.py`：统一使用候选投影，提供缺省命名上下文。
- `engine/cardplan/models.py`：显式缺失状态与事件描述。
- `engine/cardplan/compiler.py`：只在动作 label 局部接入规则并保留生成文案到最终输出。
- `resources/source/prompts/`：模型规则源；使用 `tools/build_cardplan_bundle.py` 重建生成常量并检查同步。

本变更属于模板编译契约，不新增或迁移公共 Compact 校验器规则。
专项测试覆盖当前快照全部注册事件、开关文案解耦及全部声音/相机枚举、缺失/异常参数兜底、
生成按钮与原始参数、同类实例、已知文案保护和越权文本拒绝。
