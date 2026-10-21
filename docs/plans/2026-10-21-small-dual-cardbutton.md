# 2×2双CardButton与主辅示例 Implementation Plan

**Goal:** 双必要动作统一使用CardButton，保留全部正文和动作；补充无动作主辅与纯双操作案例。

**Architecture:** 继续使用S-content-dual-action。标准变体保留38vp内容、8vp间隔及两个36vp紧凑CardButton；
actions-only使用两个57vp CardButton、间隔8vp、12vp安全边距并整体居中。
公开CardButton属性不变，几何仅由语义布局和Recipe提供；单动作PillButton及全部2×4行为不变。

**Tech Stack:** Python、JSON布局/视觉合同、Markdown Skill、pytest、统一build_gallery.mjs。

## 实施

1. 先更新云侧方案及校验规则归属，再实现共享Recipe与尺寸可用组件。
2. 语义编译强制两个CardButton，拒绝PillButton、错误槽、手写尺寸、缺少onClick。
3. 标准变体固定36vp，只允许单行标签；纯动作槽57vp可使用既有两行标签。文本、事件、授权不放宽。
4. Plan标准化与接受提示同步CardButton；组合预算使用各自槽位规格；纯动作授权仍要求恰好两个不同必要动作。
5. CardButton通用Props归Common；尺寸文件只补槽位和容量；Plan/Repair不重复样式细则。
6. 现有双动作V03改用CardButton，补无动作数值主辅、文本主辅、纯双操作及单读数双操作。
   只复用已有示例领域、字段与动作能力，不修改测试输入或增加测试答案。
7. 定向与扩大回归；使用统一Renderer可视化全部示例并提供新增/变更示例入口。

## 验收

双动作转换、布局、绑定、动作/素材与Plan覆盖通过；非法槽与旧双PillButton拒绝；
standard与actions-only分别按126/122vp预算闭合；2×4原A2UI逐行不变。
原14个旧few-shot迁移断言中的历史ID差异需单独记录，不能以放宽校验或删字段解决。
静态示例先供用户审阅；后续用户已授权真实双动作单例验证及提交PR。
