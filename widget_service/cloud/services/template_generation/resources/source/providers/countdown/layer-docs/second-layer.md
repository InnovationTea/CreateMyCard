# 倒计时高级组件二层规则

## CountdownOverview

- 调用：`Template("CountdownOverview@1", "countdown", {})`。
- 只展示可信 `countdownDays` 与模板内置通用标签。
- 不得补造事件名、目标日期、进度或运动语义；不得输出旧构造器。
