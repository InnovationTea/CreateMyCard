# Tersel 协议

本文定义 `template_generation` 模块使用的受限 Tersel 组件树协议。历史文档和代码中的
`Tersel-Nest2`、`TerseDSL-Nested-2`、`Nested-2` 统一归为 **Tersel**。现有 WebSocket operation
仍保留旧名称，但 Python 模块、函数和内部输出字段不再提供旧名称兼容层。

## 1. 文档结构

完整 Tersel 文档包含一棵组件树，以及可选的静态预览 `data` 对象：

```tersel
Column("Card",
  Text("上海", "title")
);
data = {"weather": {"city": "上海"}}
```

约束如下：

- 第一条语句必须是一个直接组件调用，完整卡片的根组件只允许 `Column` 或 `Stack`。
- 第二条语句若存在，只能是 `data = {...}`；不得出现变量声明、赋值链或其它语句。
- 组件、对象、数组和标量都只作为数据解析，禁止执行、动态导入、成员调用和关键字参数。
- 组件值参数必须位于第一个子组件之前；子组件只能是直接组件调用，不使用 `[]` 包装。
- 单个文档最多 256 个组件，组件和字面量最多嵌套 32 层。

## 2. 组件调用签名

统一签名为：

```text
ComponentName(requiredValues..., designToken?, inlineStyles?, ...children)
```

其中：

- `requiredValues` 是组件自身必需值，例如 `Text` 的可见内容、`Image` 的资源地址。
- `designToken` 是组件对应的可选字符串 Token，必须紧跟在必需值之后。
- `inlineStyles` 是可选对象，必须位于最后一个值参数位置。
- `children` 只允许出现在 `Row`、`Column`、`List`、`Stack` 等容器中。
- 本轮不支持运行时 `If` 组件；模板 `#if/#elseif/#else/#endif/#end` 只做编译期选择，
  不输出虚拟节点。`Expr(...)` 可继续生成组件属性中的运行时表达式。

Tersel 只接受当前 Form Catalog 的标准组件，不定义 `FusionBall` 等云端组件。融球 Theme 由受信模板编译器
在序列化 Tersel 前展开为标准 `Stack` 组件树，因此 Tersel 转换器遇到 `FusionBall(...)` 必须按未知组件拒绝。

解析器先展开 DesignToken，再合并内联样式。内联样式优先级更高；同名属性由内联值覆盖 Token 默认值。
最终 A2UI 只包含展开后的标准属性，不保留 DesignToken。

## 3. 三种样式写法

以下示例用于说明单个组件签名；作为完整卡片根节点时，`width`/`height` 仍受第 5 节的尺寸锁定约束。

### Option 1：只使用 DesignToken

```tersel
Column("Compact",
  Text("hello world", "title")
)
```

### Option 2：DesignToken 加内联样式

```tersel
Column("Compact", {"width": 120},
  Text("hello world", "title", {"fontColor": "#FF1122"})
)
```

### Option 3：只使用内联样式

```tersel
Column({"width": 120},
  Text("hello world", {"fontColor": "#FF1122", "fontSize": 30})
)
```

三种写法可以在同一棵组件树中混用。Provider `.cardtpl` 是受信模板资源，当前统一使用 Option 3，避免
把 DesignToken 作为模板 Prompt 的 Token 优化手段；模型生成的普通 Tersel 仍可使用 Option 1 或 Option 2。

## 4. 当前 DesignToken

| 组件 | Token |
| --- | --- |
| `Column` | `Card`、`Section`、`Compact` |
| `Row` | `Between`、`Actions` |
| `List` | `List`、`Dense` |
| `Stack` | `Card`、`Overlay` |
| `Text` | `title`、`compact-title`、`compact-action`、`body`、`subtitle`、`success`、`warning` |
| `Image` | `icon`、`compact-icon`、`thumbnail`、`hero` |
| `Button` | `default`、`primary`、`small` |

容器 Token 的首字母大写形式是本文推荐写法。解析器继续接受旧资源使用的小写形式，例如 `compact`、
`between` 和 `overlay`。没有登记 DesignToken 的组件只能使用内联样式，未知 Token 必须明确报错，不能按
普通字符串猜测。

## 5. 根组件与尺寸

根组件由目标卡片尺寸锁定外围宽高。`2x2` 和 `2x4` 的尺寸由当前协议 Profile 决定；根组件的内联样式
不得覆盖 `width` 或 `height`。根 `Column`/`Stack` 可以使用 DesignToken，也可以只写内联样式。根以下的
普通容器不受该尺寸锁定，可以按三种 Option 正常设置宽高。

## 6. 动态值与 `data`

简单动态值使用完整路径占位，例如：

```tersel
Text("${data.weather.current.temperatureText}", "body")
```

拼接、条件、算术或 `size()` 使用受限 `Expr("...")`。表达式至少引用一个本轮 TaskSpec/DataModel 路径，
转换后统一成为 A2UI `{{ ... }}` 表达式。纯静态内容继续写字面量，不使用表达式伪装。
这里的 `Expr("...")` 是可信展开后的 Tersel 语法；Provider `.cardtpl` 作者侧改用无需外层引号的
`Expr(data.xxx + "单位")`，由模板编译器先解析为绑定 IR，再映射实际 path，不能在云侧读取数据值求值。

`data` 只保存本轮真实 TaskSpec 路径的预览初值。组件引用的动态路径必须在 `data` 中存在，且不得出现
`_advancedSelectors`、`_templateProjection` 等内部投影字段。

CardTpl 和可信展开后的 Tersel 内联样式还可使用受限 `$theme('<path>')` 颜色引用。允许路径由 Theme Base
统一声明，仅包括 `primaryColor`、`supportContentColor`、`actionStyle.backgroundColor` 和
`actionStyle.contentColor`。解析器只接受直接调用，并要求调用方传入本轮已选 Theme 的完整取值；路径未知、
值缺失或值不是 `#AARRGGBB` 时整次转换失败。解析时直接替换为真实值，最终 A2UI 不保留 `$theme`。
主内容和辅助内容的归类由 Provider 模板显式声明，解析器不按字号、位置、DesignToken 或文案进行猜测。

## 7. 安全与失败规则

- 只允许 Catalog 白名单组件和受限字面量；禁止 `eval`、函数执行、任意属性访问和字典展开。
- 禁止对象键 `__proto__`、`prototype`、`constructor`，并拒绝重复对象键。
- DesignToken 必须属于当前组件；Token 不能跨组件复用。
- 内联样式必须是一个对象，并位于最后一个值参数位置。
- 叶子组件不得包含 children；容器 children 前不得再出现值参数。
- 非法组件、未知 Token、非法表达式、越界路径、超限深度或组件数都必须终止转换，不输出部分 A2UI。

## 8. 对外保留名称

以下名称因对外接口稳定性保留：

- Profile ID：`terse-dsl-nested-2`。
- WebSocket operation：`generateWidgetCardTerseDslNested2`。

模板内部只使用 `tersel_converter.py`、`parse_tersel()`、`convert_tersel_to_a2ui()` 和 `tersel` 输出字段，
不维护第二套 Parser 或旧 Python 别名。
