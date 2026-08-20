# 问题样本真实重跑报告

本次只重跑上一版报告列出的 49 条；每条均重新调用 DeepSeek，没有复用旧输出。路由由模板 facade 是否实际返回记录。

## 结果

- 模板直出成功：12 条
- LLM 全量生成成功：7 条
- 未出卡：30 条

## 上一版被错误标为问题、此次确认模板直出

- TRE-021：做一张下一个会议提醒，必须显示会议标题和开始结束时间 → `a2ui/TRE-021.a2ui`
- TRE-022：显示下一场日程的标题、时间和地点 → `a2ui/TRE-022.a2ui`
- TRE-023：给我做个专注风格的下一场会议卡，只看标题和时间 → `a2ui/TRE-023.a2ui`
- TRE-024：今天有什么安排，显示第一条日程标题 → `a2ui/TRE-024.a2ui`
- TRE-031：用睡眠夜紫主题显示下一场会议 → `a2ui/TRE-031.a2ui`
- TRE-040：暖黄色风格显示我今天刷短视频用了多久 → `a2ui/TRE-040.a2ui`
- TRE-044：做一张2x4的应用使用时长卡 → `a2ui/TRE-044.a2ui`
- TRE-069：我要睡眠时长卡，重点显示昨晚睡了多久 → `a2ui/TRE-069.a2ui`
- TRE-070：显示昨晚睡眠时长和睡眠状态 → `a2ui/TRE-070.a2ui`
- TRE-071：做一张2x4睡眠作息卡，显示入睡、起床和睡眠时长 → `a2ui/TRE-071.a2ui`
- TRE-095：显示下一场会议的标题和时间 → `a2ui/TRE-095.a2ui`
- TRE-096：看睡眠时长 → `a2ui/TRE-096.a2ui`

## LLM 全量生成成功（没有走模板直出）

- TRE-019：显示今天日期和星期几 → `a2ui/TRE-019.a2ui`
- TRE-020：来一个暖黄色的今天日期卡 → `a2ui/TRE-020.a2ui`
- TRE-028：做日期卡，显示上次同步时间 → `a2ui/TRE-028.a2ui`
- TRE-032：做一个只显示今天日期的2x2卡 → `a2ui/TRE-032.a2ui`
- TRE-047：给我一个低电量蓝牙耳机卡，显示总电量 → `a2ui/TRE-047.a2ui`
- TRE-067：昨晚平均心率是多少 → `a2ui/TRE-067.a2ui`
- TRE-098：做一个耳机连接状态卡 → `a2ui/TRE-098.a2ui`

## 未出卡：请求在模型前被拒

- TRE-026：日程卡必须显示参会人；`GenerationPreflightError: generation preflight rejected 1 issue(s)`
- TRE-027：日程提醒里要有会议号；`GenerationPreflightError: generation preflight rejected 1 issue(s)`
- TRE-036：倒计时里必须写出目标日期；`GenerationPreflightError: generation preflight rejected 1 issue(s)`
- TRE-037：倒计时卡要显示进度百分比；`GenerationPreflightError: generation preflight rejected 1 issue(s)`
- TRE-042：应用使用卡还要展示今天的使用上限和剩余时长；`GenerationPreflightError: generation preflight rejected 2 issue(s)`
- TRE-052：耳机卡要展示降噪模式；`GenerationPreflightError: generation preflight rejected 1 issue(s)`
- TRE-059：电量卡必须显示预计充满时间；`GenerationPreflightError: generation preflight rejected 1 issue(s)`
- TRE-060：电量卡要有电池健康度；`GenerationPreflightError: generation preflight rejected 1 issue(s)`
- TRE-074：运动卡必须展示配速；`GenerationPreflightError: generation preflight rejected 1 issue(s)`
- TRE-075：睡眠卡要有睡眠评分和各阶段图；`GenerationPreflightError: generation preflight rejected 1 issue(s)`
- TRE-081：做一张内存占用卡，显示占用比例、可用内存和总内存；`ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type`
- TRE-082：系统内存还剩多少，给我蓝色卡；`ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type`
- TRE-083：内存卡要展示存储空间使用情况；`ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type`
- TRE-084：显示内存占用趋势和历史曲线；`ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type`
- TRE-085：系统内存占用；`ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type`
- TRE-086：用赛跑主题做内存使用卡；`ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type`
- TRE-087：内存卡显示可用内存；`ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type`
- TRE-090：显示股票价格和涨跌；`ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type`

## 未出卡：DeepSeek 全量输出未通过 A2UI 校验

- TRE-039：做个屏幕使用时间卡，显示应用名称和今天用了多久；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-041：做一个应用使用概览，显示应用名；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-043：应用使用卡显示上次更新时间；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-053：耳机连接状态用会议纸张主题展示；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-068：做一个心率卡，平均心率和更新时间都要有；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-076：显示平均心率；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-080：我要一张深色专注风的平均心率卡；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-091：做天气卡显示温度；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-092：做一个天气卡；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-093：做天气卡显示温度；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-094：做天气卡显示温度；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
- TRE-097：显示平均心率；服务码 `VALIDATION_FAILED`；模型输出开头：````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":`
