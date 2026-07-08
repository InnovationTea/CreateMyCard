# 小艺UI渲染自动化测试工具
> 全链路零人工干预：发送Query → 自动提取DSL → 多设备并行构建渲染 → 自动截图 → AI审美打分 → 生成可视化报告，大幅提升UI测试和DSL效果验证效率。

## ✨ 核心功能亮点
| 功能 | 价值 |
|------|------|
| 🚀 **全链路自动化闭环** | 从输入Query到生成最终报告全程自动执行，不需要人工操作设备、复制DSL、构建安装、截图打分 |
| 📱 **多设备并行测试** | 支持多台鸿蒙设备同时跑全量用例，每个设备独立环境互不干扰，N台设备并行总耗时和单台一样 |
| 🎨 **AI自动审美评分** | 集成字节豆包多模态大模型，按照设计师标准自动对渲染结果打分，输出多维度评分和优化建议，不用人工一个个看效果 |
| 🧩 **零侵入兼容现有流程** | 完全不修改原有ArkTS开发流程，不用改代码、不用换构建工具，现有项目直接接入即可用 |
| 🔍 **结果可追溯可对比** | 每个Query的DSL、截图、打分结果、错误日志按设备隔离归档，方便排查问题和版本效果对比 |
| ⚡ **智能容错降级** | 单台设备/单条用例失败不影响整体流程，API调用失败自动重试，支持失败跳过/终止两种模式 |
| 📋 **全链路日志追踪** | 每个模块独立埋点，按设备SN隔离日志文件，控制台实时进度+文件完整追溯，DEBUG模式记录每次HDC命令细节 |

## 🚀 快速开始
### 1. 环境准备
- Python 3.10+
- DevEco Studio 已正确安装，配置好HarmonyOS SDK和签名，项目能正常构建HAP
- HDC工具已加入环境变量，测试设备已开启调试模式，`hdc list targets`能看到设备
- 安装依赖：
  ```powershell
  pip install httpx
  ```

### 2. 基础配置（默认已经配好，DevEco装在D盘不用改）
在`Automation/automation/config.py`顶部配置本地DevEco路径：
```python
LOCAL_DEVECO_STUDIO_HOME = Path("D:/DevEco Studio")
```

### 3. 准备测试用例
在项目根目录新建`queries.jsonl`，每行一个测试用例，格式：
```json
{"qid": "weather_card_01", "query": "帮我生成一个天气预报卡片，显示未来3天天气，要有温度、降水概率、风力信息"}
{"qid": "todo_list_01", "query": "帮我生成一个待办事项列表，支持添加、完成、删除待办，显示已完成/未完成统计"}
```

### 4. 快速运行
#### 👉 单设备批量跑所有用例+自动打分
```powershell
python Automation\main.py batch `
    --enable-aesthetics `
    --aesthetics-base-url "https://ark.cn-beijing.volces.com/api/plan/v3" `
    --aesthetics-api-key "你的API密钥"
```

#### 👉 多设备自动发现并行跑所有用例
```powershell
python Automation\main.py parallel `
    --devices auto `
    --enable-aesthetics `
    --aesthetics-base-url "https://ark.cn-beijing.volces.com/api/plan/v3" `
    --aesthetics-api-key "你的API密钥"
```

#### 👉 单独给已有截图批量打分生成报告
```powershell
python Automation\main.py aesthetics `
    --input ./output `
    --output ./output `
    --aesthetics-base-url "https://ark.cn-beijing.volces.com/api/plan/v3" `
    --aesthetics-api-key "你的API密钥"
```

## 📖 命令说明
### 公共参数（所有命令通用）
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--project-root` | 项目根目录路径 | 自动识别当前目录 |
| `--sn` | 指定运行的设备SN，单台设备时不用传 | 不指定默认用唯一在线设备 |
| `--deveco-sdk-home` | DevEco SDK路径 | `D:/DevEco Studio/sdk` |
| `--java-home` | DevEco JDK路径 | `D:/DevEco Studio/jbr` |
| `--render-wait` | 应用启动后等待截图的时间(秒) | 5 |
| `--build-timeout` | 构建安装的超时时间(秒) | 300 |
| `--enable-aesthetics` | 开启UI审美打分功能 | 关闭 |
| `--aesthetics-base-url` | 打分模型API地址 | 无 |
| `--aesthetics-api-key` | 打分模型API密钥 | 无 |
| `--aesthetics-model` | 打分模型名称 | `doubao-seed-2-0-lite` |
| `--aesthetics-max-workers` | 打分最大并发数 | 2 |
| `--aesthetics-fail-fast` | 打分失败是否中断流程 | 关闭 |
| `--debug` | 开启DEBUG日志，日志文件记录每次HDC命令、poll细节等调试信息 | 关闭 |
| `--aesthetics-enable-cache` | 开启本地缓存，相同截图不用重复调用API，节省成本和时间 | 默认关闭 |
| `--aesthetics-timeout` | 单张截图API调用超时时间(秒) | 360 |
| `--aesthetics-max-retries` | API调用失败重试次数 | 3 |

---

### 1. `one` - 运行单个测试用例
**用途**：快速验证单个Query的效果
```powershell
python Automation\main.py one `
    --qid test_weather `
    --query "帮我生成一个天气预报卡片" `
    --enable-aesthetics
```
| 参数 | 说明 | 必填 |
|------|------|------|
| `--qid` | 测试用例唯一ID | 否，默认`manual` |
| `--query` | 要发送给小艺的Query内容 | 是 |

---

### 2. `one-from-file` - 运行queries.jsonl里的单个用例
**用途**：单独重跑失败的用例
```powershell
python Automation\main.py one-from-file `
    --qid weather_card_01 `
    --enable-aesthetics
```
| 参数 | 说明 | 必填 |
|------|------|------|
| `--qid` | 要运行的用例ID | 是 |
| `--queries` | 指定用例文件路径 | 否，默认`queries.jsonl` |

---

### 3. `batch` - 单设备批量跑所有用例
**用途**：单台设备全量测试
```powershell
python Automation\main.py batch `
    --queries ./my_queries.jsonl `
    --enable-aesthetics
```
| 参数 | 说明 | 必填 |
|------|------|------|
| `--queries` | 指定用例文件路径 | 否，默认`queries.jsonl` |

---

### 4. `parallel` - 多设备并行跑所有用例
**用途**：多设备兼容性测试，多台设备同时跑全量用例
```powershell
python Automation\main.py parallel `
    --devices auto `
    --max-workers 3 `
    --enable-aesthetics
```
| 参数 | 说明 | 必填 |
|------|------|------|
| `--devices` | 设备列表，`auto`自动发现所有在线设备，或者逗号分隔的SN列表，比如`SN1,SN2,SN3` | 否，默认`auto` |
| `--max-workers` | 最大并行设备数，不要超过实际在线设备数 | 否，默认等于设备数 |
| `--queries` | 指定用例文件路径 | 否，默认`queries.jsonl` |

---

### 5. `aesthetics` - 独立对已有截图打分
**用途**：不用跑完整流程，直接给已有截图批量打分生成报告
```powershell
# 批量给目录下所有截图打分
python Automation\main.py aesthetics `
    --input ./output `
    --output ./output `
    --sn 设备SN
```
| 参数 | 说明 | 必填 |
|------|------|------|
| `--input` | 输入图片目录或者单张图片路径 | 是 |
| `--output` | 输出目录或者结果文件路径 | 否，默认和输入同目录 |
| `--skip-report` | 跳过生成HTML报告，只输出JSON结果 | 否，默认生成报告 |
| `--sn` | 设备SN，用于结果关联 | 否 |

## 📏 UI审美评分维度说明
总分按照8分制换算为100分，6个维度加权计算，完全符合设计行业通用评分标准：

| 维度名称 | 权重 | 判断标准 |
|---------|------|----------|
| **视觉冲击/原创性** | 30% | 最高权重，判断界面是否有记忆点、明确的主题气质和非模板化表达<br>✅ 高分：有强中心视觉、稳定氛围、原创构图、品牌感，和AI生成的通用模板有明显区别<br>❌ 低分：默认模板风格、简单卡片堆砌、毫无设计感，和常见demo没有区别 |
| **构图/层级** | 20% | 判断页面的信息组织、视觉重心、空间节奏和阅读路径是否合理<br>✅ 高分：首屏主次关系清晰、核心内容突出、导航/内容/操作区分明、布局有节奏感<br>❌ 低分：布局混乱、层级缺失、核心内容难以定位、大面积空白/拥挤，像未完成的原型 |
| **字体排版** | 15% | 判断字体选择、字号层级、字重、行高、对齐和文本排版是否形成稳定系统<br>✅ 高分：字体选择符合产品气质、字号层级清晰、对齐统一、排版干净有设计感<br>❌ 低分：系统默认字体痕迹重、字号/字重混乱、文字拥挤/错位/重叠、可读性差 |
| **颜色/材质** | 15% | 判断配色、明暗关系、材质质感、光影、边框、阴影和背景处理是否统一<br>✅ 高分：颜色系统成熟、材质光影统一、配色协调有主题感，没有廉价渐变/彩虹色<br>❌ 低分：配色随意/混乱、阴影生硬、材质粗糙、大面积高饱和色块堆砌，视觉刺眼 |
| **细节/完成度** | 15% | 判断整体细节处理和完成度，是否达到产品级设计标准<br>✅ 高分：图标/按钮/卡片风格统一、圆角/间距/边距规范统一、细节精致，像完整产品<br>❌ 低分：元素风格不统一、圆角大小不一、间距忽大忽小、细节粗糙，像快速拼凑的半成品 |
| **基础可用性** | 5% | 最低门槛，判断静态截图的可读、可识别性，不属于审美维度<br>✅ 高分：信息清晰、控件可识别、结构稳定，没有明显遮挡/错位/溢出<br>❌ 低分：核心信息不可读、按钮/输入/导航被遮挡/错位、布局严重影响理解 |

## 📂 输出目录结构
所有结果按设备SN隔离，互不干扰，方便追溯：
```
项目根目录/
├── dsl/                            # DSL提取结果目录
│   └── {设备SN}/                   # 按设备隔离
│       ├── {SN}_{qid}.jsonl        # 单个Query提取的DSL文件
│       └── ...
└── output/                         # 渲染和打分结果目录
    └── {设备SN}/                   # 按设备隔离
        ├── {SN}_{qid}.jpeg         # 单个Query的渲染截图
        ├── scores.jsonl            # 结构化打分结果，包含所有维度得分、问题、建议
        └── report.html             # 可视化打分报告，包含所有截图和评分详情
```

## 📋 日志系统

### 日志输出位置
- **控制台**：实时显示进度和关键事件（INFO/WARNING/ERROR）
- **文件**：`output/{设备SN}/pipeline.log`，完整记录所有事件，用于事后排查

### 日志格式
```
2026-07-06 15:30:00 [SN123456] xiaoyi INFO collect_dsl_for_query start: qid=q1
2026-07-06 15:30:45 [SN123456] xiaoyi INFO _wait_and_extract: DSL found, reply_len=3421
2026-07-06 15:30:45 [SN123456] arkts INFO render start: qid=q1
2026-07-06 15:31:10 [SN123456] arkts INFO hvigor assembleHap done: 22.3s
2026-07-06 15:31:15 [SN123456] arkts INFO hdc file send done: 4.8s
2026-07-06 15:31:20 [SN123456] arkts INFO bm install done: 3.2s
2026-07-06 15:31:25 [SN123456] arkts INFO render done: qid=q1 total=40.2s screenshot=q1.jpeg
2026-07-06 15:31:25 [SN123456] pipeline INFO run_one done: qid=q1 total=85.3s
```

### 日志级别
| 级别 | 说明 | 输出位置 | 示例 |
|------|------|---------|------|
| INFO | 阶段开始/结束、耗时、正常状态变化 | 控制台+文件 | `render done: qid=q1 total=40.2s` |
| WARNING | 重试、降级策略、非致命异常 | 控制台+文件 | `snapshot_display retry 2/3` |
| ERROR | 失败、超时、致命错误 | 控制台+文件 | `HDC command failed: ...` |
| DEBUG | 每次HDC命令、每次poll、完整响应 | 仅文件（--debug开启） | `run: list targets -> rc=0` |

### 各模块埋点覆盖
| 模块 | 埋点位置 | 定位的问题 |
|------|---------|-----------|
| hdc.py | run() 超时/失败、snapshot_display 重试/成功/文件太小 | 设备连接异常、截图文件异常 |
| xiaoyi.py | wait_ready 超时、send_query 控件定位失败、collect_dsl_for_query 重试、DSL找到、scroll_scan 兜底 | 小艺界面异常、DSL提取失败 |
| arkts.py | render 开始/结束耗时、hvigor clean/assembleHap 各阶段耗时、file send 推送耗时、bm install 耗时、ability start | 编译失败、安装失败、推送慢 |
| pipeline.py | run_one/run_batch 开始/结束、各环节总耗时 | 整体流程耗时分析 |
| main.py | 设备发现、并行调度 | 多设备并行调度异常 |

### 使用方式
```powershell
# 正常模式：控制台看进度，日志文件存到 output/{SN}/pipeline.log
python Automation\main.py batch

# DEBUG 模式：日志文件额外记录所有 HDC 命令、poll 细节
python Automation\main.py batch --debug
```

### 排查问题流程
1. 打开 `output/{设备SN}/pipeline.log`
2. 搜索 `ERROR` 定位致命错误
3. 搜索 `WARNING` 查看重试和降级
4. 如果信息不够，加 `--debug` 重新跑，日志文件会记录每次 HDC 命令和 poll 细节

---

## 🏗️ 项目目录结构
```
├── Automation/                     # 自动化核心代码
│   ├── automation/                 # 核心模块
│   │   ├── config.py               # 全局配置
│   │   ├── hdc.py                  # HDC命令封装，设备操作
│   │   ├── xiaoyi.py               # 小艺交互、DSL自动提取
│   │   ├── arkts.py                # ArkTS自动构建、签名、安装、启动、截图
│   │   ├── pipeline.py             # 流程编排，串起各个环节
│   │   ├── dsl.py                  # DSL解析、修复、校验
│   │   ├── queries.py              # 测试用例文件读取
│   │   └── ui_tree.py              # UI树解析、控件定位
│   │   └── logger.py                # 日志模块，统一日志格式和输出
│   ├── main.py                     # 命令行入口
│   └── .work/                      # 临时工作目录，自动生成，包括每个设备的ArkTS副本、缓存
├── visual_aesthetics/              # AI审美打分模块
│   ├── core/                       # 核心评分逻辑、评分标准、类型定义
│   ├── models/                     # 大模型调用封装，目前支持字节豆包多模态
│   ├── utils/                      # 工具类：缓存、图片处理
│   ├── reports/                    # 可视化报告生成器
│   ├── config.py                   # 打分模块配置
│   └── judge.py                    # 对外统一接口
├── ArkTs/                          # ArkTS项目源码，团队维护，自动化流程作为模板复制到各设备工作目录
├── queries.jsonl                   # 测试用例文件，自己添加
└── README.md                       # 项目文档
```

## ⚙️ 配置说明
### 配置优先级（从高到低）
1. **命令行参数** → 2. **环境变量** → 3. **配置文件默认值**

### 常用环境变量，配置后不用每次传参数
```powershell
# DevEco全局配置
$env:DEVECO_SDK_HOME = "D:/DevEco Studio/sdk"
$env:JAVA_HOME = "D:/DevEco Studio/jbr"

# 审美打分全局配置，配置后不用每次传密钥
$env:AESTHETICS_BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"
$env:AESTHETICS_API_KEY = "你的API密钥"
$env:AESTHETICS_MODEL = "doubao-seed-2-0-lite"
```

## ❓ 常见问题排查
### Q1：运行提示找不到设备
A：检查设备是否开启调试模式，HDC是否能识别设备：
```powershell
hdc list targets
```
如果识别不到，重启HDC服务：
```powershell
hdc kill && hdc start -r
```

### Q2：ArkTS构建失败
A：先手动打开ArkTS项目，执行一次构建，确保能正常生成签名HAP，常见原因：
1. DevEco签名配置错误
2. 依赖没有安装
3. 磁盘空间不足
4. 看`Automation/.work/{SN}/ArkTs/build`目录下的构建日志排查具体错误

### Q3：DSL提取失败
A：检查小艺是否已经打开，输入法是否正常弹出，常见原因：
1. 小艺没有启动或者被后台杀死
2. 屏幕亮度太低导致UI树识别失败
3. 网络不好小艺回复超时，可以加大`--reply-timeout`参数

### Q4：审美打分API调用失败
A：检查：
1. API地址和密钥是否正确
2. 网络是否能访问火山方舟API
3. 模型是否已经开通权限
4. 可以加大`--aesthetics-timeout`和`--aesthetics-max-retries`参数

### Q5：如何排查运行中断的原因
A：查看对应设备的日志文件 `output/{设备SN}/pipeline.log`，搜索 `ERROR` 和 `WARNING` 定位问题。如果信息不够，加 `--debug` 参数重新运行，日志文件会记录每次 HDC 命令和 poll 细节。

### Q6：多设备运行时某台设备失败
A：不会影响其他设备运行，失败设备的错误信息会单独打印，其他设备继续执行。可以单独指定失败设备的SN重新运行：
```powershell
python Automation\main.py batch --sn 失败设备的SN
```


