# Phase Q001–Q010 真实批跑结果

十条**模型实际输出**：脚本扮演被微服务链接的生成模型，逐条读 `taskspec/Phase/Q001.json` ～ `Q010.json` 的入参，产出这一批的紧凑 genui DSL 与说明。期望数据不在这批产物里，由你在「导入期望输出」页自己输入。

## 这批 DSL 是按正式生成契约写的

root 只能是 `Layout`，`layout` 取 `layouts/2x2.md` 登记的十个 `S-` 布局之一，children 按有序角色填真实组件 ID；只用 `SingleLineTitle`／`EmphasizedData`／`EmphasisText`／`SecondaryBody`／`EventCard`／`InfoBlock`／`ProgressCircleSingle`／`DataDisplay`／`Group`／`PillButton` 这些语义组件，图标写在 `icon`／`visual.icon` 属性上，不写宽高、间距、圆角与对齐。`Text`／`Image`／`Button` 是转换器内部展开的基础组件，模型直接写会被拒绝。

每条产物都先过 `convert_compact_dsl_to_a2ui(size, protocol_profile)` —— 与「卡片渲染」页同一个严格入口，过不了直接报错退出，所以这批 DSL 都能贴进渲染页预览。

## 目录

```text
phase_Q001_Q010_model_run/
  requests/Qxxx.json           # 入参原文（发给模型的 request）
  output/Qxxx.genui.jsonl      # 模型产出的 DSL，可直接在卡片渲染页预览
  output/Qxxx.md               # 单条产出说明（含实算指纹、自检与图标取舍）
  session/records.json         # 十条本次会话调试记录（对比页右侧的数据源）
  session/inject.js            # 自包含注入脚本，控制台整段粘贴即可
```

同时在 `debug_tools/batch_output/phase_q001_q010_model/` 落了一份批跑运行目录，「批量测试」页能看到这条运行，后端 `GET /debug/expect/compare` 也可以直接拿它当实际侧。

## 用例一览

| ID | 标题 | 分类 | 布局 | 期望数据 | 用到的图标 | 自检 |
| --- | --- | --- | --- | --- | --- | --- |
| Q001 | 西湖天气 | 天气 | S-title-primary-secondary-action | 2 | 2 | matched |
| Q002 | 明日天气 | 天气 | S-title-content | 1 | 1 | matched |
| Q003 | 发布会提醒 | 日程 | S-title-primary-secondary-action | 3 | 2 | matched |
| Q004 | 天气预警 | 天气 | S-center | 1 | 0 | matched |
| Q005 | 广州出行 | 天气 | S-title-dual-content | 1 | 2 | matched |
| Q006 | 明日双会 | 日程 | S-title-content | 1 | 1 | matched |
| Q007 | 客户交流 | 日程 | S-title-dual-content | 1 | 1 | matched |
| Q008 | 北京出差 | 出行 | S-title-content | 2 | 1 | matched |
| Q009 | 左右耳机 | 设备 | S-dual-info | 1 | 2 | matched |
| Q010 | 周末露营 | 天气 | S-title-dual-content（variant=stacked-info） | 1 | 1 | matched |

十条都是 2x2；分类为天气 5 条、日程 3 条、出行 1 条、设备 1 条。「自检」是**候选载荷当期望、这份 DSL 当实际**，用后端同一套 `match_pair` 按数据＋动作＋尺寸三个维度算出的判定。

## 图标维度为什么不会条条命中

2x2 的图标预算是默认最多两个实例（标题／按钮／环心，`NumericRatioStack` 的三个 12vp 小图标算例外），而入参常给三四个候选素材，所以本批每条只挑语义上最贴的用，其余候选素材留在清单里没用上——这是真实模型的正常取舍，不是漏写。期望侧若把全部候选素材写成需求项，图标维度就会把这些条目筛掉；各条 `output/Qxxx.md` 里逐行列了「用到的图标」和「候选里没用上的素材」。

## 让这十条出现在对比页右侧

对比页的实际侧只认浏览器会话里的调试记录（`sessionStorage` 键 `ai-widget-debug-call-history:v1`），三种方式任选：

1. 打开 <http://127.0.0.1:8888/debug/>，F12 控制台整段粘贴 `session/inject.js`，页面自动刷新后「接口调用历史」和对比页右侧都会出现这十条；同批记录会被覆盖，其它来源的记录保留。
2. 起一个带 CORS 的静态服务常驻数据集目录，页面里一行 fetch 回填：`python debug_tools/make_phase_batch_run.py --serve`，然后控制台执行：

```js
const records = await (await fetch('http://127.0.0.1:8899/session/records.json')).json();
const key = 'ai-widget-debug-call-history:v1';
const stored = JSON.parse(sessionStorage.getItem(key) || '{"calls":[]}');
stored.calls = records; stored.selectedCallId = records.at(-1).id;
sessionStorage.setItem(key, JSON.stringify(stored)); location.reload();
```

3. 真跑模型：把 `debug_tools` 的连接配置指向已启动的工具微服务（默认 `ws://127.0.0.1:8855/api/v1/ws/tools`），在「接口调试」里逐条提交 `requests/Qxxx.json`，成功调用会自动进同一份会话记录。

## 期望侧由你输入

「导入期望输出」页每条期望要求 DSL ＋ 截图（截图必须是真的图片），也可以只在「期望数据／期望动作」框里逐行粘贴需求项。各条 `output/Qxxx.md` 末尾已经把完整候选字段路径、事件参数与图标取名列好，直接复制即可；把 `requests/Qxxx.json` 的 content 块当 CardSpec 粘贴，平台会自动识别三类指纹。

启用维度的需求项必须全部命中才算「已匹配」，尺寸仍是硬门槛。本批每条都绑定了入参里的全部候选字段，事件也逐个落进唯一 `onClick`，所以只勾数据＋动作两个维度时十条都应命中；想看不匹配的形态，就按说明文件里的做法加一个没用上的素材名或改 intentName。

## 重新生成

```powershell
uv run python debug_tools/make_phase_batch_run.py
# 可选：--source <Phase 目录> --output <数据集目录>
#       --run-root <批跑根目录> --run-id <运行标识> --serve --port <端口>
```

脚本每条先做严格转换门禁，再用 `fingerprint`／`match_pair` 自检数据、动作与尺寸，并核对图标没有越出候选清单；任何一条不合格就报错退出，避免说明文件与页面口径分叉。
