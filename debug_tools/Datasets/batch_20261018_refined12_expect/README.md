# 精致版期望输出（batch_20261018_160124_3f440556 的 12 条重做）

12 条**期望输出**：从那条批跑的 88 条里挑 8 条 2x2 ＋ 4 条 2x4，沿用原 Q 编号、原 Query、原声明尺寸与入参候选，把版式重做得更精致，供你在「导入期望输出」页手工录入。

## 精致点集中在四处

- 信息补齐：入参里的候选数据字段逐个绑到可见位置，原版漏掉的区名、城市码、地点都补回来了；候选事件逐字复用，不新增第二个入口。
- 版式升级：`S-title-content` → `S-title-primary-secondary-action`、裸读数 → `ProgressCircleSingle`／`ProgressLine2` 真实比例，2x4 按 Region 角色重排并验算占高。
- 视觉落色：root 带主题 `linearGradient`，背板按登记色（小卡 `#CCFFFFFF`、宽卡 `#99FFFFFF`），图标只落在标题／按钮／环心／分区主视觉这些登记位。
- 语义自洽：动态天气现象不配固定晴天图标、未充电不配闪电，候选素材用不上时在单条说明里写明原因。

## 目录

```text
batch_20261018_refined12_expect/
  dsl/Qxxx.jsonl        # 精致版 DSL，可直接粘进「卡片渲染」页
  cards/Qxxx.md         # 单条说明：两份口径的清单＋精致点
  renders/Qxxx.png      # 真实渲染截图（导入页上传这张）
  screenshots/Qxxx.png  # 按主题色画的比例示意图，渲染截图缺失时兜底
  import/paste-all.md   # 12 条数据/动作/图标一次性粘贴
  import/render-manifest.json  # 渲染截图脚本的输入清单
  import/payload.json   # 备用：可整批 POST /debug/expect/import 的载荷
```

## 用例一览

| ID | 标题 | 分类 | 尺寸 | 布局 | 数据 | 动作 | 图标实例 | 纵向实算/预算 | 候选字段是否绑满 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q001 | 西湖天气 | 天气 | 2x2 | S-title-primary-secondary-action | 4 | 1 | 1 | 112／126vp | 是 |
| Q004 | 天气预警 | 天气 | 2x2 | S-title-content | 1 | 0 | 1 | 50／126vp | 是 |
| Q006 | 明日双会 | 日程 | 2x2 | S-title-content | 4 | 0 | 1 | 102／126vp | 是 |
| Q009 | 左右耳机 | 设备 | 2x2 | S-dual-info | 4 | 0 | 2 | 134／134vp | 是 |
| Q010 | 周末露营 | 出行 | 2x2 | S-title-dual-content（variant=stacked-info） | 4 | 0 | 0 | 126／126vp | 是 |
| Q014 | 设备充电 | 设备 | 2x2 | S-title-primary-secondary-action | 3 | 1 | 1 | 122／126vp | 是 |
| Q034 | 双城天气 | 天气 | 2x2 | S-dual-info | 4 | 0 | 2 | 134／134vp | 是 |
| Q037 | 今日运动 | 健康 | 2x2 | S-title-dual-content | 3 | 0 | 1 | 112／126vp | 是 |
| Q054 | 电池检测 | 设备 | 2x4 | W-top-bottom（variant=bottom-details） | 4 | 0 | 2 | 114／126vp | 是 |
| Q056 | 客户现场 | 日程 | 2x4 | W-split-panels | 5 | 1 | 2 | 110／110vp | 是 |
| Q069 | 睡眠分析 | 健康 | 2x4 | W-content-side-slots | 5 | 0 | 1 | 120／126vp | 是 |
| Q076 | 日出准备 | 出行 | 2x4 | W-content-side-slots | 7 | 1 | 0 | 110／126vp | 是 |

尺寸分布：2x2 八条、2x4 四条；分类覆盖天气、日程、设备、健康、出行。「候选字段是否绑满」是拿入参候选数据字段与这份 DSL 的实算数据指纹比出来的；「纵向实算/预算」是把 DSL 展开成 A2UI 后，按写死高度、`itemMargin` 与 `padding` 累加出来的占高；2x4 左右分栏取纵向最紧的一支，明细写在单条说明里。

## 手工导入怎么用

1. 打开 <http://127.0.0.1:8888/debug/> 的「导入期望输出」，批次名自定，分类按上表逐条选。
2. 每条样本粘贴 `dsl/Qxxx.jsonl` 的内容，尺寸填上表的 2x2／2x4，再上传 `renders/Qxxx.png`（真实渲染截图）。
3. 数据／动作／图标三个框按 `cards/Qxxx.md` 或 `import/paste-all.md` 逐行粘贴。每条说明里给了两份口径：
   - **本卡实际用到的**：三个维度都会判已匹配；
   - **入参候选全部**：本卡没用上的候选素材会让图标维度把该条筛掉，各条说明都写明了未用素材与原因。
4. 想在对比页看精致版与原版的差别：左侧选这批期望、右侧选 `batch_20261018_160124_3f440556`，同 ID 会自动配对；启用「数据」维度时，原版少绑字段的条目会判未匹配。

## 校验口径

每条都过了 `convert_compact_dsl_to_a2ui(size, protocol_profile)`（与渲染页同一严格入口），并核对：候选字段是否漏绑、DSL 里是否出现候选之外的数据路径、事件是否逐字复用、图标是否越出候选素材、2x2 图标实例是否超过 2 个，以及展开后的纵向占高是否超预算。任何一条不合格脚本直接报错退出。

重新生成：

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe debug_tools/make_refined_expect_batch.py
# 可选：--source <批跑目录> --output <数据集目录>
```

重出真实渲染截图（调试平台需在 8888 端口运行，浏览器用 Edge/Chrome）：

```powershell
cd debug_tools
node scripts/capture_dsl_preview.mjs 
  --manifest Datasets/batch_20261018_refined12_expect/import/render-manifest.json 
  --output Datasets/batch_20261018_refined12_expect/renders
```

截图脚本走的是「卡片渲染」页同一入口，所以 `renders/` 里的图就是页面实际效果；重出截图后再跑一次生成脚本，`import/payload.json` 会改用真图。

