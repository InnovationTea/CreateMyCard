# 视觉和交互指导

## 默认视觉方向

除非用户要求极简/朴素输出，默认应当：

- 精致
- 有层次
- 紧凑
- 贴合场景
- 在 GenUI extended Catalog 限制内具有视觉表现力

不要默认使用最少组件。使用所选尺寸预算和语义角色建立清晰层级。

## 真实交互

可点击区域必须是真实的：

- 当整个区域可点击时，在 `Stack`、`Row` 或 `Column` 上使用 `onClick`。
- 当语义上是按钮时，使用带 `label` 和 `onClick` 的 `Button`。
- 不要画没有事件的假按钮。
- 对点击、拨号、打开应用或详情页，优先读取 [`event-capability/click-event.md`](event-capability/click-event.md)，使用已声明的 `functionCall`、`parameters` 和 `supportedTargets`。
- 对未在 event capability 中声明的应用特定动作，才使用有意义的宿主函数名，并明确它是宿主假设；所需 ID 从 DataModel 绑定。

示例：

```json
{"id":"focusAction","component":"Stack","children":["focusLabel"],"onClick":[{"call":"enterFocusMode","args":{"meetingId":{"path":"/meeting/id"}}}]}
```

## 按钮安全

- `Button.label` 必须是可见文本。
- Form 不使用 `Button.action`；按钮点击写在 `Button.onClick`。
- 如果动作只是宿主占位，最终回复中说明；如果最终格式禁止额外说明，则不要生成该占位点击。
- CTA 文本是受保护内容：保持一行，不要强行放进狭窄固定宽度。

## 图片来源

- 需要图标、图片、背景图、媒体路径或视觉锚点时，先读 [`asset-library.md`](asset-library.md)，按用户场景和素材 `description` 选择语义匹配的已声明 `src`。
- 如果用户明确指定了本地/资源路径，可使用用户提供路径；否则不要跳过素材库去编造路径。
- 静态素材可直接写入 `Image.src`；如果素材选择由 DataModel 管理，绑定到 `/asset/...`，并把值初始化为素材库中声明过的 `src`。
- 不要编造网络 URL、相似资源路径或素材库中没有声明的文件名。
- 如果没有语义匹配且可靠的图片，使用渐变、`Stack`、半透明块、文本字形、`Divider` 或 `Progress`。

## 媒体真实性

`Image.src` 和 `styles.backgroundImage` 不支持网络 URL。`example.com`、`placeholder.com` 和 `picsum.photos` 等占位域名不能用于最终卡片输出。未由用户提供、也未在素材库声明的资源路径不能用于最终输出。

## 反模式

避免：

- 在 extended 卡片中使用 standard-catalog 属性名。
- 把没有事件的样式化文本伪装成按钮。
- 一张紧凑卡片中有太多小卡片块。
- 只有竖向文本堆叠，没有视觉焦点。
- 标签组和 CTA 按钮挤在同一行互相争抢。
- 从示例产物复用颜色或结构，而不是服务当前场景。
- 图片背景遮住核心文本。
- 使用素材库未声明、拼写改造或与当前场景语义不匹配的资源路径。
- 本应来自 DataModel 的宿主动作 args 被硬编码。
- `onClick.call` 使用了未在 event capability 或宿主声明中的函数名。
- 跳转目标不在 event capability 的 `supportedTargets` 中。
