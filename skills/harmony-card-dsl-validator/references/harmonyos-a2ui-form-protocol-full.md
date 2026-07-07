# HarmonyOS A2UI Form 卡片协议

## 修改记录

> ⚠ 修改记录已迁移到独立文件，**请勿在此章节编辑**。
> 回写位置：[modification-history-form.md](modification-history-form.md)

完整修改记录详见 [modification-history-form.md](modification-history-form.md)。

## 1 协议说明

### 1.1 概述

本协议是鸿蒙 A2UI 扩展协议的 Form（服务卡片）裁剪版本。Form 是鸿蒙系统中的轻量级展示组件，运行在独立的卡片渲染服务进程中，开发和运行环境受限。

Form 协议是鸿蒙 A2UI 扩展协议的**严格子集**——不新增任何全量协议之外的组件、属性或语法，仅排除 Form 环境不需要的能力。因此，基于本协议生成的 DSL 可在支持全量扩展协议的 Render 中正确渲染。同样，基于全量协议生成的 DSL 中，仅使用 Form 支持组件和能力的部分，也可在 Form Render 中正确渲染。

Form 协议仅支持鸿蒙 A2UI 扩展协议中的扩展组件，不支持 A2UI 原生组件。Form 支持的组件范围以 `form_catalog.json` 中声明的扩展组件为准。

### 1.2 能力裁剪说明

| 维度 | Form 可用 | 说明 |
|------|----------|------|
| A2UI 原生组件 | 全部排除 | Form 仅使用扩展组件，不支持 A2UI 原生组件 |
| 扩展组件 | 10/21 | 排除 TextInput/Toggle/Radio/CheckboxGroup/Select/NavContainer/Tabs/TabContent/Web/Grid/If |
| 通用事件 | 仅 onClick | 排除 onAppear |
| 组件私有事件 | 全部排除 | 排除 onChange/onSelect/onReachStart/onReachEnd |
| 预定义扩展函数 | 全部排除 | 应用方通过自定义函数机制定义所需函数 |
| 自定义组件 | 支持 | 通过 catalog 注册机制 |
| 自定义函数 | 支持 | 通过 §3.4.3 自定义扩展函数机制 |
| 表达式系统 | 支持 | 完整表达式语法 + 响应式更新 |
| 变量系统 | 支持 | 排除响应式变量 $__widthBreakpoint/$__colorMode |
| 子组件模板 | 支持 | Row/Column/List 模板循环，支持 itemVar/indexVar 自定义变量名 |
| 行为链 | 支持 | EventHandler 数组 + condition + as 绑定 |
| 多端自适应 | 排除 | 不支持响应式断点 |

## 2 A2UI原生协议

本章节简要介绍 A2UI 协议关键能力，详细请参考官方说明[[a2ui_protocol](https://github.com/google/A2UI/blob/v0.9/specification/v0_9/docs/a2ui_protocol.md)]

### 2.1 协议消息

#### 2.1.1 协议数据流

1. Create Surface: 服务端发送 createSurface 消息以初始化界面。

2. Update Components：一旦界面创建好了，服务端通过发送一个包含UI组件定义的updateComponents消息来定义界面。

3. Update Data Model: 界面创建好之后，服务端可以在任意时刻发送updateDataModel消息来定义或者修改UI组件的数据。

4. Render：客户端根据updateComponents消息和updateDataModel消息渲染UI界面。

5. Dynamic updates：当用户与应用交互或者有新的信息时，服务端可以发送 updateDataModel 消息来动态更新数据。

6. Delete Surface：当UI界面已经不需要了，服务端可以发送deleteSurface消息移除该界面。

 > 参考官网流程图了解详细数据流[[Data Flow](https://a2ui.org/concepts/data-flow/)]



#### 2.1.2 消息顺序

1. updateComponents必须在createSurface之后发出。
2. updateComponents和updateDataModel先后顺序没有约束。
3. 不同的surface之间的消息应该独立。
4. Form 不支持增量/流式构建，同一 surface 仅接受一次完整的 updateComponents 消息。后续 updateDataModel 消息可以多次更新数据，但不支持通过多次 updateComponents 增量修改组件树。

#### 2.1.3 createSurface消息

**消息格式**

```json
{
  version: "v0.9";
  createSurface: {
    surfaceId: string;      // Required: Unique surface identifier
    catalogId: string;      // Required: URL of component catalog
    sendDataModel?: boolean; // Optional: Request client to send data model updates
  }
}
```

> Form 不支持 `theme` 字段（主题配置）。

**消息示例**

```json
{
  "version": "v0.9",
  "createSurface": {
    "surfaceId": "main",
    "catalogId": "ohos.a2ui.extended.catalog"
  }
}
```

#### 2.1.4 updateComponents消息

**消息格式**

```json
{
  version: "v0.9";
  updateComponents: {
    surfaceId: string;        // Required: Target surface
    components: Array<{       // Required: List of components
      id: string;             // Required: Component ID
      component: string;      // Required: Component type name
      ...properties           // Component-specific properties (flat)
    }>
  }
}
```

**单组件示例**

```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "main",
    "components": [
      {
        "id": "greeting",
        "component": "Text",
        "content": "Hello, World!"
      }
    ]
  }
}
```

**多组件示例**

```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "main",
    "components": [
      {
        "id": "root",
        "component": "Column",
        "children": ["header", "body"]
      },
      {
        "id": "header",
        "component": "Text",
        "content": "Welcome"
      },
      {
        "id": "body",
        "component": "Row",
        "children": ["content"]
      },
      {
        "id": "content",
        "component": "Text",
        "content": "{{ $__dataModel.message }}"
      }
    ]
  }
}
```

#### 2.1.5 updateDataModel消息

**消息格式**

```json
{
  version: "v0.9";
  updateDataModel: {
    surfaceId: string;      // Required: Target surface
    path?: string;          // Optional: JSON Pointer path (defaults to "/")
    value?: any;            // Optional: Value to set (omit to delete)
  }
}
```

**初始化整个数据示例**

```json
{
  "version": "v0.9",
  "updateDataModel": {
    "surfaceId": "main",
    "path": "/",
    "value": {
      "user": {
        "name": "Alice",
        "email": "alice@example.com"
      },
      "items": []
    }
  }
}
```

**更新数据示例**

```json
{
  "version": "v0.9",
  "updateDataModel": {
    "surfaceId": "main",
    "path": "/user/email",
    "value": "alice@newdomain.com"
  }
}
```

> **路径自动追加**：当 `path` 指向的路径在当前 DataModel 中不存在时，自动创建中间路径并写入值。例如 DataModel 中 `"/user"` 尚不存在时，`path: "/user/email"` 会自动创建 `/user` 对象并写入 `email` 字段。

#### 2.1.6 deleteSurface 消息

**消息格式**

```json
{
  version: "v0.9";
  deleteSurface: {
    surfaceId: string;        // Required: Surface to delete
  }
}
```

**消息示例**

```json
{
  "version": "v0.9",
  "deleteSurface": {
    "surfaceId": "modal"
  }
}
```

#### 2.1.7 能力协商机制

由于客户端和服务端智能体可以支持多个catalog，所以他们需要通过catalog协商握手机制来决定使用哪个catalog，具体机制如下：

1. **智能体公布其支持的catalog（可选）**：智能体可以公布其支持哪些catalog（比如通过A2A的Agent Card形式）。这个可以帮助客户端知道是否智能体支持客户端特定的能力，但是这个信息仅供客户端参考，客户端不一定要使用，该过程也是可选的。

```json
{
  "name": "Ecommerce Dashboard Agent",
  "description": "This agent visualizes ecommerce data...",
  "capabilities": {
    "extensions": [
      {
        "uri": "https://a2ui.org/a2a-extension/a2ui/v0.8",
        "description": "Provides agent driven UI using the A2UI JSON format.",
        "params": {
          "supportedCatalogIds": [
            "ohos.a2ui.extended.catalog"
          ]
        }
      }
    ]
  }
}
```

2. **客户端公布其支持的（必选）Catalog**：客户端可以在每条消息的metadata部分发送其支持的catalog列表给智能体，catalog可以通过偏好来排序。通过这个来精确告知智能体客户端具体的渲染能力。以下是以A2A消息为例：

```json
{
  "parts": [
    {
      "content": "What is the current status of my flight?"
    }
  ],
  "metadata": {
    "a2uiClientCapabilities": {
      "supportedCatalogIds": [
        "ohos.a2ui.extended.catalog"
      ]
    }
  }
}
```

3. **智能体选用catalog**：当智能体创建新的界面时，需要从客户端发送的支持的catalog列表中选择一个最匹配的来使用。在一个界面的生成过程中（即一次createSurface生命周期过程）仅能按照这一个选定的catalog来生成界面，同一个会话中的多个界面生成可以选用不同的catalog。如果没有匹配的catalog，智能体可以不发送界面。

```json
{
  "createSurface": {
    "surfaceId": "salesDashboard",
    "catalogId": "ohos.a2ui.extended.catalog"
  }
}
```

## 3 A2UI扩展设计

### 3.1 扩展说明

1. 扩展组件类型、样式属性、交互以及表达式能力，这些能力均只在扩展组件上生效，A2UI原生组件上不支持这些扩展能力。
2. Form 协议仅支持扩展组件，不支持 A2UI 原生组件。`createSurface` 时必须指定 `catalogId: "ohos.a2ui.extended.catalog"`。
3. 扩展组件与原生组件采用统一命名（如 `Button`、`Text`），通过 `catalogId` 字段区分组件来源。

### 3.2 扩展组件

Form 协议仅使用扩展组件，扩展更丰富的组件类型支撑多样化 UI 能力。新增组件在 updateComponents 消息中的描述沿袭 A2UI 数据结构组织方式，详细扩展组件及属性参见 [§4.2.1 组件](#421-组件)。

```json
// createSurface 时指定扩展 catalog
{
  "version": "v0.9",
  "createSurface": {
    "surfaceId": "main",
    "catalogId": "ohos.a2ui.extended.catalog"
  }
}

// updateComponents 中直接使用统一组件名，无需再指定 catalogId，通过 surfaceId 关联到创建的 surface
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "main",  // 使用 createSurface 创建的 surfaceId
    "components": [
      {
        "id": "submit-btn", // 必选，组件ID
        "component": "Button", // 必选，组件类型
        "label": "按钮", // 组件必选属性
        "styles": {  // 可选样式属性
          "fontColor":"#33182431",
          "fontSize":12,
          "other prop":"value"
        }
        // 其他组件相关必选和可选属性
      }
    ]
  }
}
```

### 3.3 扩展组件样式

在扩展组件中统一添加styles字段，其值为一个对象，内容为需要设置的属性名及值，若没有明确配置，则使用匹配组件的默认值。具体属性名称和值类型参见[通用样式](#4212-通用样式)章节。

```json
{
  "id": "submit-btn",
  "component": "Button",
  "label": "submit-text",
  "styles": {
    "fontColor":"#33182431",
    "fontSize":12,
    "other prop":"value"
  }
}
```

### 3.4 扩展函数

A2UI 表达式系统提供内置函数 `size()`（参见 [§4.2.2.1.4 内置函数](#422214-内置函数)）。在此基础上，协议支持通过 catalog 注册自定义扩展函数，函数一般使用在一次性求值的地方，如组件属性计算或校验、事件上下文求值等。

#### 3.4.3 自定义扩展函数

除预定义函数外，协议支持在扩展 catalog 中声明自定义扩展函数。自定义函数声明负责定义函数名、参数类型、返回值类型和使用范围；EventHandler 仅通过 `call` 引用已声明的函数，不重复声明返回类型。

函数定义包含以下字段：

| 字段 | 必选 | 说明 |
|------|------|------|
| `description` | 否 | 函数说明 |
| `args` | 否 | 函数参数的 JSON Schema 定义 |
| `returnType` | 否 | 函数返回值类型。无返回值函数可声明为 `void` 或省略 |
| `interactionOnly` | 否 | 是否仅允许在交互上下文中使用。具有 UI 操作、副作用或依赖事件上下文的函数应设为 `true` |

示例 — 在扩展 catalog 的 `functions` 中定义名为 `validateForm` 的交互函数：

```json
{
  "functions": {
    "validateForm": {
      "description": "Validate form data before submission",
      "interactionOnly": true,
      "args": {
        "type": "object",
        "properties": {
          "data": {
            "type": "object",
            "format": "Expression",
            "description": "The form data to validate"
          }
        },
        "required": ["data"],
        "additionalProperties": false
      },
      "returnType": {
        "const": "boolean"
      }
    }
  }
}
```

定义后，EventHandler 的 `call` 字段即可引用该函数名：

```json
{
  "call": "validateForm",
  "args": {
    "data": "{{ $__dataModel.form }}"
  },
  "as": "validResult"
}
```

### 3.5 事件监听与交互

扩展组件支持通过注册监听事件来定义交互响应行为，使用结构示意如下：

```
{
  "component": "组件类型名",
  ... ...           // 组件属性
  "styles": {...}   // 组件样式
  "事件类型 1": [
    EventHandler,   // 函数调用包装 1
    EventHandler    // 函数调用包装 2
  ],
  "事件类型 2": [
    EventHandler,   // 函数调用包装 1
    EventHandler    // 函数调用包装 2
  ]
}
```

事件类型名即为组件的属性名，值为 EventHandler 数组，每个 EventHandler 都是一个函数的封装(以下简称 handler)。

系统在检测到该组件上对应的事件类型触发时，会依次尝试执行数组中的 handler，根据每个 handler 内的 condition 字段结果(如果没有提供该字段，则按照 condition 结果为 true 处理)来决定是否执行该 handler，如果 condition 结果为 false，则跳过该 handler，继续尝试执行下一个，直到数组遍历完成。

每个组件上可注册不同类型的事件监听，但仅能注册该组件类型支持的事件类型，所有事件类型及其适用的组件类型请参考[事件监听](#4213-通用事件)表格。

每个事件监听绑定的 EventHandler 数组内的所有 handler 都可以访问该事件的上下文数据，上下文数据即为事件发生时的系统回调数据，如 `onClick` 事件发生时，系统会自动注入携带用户点击坐标的数据对象，handler 内就可通过 $context.eventData.x/y 来访问坐标信息。具体可参考[事件上下文](#352-事件上下文)章节。

EventHandler 是函数调用的一层封装，可以通过 as 关键字将函数的返回值声明为当前事件监听作用域内可用的局部变量，其可在当前事件范围内后续执行的 handler 内被使用，具体可参考[变量系统](#42224-局部变量)。

**详细规格与约束**：

1. 一个组件可支持多种不同类型的事件监听注册；
2. 同一个组件上注册多个同一种类型的事件监听，仅会生效最后一个；
3. 组件只能使用适用于自身组件类型的事件监听，注册不适用的类型时不生效；
4. 注册的事件监听必须包含有效的 EventHandler 数组，当数组为空，或数组内部所有 handler 均无效时，则不注册该事件；
5. 当对应事件发生时，数组内的 EventHandler 会被依次尝试执行，并根据其内的 condition 字段求值结果是否为 true，决定是否跳过；
6. 当 EventHandler 未提供 condition 字段时，则按照 condition 为 true 处理，执行该 handler；
7. 当 EventHandler 包装的函数没有返回值时，通过 as 声明变量会失效；
8. EventHandler 不与具体的事件类型绑定；
9. EventHandler 不支持用于事件监听之外的地方；
10. EventHandler 不可用于组件属性和样式求值；



#### 3.5.1 EventHandler 数据结构

每个EventHandler是一个对象，包含以下字段：

| 字段 | 必选 | 说明 |
|------|------|------|
| `call` | 是 | 调用函数名，预定义函数及扩展函数均可，具体可参考[扩展函数](#341-函数总表)。 |
| `args` | 否 | 执行函数时的参数，参数类型遵循 call 所指定的函数定义，其中可以使用表达式。见下方 args 值类型说明 |
| `as` | 否 | 将返回值绑定为局部变量名，后续 EventHandler 可通过 `$变量名` 引用。作用域覆盖当前事件的 EventHandler 链，事件完成后自动释放。 |
| `condition` | 否 | 执行条件（表达式字符串）。求值为 `true` 时执行；求值为 `false` 或 `undefined` 时跳过，继续执行下一个；无 `condition` 字段时默认执行 |

**args 值类型说明**

`args` 的参数值可以是：

1. 静态值（字面量）
2. 表达式字符串（`{{ ... }}`）
3. 嵌套对象（对象字段值可以是静态值或表达式字符串）

```json
{
  "args": {
    "url": "{{ '/api/users/' + $__dataModel.user.id }}",
    "method": "POST",
    "body": {
      "name": "{{ $__dataModel.formData.name }}",
      "email": "{{ $__dataModel.formData.email }}",
      "timestamp": "{{ $__dataModel.timestamp }}"
    }
  }
}
```

#### 3.5.2 事件上下文

每个事件触发时，框架自动注入该事件的上下文信息，可在 EventHandler 的表达式（如 `condition`、`args`）中通过 `$context` 引用：

| 属性 | 类型 | 说明 |
| ---------------------- | ------ | ------------------------------------------ |
| `$context.componentId` | string | 当前事件的组件 ID |
| `$context.eventData` | any | 事件相关数据，具体结构因事件类型和组件而异 |

各事件的具体 eventData 类型参见[通用事件](#4213-通用事件)。


```json
{
  "id": "like-btn",
  "component": "Button",
  "label": "点赞",
  "onClick": [
    {
      "call": "handleLike",
      "condition": "{{ $context.eventData.x > 0 }}",
      "args": {
        "componentId": "{{ $context.componentId }}",
        "x": "{{ $context.eventData.x }}",
        "y": "{{ $context.eventData.y }}"
      },
      "as": "result"
    },
    {
      "call": "showToast",
      "condition": "{{ $result.success }}",
      "args": {
        "message": "点赞成功"
      }
    }
  ]
}
```

变量查找优先级等详细规则参见[变量作用域](#42226-作用域与冲突解决)。

### 3.6 表达式与变量系统

本协议通过表达式系统为扩展组件提供动态数据计算能力。表达式以 `"{{...}}"` 形式嵌入属性值中，通过引用变量实现数据绑定、条件判断和响应式更新。变量系统按作用域提供 DataModel 变量及局部变量，配合表达式的响应式机制，当变量值变化时自动驱动 UI 更新。详细语法规范见 [§4.2.2 公共能力](#422-公共能力)附录。

#### 3.6.1 表达式

表达式仅在扩展组件中生效，且须遵循以下约束：

1. 表达式仅适用于扩展组件。
2. 表达式仅在 updateComponents 消息中生效，其他消息类型不支持。
3. A2UI 原生数据绑定的 path 属性（如 `{"content": {"path": "/user/name"}}`）为字面量 JSON Pointer 路径，不支持表达式。
5. 组件的 component 和 id 属性不支持表达式。
6. EventHandler 中的 call 和 as 字段为标识符引用（函数名与变量绑定名），不支持表达式。
7. 表达式仅可用于 JSON 值（value）位置，不可用于键（key）位置。
8. 组件的各属性是否支持表达式，以其所属 catalog 中的 JSON Schema 定义为准；支持表达式的属性在 Schema 中声明为 `Expression` 类型的联合类型。
9. 表达式字符串总长度不超过 2048 字符，括号嵌套深度不超过 20 层（参见 [§4.2.2.1.1](#42211-基本语法) 安全约束）。

当表达式用于组件属性和样式，当引用的变量值发生变化时，表达式会自动重新求值并更新对应的组件属性和样式属性（响应式更新机制详见 [§4.2.2.2.7 响应式更新](#42227-响应式更新)）。

**语法速览**

| 能力 | 语法 | 示例 |
|------|------|------|
| 字符串字面量 | 单引号 | `'hello'` |
| 算术运算 | `+` `-` `*` `/` `%` | `$price * $count` |
| 比较运算 | `==` `!=` `>` `>=` `<` `<=` | `$age >= 18` |
| 逻辑运算 | `&&` `\|\|` `!` | `$a && !$b` |
| 三元条件 | `? :` | `$flag ? 'yes' : 'no'` |
| 内置函数 | `size()` | `size($items)` |
| 成员访问 | `.` `[]` | `$item.name`、`$items[0]` |

完整语法规范（数据类型、运算符优先级、类型转换规则、EBNF 文法）见 [§4.2.2.1 表达式](#4221-表达式)。

典型使用场景：

**组件属性值采用表达式计算**

```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "main",
    "components": [
      {
        "id": "greeting",
        "component": "Text",
        "content": "{{ 'Hello, ' + $__dataModel.name + '!' }}"  // 表达式拼接 DataModel 变量与字符串字面量
      }
    ]
  }
}
```

**使用表达式设定 EventHandler 条件和函数参数值**

```json
// as 绑定（推荐）
{
  "call": "submitForm",
  "condition": "{{ $confirmResult == 0 }}",  // 条件表达式，引用行为链变量
  "args": {
    "path": "{{'/items/' + $index }}",  // 函数参数使用表达式动态拼接路径
    "value": ""
  }
}
```

**使用表达式表示组件的样式**

```json
{
  "id": "submit-btn",
  "component": "Button",
  "label": "提交",
  "styles": {
    "fontColor":"#33182431",
    "fontSize": "{{ $__dataModel.fontSize }}",  // 样式属性使用表达式绑定 DataModel 变量
    "other prop":"value"
  }
}
```

#### 3.6.2 变量系统

变量仅使用在表达式中，按作用域分为以下几类，求值计算时遵循就近优先原则：

| 类别 | 前缀/语法 | 作用域 | 响应式 |
|------|-----------|--------|--------|
| DataModel 变量 | `$__dataModel.xxx` | surface 级 | 是 |
| 循环变量（`$item`、`$index`） | `$` | [子组件模板内](#37-子组件模板生成) | 否 |
| 行为链变量（`as` 绑定） | `$varName` | 当前事件行为链 | 否 |
| 事件上下文 | `$context` | 当前事件行为链 | 否 |

**变量引用示例：**

* `{{ $__dataModel.user.name }}` — DataModel 绝对路径
* `{{ $item.price * $item.count }}` — 循环变量运算
* `{{ $context.eventData }}` — 事件上下文

变量引用语法、作用域冲突解决规则及各类变量的详细说明参见 [§4.2.2.2 变量系统](#4222-变量系统)。

### 3.7 子组件模板生成

本协议支持容器组件通过**模板机制**根据数据数组动态生成子组件。当容器组件的 `children` 属性从子组件 ID 列表改为 `{ componentId, path }` 对象形式时，客户端对 `path` 所指数组进行迭代，为每个数组项实例化 `componentId` 指定的模板组件。

#### 3.7.1 机制概述

**触发条件**：容器组件的 `children` 属性值为对象（而非字符串数组）时进入模板模式：

```json
{
  "id": "employee_list",
  "component": "List",
  "children": {
    "path": "/employees",
    "componentId": "employee_card"
  }
}
```

**工作流程**：

1. 客户端根据 `path`（JSON Pointer）从 DataModel 中获取数组数据。
2. 为数组中的每个元素实例化一个 `componentId` 指定的组件。
3. 实例化的组件可通过 `$item.fieldName` 引用当前迭代项的字段（相对路径），也可通过 `$__dataModel.xxx` 引用全局数据（绝对路径）。

**模板模式与静态模式的区别**：

| 属性值形式 | 模式 | 说明 |
|------------|------|------|
| `["id1", "id2", ...]` | 静态模式 | 固定引用已定义的子组件 |
| `{ "path": "/xxx", "componentId": "tpl" }` | 模板模式 | 根据数据数组动态生成子组件 |

#### 3.7.2 支持模板的组件

以下容器组件支持模板生成机制：

| 组件 | 类型 | 说明 |
|------|------|------|
| Row | 布局组件 | 水平方向排列子组件 |
| Column | 布局组件 | 垂直方向排列子组件 |
| List | 布局组件 | 高效滚动列表 |

> 各组件的完整属性定义（包括 `children` 的详细类型说明）参见 [§4.2.1.6 布局组件](#4216-布局组件)。

#### 3.7.3 循环变量与自定义

模板模式下，每个实例化的组件可使用以下循环变量：

| 变量 | 类型 | 说明 |
|------|------|------|
| `$index` | number | 当前项的索引（从 0 开始） |
| `$item` | any | 当前迭代项的数据对象，通过 `.fieldName` 访问字段 |

**基本用法**：

```json
{
  "id": "employee_list",
  "component": "List",
  "children": { "path": "/employees", "componentId": "employee_card" }
},
{
  "id": "employee_card",
  "component": "Column",
  "children": ["name_text", "role_text"]
},
{
  "id": "name_text",
  "component": "Text",
  "content": "{{ $item.name }}"
},
{
  "id": "role_text",
  "component": "Text",
  "content": "{{ $item.role }}"
}
```

**自定义循环变量名**：通过 `indexVar` 和 `itemVar` 属性可将默认的 `$index`/`$item` 替换为自定义名称：

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `indexVar` | string | `"index"` | 自定义索引变量名（使用时加 `$` 前缀） |
| `itemVar` | string | `"item"` | 自定义项数据变量名（使用时加 `$` 前缀） |

```json
{
  "component": "List",
  "children": {
    "path": "/products",
    "componentId": "product_card",
    "indexVar": "i",
    "itemVar": "product"
  }
},
{
  "id": "product_card",
  "component": "Text",
  "content": "{{ ($i + 1) + '. ' + $product.name }}"
}
```

#### 3.7.4 嵌套模板

模板支持嵌套：外层模板的自定义循环变量可在内层模板中访问。

```json
{
  "component": "List",
  "children": {
    "path": "/departments",
    "componentId": "dept_tpl",
    "itemVar": "dept"
  }
},
{
  "id": "dept_tpl",
  "component": "Column",
  "children": [
    { "component": "Text", "content": "{{ $dept.name }}" },
    {
      "component": "List",
      "children": {
        "path": "members",
        "componentId": "member_tpl"
      }
    }
  ]
},
{
  "id": "member_tpl",
  "component": "Text",
  "content": "{{ $dept.name + ' - ' + $item.name }}"
}
```

上例中 `member_tpl` 同时引用了外层自定义变量 `$dept` 和内层默认变量 `$item`。

**注意**：内层默认的 `$item`/`$index` 会遮蔽外层同名变量。如需在内层访问外层项数据，应通过 `itemVar` 为外层指定不同的变量名。


#### 3.7.5 综合示例

以下示例展示完整的协议消息，包括 DataModel 定义、模板组件树结构和表达式绑定：

**第一步：发送 DataModel**：

```json
{
  "version": "v0.9",
  "updateDataModel": {
    "surfaceId": "main",
    "path": "/",
    "value": {
      "company": "Acme Corp",
      "teams": [
        {
          "name": "Engineering",
          "lead": "Alice",
          "members": [
            { "name": "Bob", "role": "Backend" },
            { "name": "Carol", "role": "Frontend" }
          ]
        },
        {
          "name": "Design",
          "lead": "Dave",
          "members": [
            { "name": "Eve", "role": "UI" }
          ]
        }
      ]
    }
  }
}
```

**第二步：发送组件定义**：

```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "main",
    "components": [
      {
        "id": "team_list",
        "component": "List",
        "children": {
          "path": "/teams",
          "componentId": "team_card",
          "itemVar": "team"
        }
      },
      {
        "id": "team_card",
        "component": "Column",
        "children": ["team_title", "company_label", "member_list"]
      },
      {
        "id": "team_title",
        "component": "Text",
        "content": "{{ $team.name + ' (Lead: ' + $team.lead + ')' }}"
      },
      {
        "id": "company_label",
        "component": "Text",
        "content": "{{ $__dataModel.company }}"
      },
      {
        "id": "member_list",
        "component": "List",
        "children": {
          "path": "members",
          "componentId": "member_row"
        }
      },
      {
        "id": "member_row",
        "component": "Text",
        "content": "{{ $item.name + ' - ' + $item.role }}"
      }
    ]
  }
}
```

要点说明：

* `team_card` 通过 `$team.name`（自定义 itemVar）引用外层迭代项，通过 `$__dataModel.company` 引用全局数据。
* 嵌套的 `member_row` 使用默认 `$item` 引用内层迭代数据（`members` 数组的每个元素）。
* 内层模板的 `path: "members"` 为相对路径，解析为 `/teams/N/members`。

循环变量与变量作用域的详细规范参见 [§4.2.2.2.4 局部变量](#42224-局部变量)。DataModel 变量的路径解析规则参见 [§4.2.2.2.3 DataModel 变量](#42223-datamodel-变量)。

## 4 附录

### 4.2 扩展协议

#### 4.2.1 组件

##### 4.2.1.1 通用属性

组件如无特殊说明均支持以下通用属性：

1. id： 必选，surface范围内唯一的组件ID

2. component：必选，组件类型名

3. accessibility：可选，无障碍属性

 

##### 4.2.1.2 通用样式

组件如无特殊说明则均支持以下通用样式：

| 名称 | 样式说明 | 类型 | 必选 | 支持表达式 | 使用示例 |
|------|----------|------|------|------|----------|
| backgroundImageSizeWithStyle | 设置组件背景图片的宽度和高度。 | 字符串枚举值或对象，默认值为"auto"。<br>字符串枚举值：<br>"cover":保持宽高比进行缩小或者放大，使得图片两边都大于或等于显示边界<br>"contain":保持宽高比进行缩小或者放大，使得图片完全显示在显示边界内<br>"auto":保持原图的比例不变<br>"fill":不保持宽高比进行放大缩小，使得图片充满显示边界<br><br>对象：{width， height}，两个属性都是必选，类型为数值或者字符串。<br>数值：[0,inf)<br>默认单位vp<br>字符串：<br>数值+单位（"100fp"）<br>单位："fp"、"vp"、"%" | 否 | 是 | "backgroundImageSizeWithStyle": "contain" |
| flexShrink | 控制子组件在父组件主轴方向上空间不足时的压缩比例的属性。当 Flex 容器在主轴方向上的空间不足以容纳所有子组件时，设置了flexShrink的子组件会根据其值按比例被压缩，以适应容器空间。 | 数值，范围[0, 1]，默认值：1 | 否 | 是 | "flexShrink": 1 |
| width | 设置组件宽度 | 数值：[0,inf)<br>默认单位vp<br><br>字符串：<br>数值+单位（"100fp"）<br>单位："fp"、"vp"、"%"<br><br>枚举值：<br>"matchParent"：当前组件自适应父组件布局时，其大小与父组件内容区相等，不包括padding和border<br>"wrapContent"：当前组件自适应子组件（内容）时，其大小与子组件（内容）相等，并且其大小受父组件内容区大小约束<br>"fixAtIdealSize"：当前组件自适应子组件（内容）时，其大小与子组件（内容）相等，并且其大小不受父组件内容区大小约束 | 否 | 是 | "width": 100 |
| height | 设置组件高度 | 数值：[0,inf)<br>默认单位vp<br>字符串：<br>数值+单位（"100fp"）<br>单位："fp"、"vp"、"%"<br>枚举值：<br>"matchParent"：当前组件自适应父组件布局时，其大小与父组件内容区相等，不包括padding和border<br>"wrapContent"：当前组件自适应子组件（内容）时，其大小与子组件（内容）相等，并且其大小受父组件内容区大小约束<br>"fixAtIdealSize"：当前组件自适应子组件（内容）时，其大小与子组件（内容）相等，并且其大小不受父组件内容区大小约束 | 否 | 是 | "height": "100vp" |
| constraintSize | 设置约束尺寸，组件布局时，进行尺寸范围限制。 | 对象：{minWidth, maxWidth, minHeight, maxHeight}，四个属性分别是宽度和高度的最大最小值，都是必选，类型为数值或者字符串。<br>数值：[0,inf)<br>默认单位vp<br>字符串：<br>数值+单位（"100fp"）<br>单位："fp"、"vp"、"%" | 否 | 否 | "constraintSize": { "minWidth": 10, "maxWidth": 100, "minHeight": 10, "maxHeight": 100 } |
| backgroundImage | 设置组件的背景图片路径 | 字符串，本地图片路径。不支持网络 URL。 | 否 | 是 | "backgroundImage": "/resources/bg.png" |
| margin | 外间距，支持数字（统一边距）或对象{top, right, bottom, left}（分别设置四边） | 数值：[0,inf)<br>默认单位vp<br>对象：四个属性都是可选，类型为数值或者字符串。<br>数值：[0,inf)<br>默认单位vp<br>字符串：<br>数值+单位（"100fp"）<br>单位："fp"、"vp"、"%" | 否 | 是 | "margin": { "left": 4, "top": "4vp", "right": "4%" } |
| borderRadius | 4边角半径，支持数字（统一半径）或对象{topLeft, topRight, bottomLeft, bottomRight}（分别设置四角） | 数值：[0,inf)<br>默认单位vp<br>对象：四个属性都是可选，类型为数值或者字符串。<br>数值：[0,inf)<br>默认单位vp<br>字符串：<br>数值+单位（"100fp"）<br>单位："fp"、"vp"、"%" | 否 | 是 | "borderRadius": 8 |
| visibility | 是否可见 | 枚举值字符串，<br>"visible"：可见<br>"hidden"：不可见但占位<br>"none"：不可见也不占位 | 否 | 是 | "visibility": "visible" |
| clip | 是否根据父组件边界进行裁切，true/false | 布尔值，默认值：false | 否 | 是 | "clip": true |
| backgroundColor | 颜色值，0xARGB 格式的16进制表示 | 字符串 | 否 | 是 | "backgroundColor": "#00FF0000" |
| borderWidth | 边框宽度，支持数值/字符串 | 数值：[0,inf)<br>默认单位vp<br>字符串：<br>数值+单位（"100fp"）<br>单位："fp"、"vp"、"%" | 否 | 是 | "borderWidth": 1 |
| borderColor | 边框颜色，0xARGB 格式的16进制表示 | 字符串 | 否 | 是 | "borderColor": "#00000000" |
| padding | 内边距，支持数字（统一边距）或对象（分别设置四边） | 数值：[0,inf)<br>默认单位vp<br>对象：四个属性都是可选，类型为数值或者字符串。<br>数值：[0,inf)<br>默认单位vp<br>字符串：<br>数值+单位（"100fp"）<br>单位："fp"、"vp"、"%" | 否 | 是 | "padding": { "left": 8, "top": "8vp", "right": "8%" } |
| layoutWeight | 布局权重，仅当父节点为Row和Column时生效 | 数值，默认值为1 | 否 | 是 | "layoutWeight": 2 |
| shadow | 阴影效果，对象或者字符串枚举值 | 对象 { offsetX, offsetY, radius, color, fill, type};<br>offsetX:可选，数值，阴影的X轴偏移量。默认值：0，单位：vp<br><br>offsetY:可选，数值，阴影的Y轴偏移量。默认值：0，单位：vp<br><br>radius:必选，数值，阴影模糊半径。取值范围：[0, +∞)。单位：vp。设置小于0的值时，按值为0处理。<br><br>color:可选，16进制字符串，阴影的颜色。默认为黑色。<br><br>fill:可选，布尔，阴影是否内部填充。true表示阴影在内部填充，false表示阴影在外部填充。默认值：false。<br><br>type:可选,字符串枚举值，阴影类型。默认值："color"。<br>"color":颜色<br>"blur":模糊<br><br>字符串枚举值：<br>"outerDefaultXS":超小阴影<br>"outerDefaultSM":小阴影<br>"outerDefaultMD":中阴影<br>"outerDefaultLG":大阴影<br>"outerFloatingSM":浮动小阴影<br>"outerFloatingMD":浮动中阴影。 | 否 | 否 | "shadow": { "offsetX": 2, "offsetY": 2, "radius": 4, "color": "#66000000" } |
| linearGradient | 线性渐变 | 对象 {angle, direction, colors, repeating}<br>angle:可选，数值，线性渐变的起始角度；默认值：180<br>direction:可选，枚举字符串（Left, Top, Right, Bottom, LeftTop, LeftBottom, RightTop, RightBottom, None），线性渐变的方向；默认值：None<br>colors:必选，数组 Array&lt;[ResourceColor, number]&gt;，指定渐变色颜色和其对应的百分比位置的数组；默认值：[]，无渐变效果<br>repeating:可选，布尔值，为渐变的颜色重复着色；默认值：false | 否 | 否 | "linearGradient": { "angle": 90, "colors": [["#ff0000", 0.0], ["#0000ff", 0.3], ["#ffff00", 1.0]], "repeating": true } |

##### 4.2.1.3 通用事件

组件如无特殊说明则均支持以下通用事件：


| 事件类型 | 适用组件 | 触发条件 | 事件上下文数据 | 数据说明 | 上下文数据示例 |
|----------|----------|----------|----------------|----------|----------------|
| onClick | 所有组件 | 用户点击组件 | `{ x: number, y: number }` | x/y 为点击位置相对于组件的坐标，单位 vp | `{ "x": 120, "y": 340 }` |

##### 4.2.1.4 展示组件

###### Text

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 支持表达式 | 说明 |
|------|------|------|------|------|------|------|------|
| Text | 展示组件 | 用于显示普通文本内容，支持字体、颜色、样式等设置。 | content | string，默认值：'' | 是 | 是 | 要显示的文本内容 |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| textOverflow | 文本超长时的显示方式，需配合maxLines使用 | 字符串枚举值，默认值：clip<br>"none"：文本超长时按最大行截断显示<br>"clip"：文本超长时按最大行截断显示<br>"ellipsis"：文本超长时显示不下的文本用省略号代替<br>"marquee"：文本在一行内滚动显示 | 否 | 是 | "textOverflow": "ellipsis" |
| decoration | 设置文本装饰线样式及其颜色 | 对象 { type, style, color, thicknessScale }，默认值：{type: none, color: black, style: solid, thicknessScale: 1.0}<br>type：装饰线类型，字符串枚举值("none":不使用文本装饰线,"underline":文字下划线修饰,"overline":文字上划线修饰,"lineThrough":穿过文本的修饰线)<br>color:装饰线颜色,字符串类型（16进制）<br>style:装饰线样式,字符串枚举值("solid":单实线,默认值,"double":双实线,"dotted":点线,"dashed":虚线,"wavy":波浪线)<br>thicknessScale:装饰线粗细，数字类型 | 否 | 否 | "decoration": { "type": "underline", "color": "#ff007dff", "style": "solid" } |
| fontSize | 设置字体大小，默认16 fp | 数字，单位为fp，默认值：16fp | 否 | 是 | "fontSize": 18 |
| fontWeight | 文本的字体粗细 | 数字，取值范围：[100, 900]，取值间隔为100，默认值：400 | 否 | 是 | "fontWeight": 400 |
| fontColor | 字体颜色 | 字符串（16进制） | 否 | 是 | "fontColor": "#333333" |
| textAlign | 水平对齐方式 | 字符串枚举值，默认值：start<br>("start":水平对齐首部,"center":水平居中对齐,"end":水平对齐尾部,"justify": 双端对齐) | 否 | 是 | "textAlign": "center" |
| maxLines | 文本最大行数 | 数字，默认值：inf。取值范围：[0, inf]。当不设置或设置非法值时，不限制最大行数。 | 否 | 是 | "maxLines": 2 |
| wordBreak | 文本断行规则 | 字符串枚举值，默认值：breakWord<br>"normal"：CJK(中文、日文、韩文)文本可以在任意2个字符间断行，而Non-CJK文本（如英文等）只能在空白符处断行。"breakAll"：对于Non-CJK的文本，可在任意2个字符间断行。对于CJK文本，效果与NORMAL一致。<br>"breakWord"：与breakAll相同，对于Non-CJK的文本可在任意2个字符间断行，一行文本中有断行破发点（如空白符）时，优先按破发点换行，保障单词优先完整显示。若整一行文本均无断行破发点，则在任意2个字符间断行。对于CJK文本，效果与normal一致。"hyphenation"：每行末尾单词尝试通过连字符"-"进行断行，若无法添加连字符"-"，则跟breakWord保持一致。 | 否 | 是 | "wordBreak": "breakWord" |
| maxFontSize | 文本最大显示大小 | 数字，单位 fp。需配合minFontSize以及maxLines或布局大小限制使用，单独设置不生效。maxFontSize小于等于0或者maxFontSize小于minFontSize时，自适应字号不生效，此时按照fontSize属性的值生效，未设置时按照其默认值生效。 | 否 | 是 | "maxFontSize": 24 |
| minFontSize | 文本最小显示大小 | 数字，单位 fp。需配合maxFontSize以及maxLines或布局大小限制使用，单独设置不生效。minFontSize小于或等于0时，自适应字号不生效，此时按照fontSize属性的值生效，未设置时按照其默认值生效。 | 否 | 是 | "minFontSize": 12 |

**事件**

支持[通用事件](#4213-通用事件)。

###### Image

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 支持表达式 | 说明 |
|------|------|------|------|------|------|------|------|
| Image | 展示组件 | 用于展示图片，支持本地或资源图片。不支持 SVG 格式，不支持网络图片路径。 | src | String | 是 | 是 | 图片数据源（本地资源路径）。不支持 SVG 格式，包括 base64 编码的 SVG（如 data:image/svg+xml;base64,...）。不支持网络 URL。 |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| aspectRatio | 宽高比 (width/height) | 数字，默认值：1.0。指定当前组件的宽高比，aspectRatio=width/height。仅设置width、aspectRatio时，height = width/aspectRatio。<br>仅设置height、aspectRatio时，width = height * aspectRatio。<br>同时设置width、height和aspectRatio时，height不生效，height = width / aspectRatio。<br>设置aspectRatio属性后，组件宽高会受父组件内容区大小限制，constraintSize的优先级高于aspectRatio。 | 否 | 是 | "aspectRatio": 1.5 |
| objectFit | 图片填充效果 | 字符串枚举值，默认值：cover<br>"fill"：不保持宽高比进行放大缩小，使得图片或视频充满显示边界，对齐方式为水平居中<br>"contain"：保持宽高比进行缩小或者放大，使得图片或视频完全显示在显示边界内，对齐方式为水平居中<br>"cover"：保持宽高比进行缩小或者放大，使得图片或视频两边都大于或等于显示边界，对齐方式为水平居中<br>"auto"：图片或视频会根据其自身尺寸和组件的尺寸进行适当缩放，以在保持比例的同时填充视图，对齐方式为水平居中<br>"none"：保持原有尺寸进行显示，对齐方式为水平居中<br>"scaleDown"：保持宽高比进行显示，图片或视频缩小或者保持不变，对齐方式为水平居中<br>"topStart"：图片或视频显示在组件的顶部起始端，且保持原有尺寸<br>"top"：图片或视频显示在组件的顶部横向居中，且保持原有尺寸<br>"topEnd"：图片或视频显示在组件的顶部尾端，且保持原有尺寸。<br>"start"：图片或视频显示在组件的起始端纵向居中，且保持原有尺寸<br>"center"：图片或视频显示在组件的横向和纵向居中，且保持原有尺寸<br>"end"：图片或视频显示在组件的尾端纵向居中，且保持原有尺寸<br>"bottomStart"：图片或视频显示在组件的底部起始端，且保持原有尺寸<br>"bottom"：图片或视频显示在组件的底部横向居中，且保持原有尺寸<br>"bottomEnd"：图片或视频显示在组件的底部尾端，且保持原有尺寸<br>"matrix"：配合imageMatrix使用，使图像在Image组件自定义位置显示，且保持原有尺寸。不支持svg图源 | 否 | 是 | "objectFit": 1 |

**事件**

支持[通用事件](#4213-通用事件)。

###### Divider

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 说明 |
|------|------|------|------|------|------|------|
| Divider | 展示组件 | 分割线组件，用于在视觉上分隔不同内容区域。 | — | — | — | — |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| strokeWidth | 分割线宽度 | 数值或者字符串，默认值：1px。非法值按默认值处理。数值：[0,inf)默认单位vp；字符串：数值+单位（"100px"） | 否 | 是 | "strokeWidth": 1 |
| vertical | 分割线方向 | 布尔值，默认值：false（false:水平; true:垂直） | 否 | 是 | "vertical": false |
| color | 分割线颜色 | 16进制字符串，默认值：浅色模式#33000000，深色模式#33FFFFFF | 否 | 是 | "color": "#E0E0E0" |

**事件**

支持[通用事件](#4213-通用事件)。

###### Progress

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 支持表达式 | 说明 |
|------|------|------|------|------|------|------|------|
| Progress | 展示组件 | 进度条组件，用于显示任务完成进度或加载状态。 | value | number，取值范围：[0, total]，默认值：0 | 否 | 是 | 当前进度值 |
| | | | total | number，取值范围：[0, 2147483647]，total是负数时按照100处理 | 是 | 是 | 进度总长 |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| color | 进度条前景色 | 16进制字符串，默认值：浅色模式#FF0A59F7，深色模式#FF317AF7 | 否 | 是 | "color": "#007AFF" |
| type | 进度条类型 | 字符串枚举值，默认值：linear<br>"linear":线性样式<br>"ring":环形无刻度样式，环形圆环逐渐显示直至完全填充<br>"eclipse":圆形样式，显示类似月圆月缺的进度展示效果，从月牙逐渐变化至满月<br>"scaleRing":环形有刻度样式，显示类似时钟刻度形式的进度展示效果<br>"capsule":胶囊样式，头尾两端圆弧处的进度展示效果与Eclipse相同，中段的进度展示效果与Linear相同。当高度大于宽度时，自适应垂直显示。 | 否 | 是 | "type": "ring" |

**事件**

支持[通用事件](#4213-通用事件)。

##### 4.2.1.5 交互组件

###### Button

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 支持表达式 | 说明 |
|------|------|------|------|------|------|------|------|
| Button | 交互组件 | 按钮组件，响应用户点击操作，常用于触发事件。 | label | string | 是 | 是 | 按钮中的文本 |
| | | | enabled | boolean，默认值：true | 否 | 是 | 按钮是否可点击 |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| fontColor | 设置按钮文本显示颜色 | 16进制字符串 | 否 | 是 | "fontColor": "#FFAAFF" |
| fontSize | 设置字体大小，默认16 fp | 数字，单位为fp | 否 | 是 | "fontSize": 16 |
| fontWeight | 文本的字体粗细 | 数字，默认值：500<br>或枚举值"lighter":100字重，字体较细<br>"normal":400字重，字体粗细正常<br>"regular":400字重，字体粗细正常，与normal效果相同<br>"medium":500字重，字体粗细适中<br>"bold":700字重，字体较粗<br>"bolder":900字重，字体非常粗 | 否 | 是 | "fontWeight": 600 |
| maxFontSize | 文本最大显示大小 | 数字，单位 fp。需配合minFontSize以及maxLines或布局大小限制使用，单独设置不生效。maxFontSize小于等于0或者maxFontSize小于minFontSize时，自适应字号不生效，此时按照fontSize属性的值生效，未设置时按照其默认值生效。 | 否 | 是 | "maxFontSize": 20 |
| minFontSize | 文本最小显示大小 | 数字，单位 fp。需配合maxFontSize或布局大小限制使用，单独设置不生效。minFontSize小于或等于0时，自适应字号不生效，此时按照fontSize属性的值生效，未设置时按照其默认值生效。 | 否 | 是 | "minFontSize": 12 |

**事件**

支持[通用事件](#4213-通用事件)。

###### Checkbox

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 支持表达式 | 说明 |
|------|------|------|------|------|------|------|------|
| Checkbox | 交互组件 | 提供多选框组件，通常用于某选项的打开或关闭。 | label | string，默认值：空字符串 | 否 | 是 | 设置复选框旁的显示文本，支持任意字符串。 |
| | | | value | string，默认值：空字符串 | 否 | 是 | 当前多选框的标识，不绘制显示。可用于在所属 group 中区分不同选项。 |
| | | | group | string，默认值：空字符串 | 否 | 是 | 用于指定多选框所属群组的名称。 |
| | | | select | boolean，默认值：false | 否 | 是 | 设置多选框选中状态。true：多选框被选中，false：多选框未选中 |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| selectedColor | 设置多选框选中状态颜色。 | 16进制字符串 | 否 | 是 | "selectedColor": "#FFAAFF" |
| unSelectedColor | 设置多选框非选中状态颜色。 | 16进制字符串 | 否 | 是 | "unSelectedColor": "#FFAAFF" |
| mark | 设置多选框内部图标的样式。 | 对象{ strokeColor, size, strokeWidth }<br>三个属性都是可选。<br>strokeColor: 16进制字符串，内部图标颜色<br>size: 数值，内部图标大小，单位vp，默认大小与多选框组件宽度相同。<br>strokeWidth：数值，内部图标粗细，单位vp。 | 否 | 否 | "mark": {<br>"strokeColor": "#FFABCD", "size": 20, "strokeWidth": 2 } |
| shape | 设置Checkbox组件形状，包括圆形和圆角方形。 | 字符串枚举值，默认值：circle<br>"circle": 圆形<br>"rounded_square": 圆角方形 | 否 | 是 | "shape": "circle" |

**事件**

支持[通用事件](#4213-通用事件)，并支持以下组件私有事件：

| 事件类型 | 触发条件 | 事件上下文数据 | 数据说明 | 上下文数据示例 |
|----------|----------|----------------|----------|----------------|

##### 4.2.1.6 布局组件

以下组件支持通过 `children` 属性的模板模式动态生成子组件，模板机制概述参见 [§3.7 子组件模板生成](#37-子组件模板生成)。

###### Row

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 支持表达式 | 说明 |
|------|------|------|------|------|------|------|------|
| Row | 布局组件 | 水平方向线性布局，将子组件沿水平方向排列。 | children | List[String] 或者 object { componentId: string, path: string } | 否 | 否 | 子组件ID列表 或者 模板组件ID和循环数据路径 |
| | | | itemMargin | number，默认值：16vp | 否 | 是 | 横向布局元素水平方向间距。itemMargin为负数或者justifyContent设置为"spaceBetween"、"spaceAround"、"spaceEvenly"时，itemMargin不生效。非法值：按默认值处理。单位：vp |
| | | | wrap | 字符串枚举值，默认值：noWrap<br>"noWrap"：以单行布局，子元素尽可能约束在容器内。<br>"wrap"：以多行布局，子项允许超出容器并换行。 | 否 | 是 | 单行还是多行排列 |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| justifyContent | 水平方向对齐格式 | 字符串枚举值，默认值：start<br>"start"：元素在主轴方向首端对齐，第一个元素与行首对齐，后续元素与前一个对齐<br>"center"：元素在主轴方向中心对齐，第一个元素与行首的距离和最后一个元素与行尾的距离相同<br>"end"：元素在主轴方向尾部对齐，最后一个元素与行尾对齐，其余元素与后一个对齐<br>"spaceBetween"：Flex主轴方向均匀分配弹性元素，相邻元素之间距离相同。第一个元素与行首对齐，最后一个元素与行尾对齐<br>"spaceAround"：Flex主轴方向均匀分配弹性元素，相邻元素之间距离相同。第一个元素到行首的距离和最后一个元素到行尾的距离是相邻元素之间距离的一半<br>"spaceEvenly"：Flex主轴方向均匀分配弹性元素，相邻元素之间的距离、第一个元素与行首的间距、最后一个元素到行尾的间距均相同 | 否 | 是 | "justifyContent": "spaceBetween" |
| alignItems | 垂直方向对齐格式 | 字符串枚举值，默认值：center<br>"top"：顶部对齐<br>"center"：居中对齐<br>"bottom"：底部对齐 | 否 | 是 | "alignItems": "center" |

**事件**

支持[通用事件](#4213-通用事件)。

###### Column

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 支持表达式 | 说明 |
|------|------|------|------|------|------|------|------|
| Column | 布局组件 | 垂直方向线性布局，将子组件沿垂直方向排列。 | children | List[String] 或者 object { componentId: string, path: string } | 否 | 否 | 子组件ID列表 或者 模板组件ID和循环数据路径 |
| | | | itemMargin | number，默认值：8vp | 否 | 是 | 纵向布局元素垂直方向间距。itemMargin为负数或者justifyContent设置为"spaceBetween"、"spaceAround"、"spaceEvenly"时，itemMargin不生效。非法值：按默认值处理。单位：vp |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| justifyContent | 垂直方向对齐格式 | 字符串枚举值，默认值：start<br>"start"：元素在主轴方向首端对齐，第一个元素与行首对齐，后续元素与前一个对齐<br>"center"：元素在主轴方向中心对齐，第一个元素与行首的距离和最后一个元素与行尾的距离相同<br>"end"：元素在主轴方向尾部对齐，最后一个元素与行尾对齐，其余元素与后一个对齐<br>"spaceBetween"：Flex主轴方向均匀分配弹性元素，相邻元素之间距离相同。第一个元素与行首对齐，最后一个元素与行尾对齐<br>"spaceAround"：Flex主轴方向均匀分配弹性元素，相邻元素之间距离相同。第一个元素到行首的距离和最后一个元素到行尾的距离是相邻元素之间距离的一半<br>"spaceEvenly"：Flex主轴方向均匀分配弹性元素，相邻元素之间的距离、第一个元素与行首的间距、最后一个元素到行尾的间距均相同 | 否 | 是 | "justifyContent": "spaceBetween" |
| alignItems | 水平方向对齐格式 | 字符串枚举值，默认值：start<br>"start"：起始端对齐<br>"center"：居中对齐<br>"end"：尾端对齐。 | 否 | 是 | "alignItems": "center" |

**事件**

支持[通用事件](#4213-通用事件)。

###### List

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 支持表达式 | 说明 |
|------|------|------|------|------|------|------|------|
| List | 布局组件 | 列表组件，高效展示滚动列表项，支持大量数据。 | children | List[String]或object { componentId: string, path: string } | 否 | 否 | 子节点的ID列表或者模板组件ID和循环数据路径。 |
| | | | space | Number，默认值：0 | 否 | 是 | 子组件主轴方向的间隔。参数类型为number时单位为vp。设置为负数或者大于等于List内容区长度时，按默认值显示。space参数值小于List分割线宽度时，子组件主轴方向的间隔取分割线宽度。List子组件的visibility属性设置为None时不显示，但该子组件上下的space还是会生效。 |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| listDirection | 列表排列方向 | 字符串枚举值，默认值：vertical<br>"vertical":方向为纵向<br>"horizontal":方向为横向 | 否 | 是 | "listDirection": "vertical" |
| scrollBar | 滚动条状态 | 字符串枚举值，默认值：auto<br>"off"：不显示<br>"auto"：按需显示(触摸时显示，2s后消失)<br>"on"：常驻显示 | 否 | 是 | "scrollBar": "auto" |
| nestedScroll | 嵌套滚动模式 | 字符串枚举值，默认值：{scrollForward: selfOnly, scrollBackward: selfOnly}<br>"scrollForward"：滚动组件往末尾端滚动时的嵌套滚动选项<br>"scrollBackward"：滚动组件往起始端滚动时的嵌套滚动选项 | 否 | 是 | "nestedScroll": "scrollForward" |

**事件**

支持[通用事件](#4213-通用事件)，并支持以下组件私有事件：

| 事件类型 | 触发条件 | 事件上下文数据 | 数据说明 | 上下文数据示例 |
|----------|----------|----------------|----------|----------------|

###### Stack

**属性**

| 名称 | 类型 | 说明 | 属性 | 类型 | 必选 | 支持表达式 | 说明 |
|------|------|------|------|------|------|------|------|
| Stack | 布局组件 | 堆叠布局，子组件按顺序叠放，后添加的在上层。 | children | List[String] | 否 | 否 | 子组件ID列表 |

**样式**

| 样式名称 | 样式说明 | 样式类型 | 必选 | 支持表达式 | 使用示例 |
|----------|----------|----------|------|------|----------|
| alignContent | 子组件对齐方式 | 字符串枚举值，默认值：center<br>"topStart"：顶部起始端<br>"top"：顶部横向居中<br>"topEnd"：顶部尾端<br>"start"：起始端纵向居中<br>"center"：横向和纵向居中<br>"end"：尾端纵向居中<br>"bottomStart"：底部起始端<br>"bottom"：底部横向居中<br>"bottomEnd"：底部尾端 | 否 | 是 | "alignContent": "center" |

**事件**

支持[通用事件](#4213-通用事件)。



#### 4.2.2 公共能力

##### 4.2.2.1 表达式

###### 4.2.2.1.1 基本语法

表达式统一采用 `"{{` 和 `}}"` 包裹（定义见 [§3.6.1 表达式](#361-表达式)）。

**语法规则：**

* 表达式必须以 `"{{` 开始，以 `}}"` 结束
* 每个 `"{{ }}"` 对包含且仅包含一个完整的表达式
* 不支持嵌套表达式
* 不支持在一对双引号中使用多个表达式

**正确写法：**

```json
{
  "content": "{{ $firstName + ' ' + $lastName }}"  // 正确：完整的单个表达式
}
```

**错误示例（表达式完整性要求）：**

```json
{
  "content": "{{ '123' }} + {{ $__dataModel.count }}"  // 错误：多个独立表达式
  "content": "{{ $firstName }} {{ $lastName }}"        // 错误：包含多个表达式
}
```

**限制说明：**

* ❌ "{{ inner {{ nested }} }}" - 不允许嵌套
* ❌ "{{ $firstName }} and {{ $lastName }}" - 不允许包含多个表达式
* ❌ "{{ '123' }} + {{ $__dataModel.count }}" - 不允许多个表达式拼接
* ✅ "{{ $firstName + ' and ' + $lastName }}" - 使用字符串连接形成单个完整表达式
* ✅ "{{ '123' + $__dataModel.count }}" - 在一个表达式内完成所有计算

**安全约束：**

| 约束 | 上限值 | 超限行为 |
|------|--------|----------|
| 表达式字符串总长度 | 2048 字符 | 求值失败，返回 `""` |
| 括号嵌套最大深度 | 20 层 | 求值失败，返回 `""` |

###### 4.2.2.1.2 数据类型

| 类型 | 说明 | 示例 |
|------|------|------|
| string | 字符串（支持单引号） | 'hello' |
| number | 数字（整数或浮点） | 42，3.14 |
| boolean | 布尔值（必须小写） | true，false |

**基本类型写法规范：**

* 字符串字面量：表达式内使用单引号包裹，如 'string'
* 布尔值：
 必须是小写：true、false
  ❌ 不支持：True、False、TRUE、FALSE

###### 4.2.2.1.3 运算符

| 优先级<br>（从高到低） | 运算符 | 说明 | 示例 |
|----------------|---------|------|------|
| 1 | () | 括号 | "{{ ($parentWidth - 20) / 2 }}" |
| 2 | . [] | 成员访问 | "{{ $items[0].name }}" |
| 3 | ! | 逻辑非 | "{{ $isLogin && !$isLocked && $hasPermission }}" |
| 4 | * / % | 乘、除、取模 | "{{ $price * $quantity / $count % 100 }}" |
| 5 | + - | 加、减 | "{{ 1 - ($progress + $startValue) / 100 }}" |
| 6 | > >= < <= | 比较 | "{{ $age >= 18 ? '成年人' : '未成年' }}" |
| 7 | == != | 等值比较 | "{{ $password == $answer }}" |
| 8 | && | 逻辑与 | "{{ $isLogin && !$isLocked && $hasPermission }}" |
| 9 | \|\| | 逻辑或 | "{{ $isLogin \|\| !$isLocked && $hasPermission }}" |
| 10 | ?: | 三元条件 | "{{ $age >= 18 ? '成年人' : '未成年' }}" |

**数组索引访问**

支持使用方括号访问数组元素，索引可以是数字常量或变量。

* **数组索引特点**：
 1. 使用 `[index]` 语法访问数组元素
 2. 索引可以是数字常量或变量
 3. 支持链式访问：`$items[0].user.name`
 4. 绝对路径也支持数组：`$__dataModel.items[0].name`

```json
{
  "content": "{{ $items[0].name }}",
  "value": "{{ $__dataModel.users[$index].age }}",
  "visible": "{{ $items[$index].isActive }}"
}
```

> 变量引用与作用域规则详见 [§4.2.2.2 变量系统](#4222-变量系统)。

###### 4.2.2.1.4 内置函数

表达式内置函数仅支持 `size()`。

**数组函数**

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| size(arr) | array | number | 数组长度。参数为非数组类型时返回 `0` |

```json
{
  "content": "{{ size($items) + ' 件商品' }}"
}
```

###### 4.2.2.1.5 类型转换

表达式在运算时遵循以下自动类型转换规则。类型转换失败时求值失败，返回空字符串 `""`。

**falsy 值定义**：`false`、`0`、`''`（空字符串）。非 falsy 值均为 truthy。

**加法运算 `+`**

任一操作数为 string → 拼接（另一操作数转 string）；否则 → 算术加法（boolean 转 number）。

| 运算 | 转换规则 | 示例 |
|------|----------|------|
| string + string | 无转换，字符串拼接 | `'Hello, ' + $name` → `'Hello, Alice'` |
| string + number | number转string，拼接 | `'count: ' + 3` → `'count: 3'` |
| string + boolean | boolean转string，拼接 | `'flag: ' + true` → `'flag: true'` |
| number + string | number转string，拼接 | `3 + ' items'` → `'3 items'` |
| boolean + string | boolean转string，拼接 | `true + ' yes'` → `'true yes'` |
| number + number | 无转换，算术加法 | `3 + 5` → `8` |
| boolean + number | boolean转number（true=1, false=0），算术加法 | `true + 2` → `3` |
| number + boolean | boolean转number（true=1, false=0），算术加法 | `5 + false` → `5` |
| boolean + boolean | 都转number，算术加法 | `true + true` → `2` |

**算术运算 `-` `*` `/` `%`**

操作数均转 number 后计算。boolean 直接转换，string 尝试转换，转换失败则求值失败返回 `""`。

| 运算 | 转换规则 | 示例 |
|------|----------|------|
| number - number | 无转换，直接计算 | `10 - 3` → `7` |
| boolean - number | boolean转number | `true - 1` → `0` |
| number - boolean | boolean转number | `5 - false` → `5` |
| boolean - boolean | 都转number | `true - false` → `1` |
| string(数字) - number | string转number后计算 | `'10' - 3` → `7` |
| number - string(数字) | string转number后计算 | `10 - '3'` → `7` |
| string(非数字) - number | 求值失败，返回 `""` | `'abc' - 3` → `""` |
| string - string | 均尝试转number，任一失败则返回 `""` | `'10' - '3'` → `7`，`'abc' - '3'` → `""` |

> `*` `/` `%` 规则相同。

**比较运算 `>` `>=` `<` `<=`**

同为 string → 字典序比较；否则 → 都转 number 比较，string 转换失败则为 `NaN`，比较结果为 `false`。

| 运算 | 转换规则 | 示例 |
|------|----------|------|
| number > number | 无转换，数值比较 | `10 > 3` → `true` |
| string > string | 字典序比较 | `'abc' > 'abb'` → `true` |
| boolean > boolean | 都转number | `true > false` → `true` |
| number > boolean | boolean转number | `2 > true` → `true` |
| boolean > number | boolean转number | `false > 0` → `false` |
| string(数字) > number | string转number后比较 | `'20' > 18` → `true` |
| number > string(数字) | string转number后比较 | `18 > '10'` → `true` |
| string(非数字) > number | string转为NaN，比较结果为 `false` | `'abc' > 3` → `false` |

**等值比较 `==` `!=`**

同类型直接比较值；不同类型时，boolean 转 number，string 尝试转 number 后比较。

| 运算 | 转换规则 | 示例 |
|------|----------|------|
| 同类型 == 同类型 | 无转换，直接比较值 | `3 == 3` → `true`，`'a' == 'b'` → `false` |
| number == boolean | boolean转number | `1 == true` → `true`，`0 == false` → `true` |
| string == boolean | 都转number（boolean→0/1，string→number） | `'true' == true` → `false`，`'1' == true` → `true` |
| string(数字) == number | string转number后比较 | `'42' == 42` → `true` |
| number == string(数字) | string转number后比较 | `42 == '42'` → `true` |
| string(非数字) == number | 转换失败，返回 `false`（`!=` 返回 `true`） | `'abc' == 42` → `false` |

**逻辑运算 `&&` `||`**

短路求值，返回实际值（不一定是 boolean）。

| 运算 | 转换规则 | 示例 |
|------|----------|------|
| truthy && value | 返回 value | `$isLogin && $userName` → $userName 的值 |
| falsy && value | 返回 falsy 值（短路） | `false && $name` → `false` |
| truthy \|\| value | 返回 truthy 值（短路） | `$name \|\| 'default'` → $name 的值 |
| falsy \|\| value | 返回 value | `0 \|\| 42` → `42` |

**逻辑非 `!` 和三元条件 `?:`**

| 运算 | 转换规则 | 示例 |
|------|----------|------|
| !falsy | 返回 `true` | `!false` → `true`，`!0` → `true`，`!''` → `true` |
| !truthy | 返回 `false` | `!true` → `false`，`!1` → `false`，`!'hello'` → `false` |
| truthy ? a : b | 返回 a | `$count ? $count + ' items' : 'empty'` |
| falsy ? a : b | 返回 b | `0 ? 'yes' : 'no'` → `'no'` |

###### 4.2.2.1.6 表达式文法（EBNF）

完整 EBNF 文法见 [expression_grammar.ebnf](json/expression_grammar.ebnf)。

##### 4.2.2.2 变量系统

各类变量的定义与使用规则见以下各节，求值计算时遵循就近优先原则（详见 [§4.2.2.2.6 作用域与冲突解决](#42226-作用域与冲突解决)）。

###### 4.2.2.2.1 变量分类总览

| 类别 | 前缀/语法 | 作用域 | 响应式 | 详见 |
|------|-----------|--------|--------|------|
| 全局系统变量 | `$__` | 全局 | Form 不支持 | [§4.2.2.2.2](#42222-全局系统变量) |
| DataModel 变量 | `$__dataModel.xxx` | surface 级 | 是 | [§4.2.2.2.3](#42223-datamodel-变量) |
| 循环变量 | `$item`, `$index` | 子组件模板内 | 否 | [§4.2.2.2.4.1](#422241-循环变量子组件模板) |
| 行为链变量 | `$varName`（as 绑定） | 当前事件行为链 | 否 | [§4.2.2.2.4.2](#422242-行为链变量as-绑定) |
| 事件上下文 | `$context` | 当前事件行为链 | 否 | [§4.2.2.2.4.3](#422243-事件上下文变量) |

###### 4.2.2.2.2 全局系统变量

全局系统变量由框架自动维护，在任何表达式中均可引用。

> Form 协议排除了全量协议中的全局系统变量 `$__widthBreakpoint`（响应式断点）和 `$__colorMode`（颜色模式），因为服务卡片运行在固定尺寸和固定主题环境中。`$__dataModel` 作为 surface 级变量不受此限制，详见 [§4.2.2.2.3](#42223-datamodel-变量)。

> `$__dataModel` 虽使用 `$__` 前缀，但其作用域为 surface 级，详见 [§4.2.2.2.3](#42223-datamodel-变量)。

###### 4.2.2.2.3 DataModel 变量

DataModel 变量引用数据模型中的数据，支持**绝对路径**和**相对路径**两种方式。相对路径在子组件模板中使用（模板机制概述参见 [§3.7 子组件模板生成](#37-子组件模板生成)）。

| 路径类型 | 语法 | 示例 | 适用范围 |
|----------|------|------|----------|
| 绝对路径 | `$__dataModel.xxx.yyy` | `$__dataModel.user.name` | 任何表达式 |
| 相对路径 | `$item.fieldName` | `$item.firstName` | 子组件模板内 |

**绝对路径**：从数据模型根节点开始，使用 `$__dataModel` 前缀，通过 `.` 访问属性。

```json
{
  "component": "Text",
  "content": "{{ $__dataModel.user.profile.name }}"
}
```

**绝对路径特点：**
1. 必须以 `$__dataModel` 开头
2. 使用 `.` 进行属性访问
3. 不受当前模板作用域影响
4. 适合访问全局配置、用户信息等跨模板数据

**相对路径（子组件模板）**：模板中使用 `$item.fieldName` 引用当前迭代项的字段。`$item` 是当前项对象，通过 `.` 访问其属性。

```json
{
  "component": "List",
  "children": {
    "path": "/users",
    "componentId": "user_item"
  }
},
{
  "id": "user_item",
  "component": "Text",
  "content": "{{ $item.firstName + ' ' + $item.lastName }}"
}
```

**绝对路径与相对路径的混合使用**：

```json
{
  "component": "List",
  "children": { "path": "/comments", "componentId": "comment_item" }
},
{
  "id": "comment_item",
  "component": "Column",
  "children": ["app_name", "comment_text"]
},
{
  "id": "app_name",
  "component": "Text",
  "content": "{{ $__dataModel.app.name }}"       // 绝对路径：每次迭代都从根获取
},
{
  "id": "comment_text",
  "component": "Text",
  "content": "{{ $item.text }}"                   // 相对路径：当前评论项的 text 字段
}
```

**与 A2UI path 属性的区别：**
- A2UI 协议的 `path` 属性使用 `/` 分隔符（如 `"path": "/users"`），用于声明式数据绑定
- 表达式内部使用 `$__dataModel.xxx` 点路径引用，用于动态表达式计算

**JSON Pointer 引用**（扩展）：

表达式中支持 `${/json/pointer}` 语法引用数据模型路径，作为 `$__dataModel.xxx` 点路径语法的补充，与 A2UI 规范保持一致：

```json
{
  "component": "Text",
  "content": "{{ ${/user/profile/name} + ' 您好' }}"
}
```

以上 `${/user/profile/name}` 等价于 `$__dataModel.user.profile.name`，两种语法可按需选用。

###### 4.2.2.2.4 局部变量

局部变量在特定作用域内有效，包括循环变量、行为链变量、事件上下文变量。

<a id="422241-循环变量子组件模板"></a>

**4.2.2.2.4.1 循环变量（子组件模板）**

在支持模板生成子组件的父组件（Row, Column, List）中，循环变量自动可用。模板机制概述及典型示例参见 [§3.7 子组件模板生成](#37-子组件模板生成)。

| 变量 | 类型 | 说明 |
|------|------|------|
| `$index` | number | 当前项的索引（从 0 开始） |
| `$item` | any | 当前项的数据对象 |

```json
{
  "component": "List",
  "children": { "path": "/items", "componentId": "item_template" }
},
{
  "id": "item_template",
  "component": "Text",
  "content": "{{ ($index + 1) + '. ' + $item.name }}"
}
```

**自定义循环变量名**：通过 `indexVar` 和 `itemVar` 属性自定义：

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `indexVar` | string | `"index"` | 自定义索引变量名 |
| `itemVar` | string | `"item"` | 自定义项数据变量名 |

```json
{
  "component": "List",
  "children": {
    "path": "/products",
    "componentId": "product_template",
    "indexVar": "i",
    "itemVar": "product"
  }
},
{
  "id": "product_template",
  "component": "Text",
  "content": "{{ $i + ': ' + $product.name }}"
}
```

**嵌套子组件模板**：外层自定义变量可在内层模板中访问：

```json
{
  "component": "List",
  "children": {
    "path": "/classes",
    "componentId": "class_tpl",
    "indexVar": "classIdx",
    "itemVar": "classInfo"
  }
},
{
  "id": "class_tpl",
  "component": "Column",
  "children": [
    { "component": "Text", "content": "{{ $classInfo.name }}" },
    {
      "component": "List",
      "children": {
        "path": "/students",
        "componentId": "student_tpl"       // 使用默认 $index 和 $item
      }
    }
  ]
},
{
  "id": "student_tpl",
  "component": "Text",
  "content": "{{ $classIdx + ':' + $item.name }}"
  // 可同时访问外层 $classIdx 和内层 $item
}
```

<a id="422242-行为链变量as-绑定"></a>

**4.2.2.2.4.2 行为链变量（as 绑定）**

行为通过 `as` 字段将返回值绑定为局部变量，后续行为通过 `$varName` 引用。作用域覆盖当前事件的行为链，事件完成后释放。

```json
{
  "component": "Button",
  "onClick": [
    {
      "call": "validateForm",
      "as": "validResult",
      "args": {}
    },
    {
      "call": "submitData",
      "condition": "{{ $validResult == 0 }}"
    }
  ]
}
```

**规则：**
- `as` 绑定的变量名以 `$` 前缀引用（如 `$validResult`）
- 变量作用域为当前事件的行为链，不可跨事件引用
- `as` 绑定名应避免与 DataModel 变量名同名，若同名则局部优先（见 [§4.2.2.2.6](#42226-作用域与冲突解决)）

<a id="422243-事件上下文变量"></a>

**4.2.2.2.4.3 事件上下文变量**

在事件处理的行为数组中，可通过 `$context` 获取事件触发时的上下文信息：

| 属性 | 类型 | 说明 |
|------|------|------|
| `$context.componentId` | string | 触发事件的组件 ID |

```json
{
  "call": "updateField",
  "args": {
    "field": "{{ $context.componentId }}",
    "value": "{{ $context.eventData }}"
  }
}
```

###### 4.2.2.2.5 变量引用语法

表达式中引用变量的完整语法规则：

```jsonc
{{ $userName }}                              // 简单变量
{{ $user.address.city }}                     // 点路径嵌套
{{ $items[0].name }}                         // 数组索引
{{ $age >= 18 ? 'adult' : 'minor' }}         // 变量参与运算
{{ size($items) }}                           // 变量作为函数参数
{{ 'Hello, ' + $name }}                      // 字符串拼接
```

**规则：**
1. `$var` 是变量的唯一引用形式
2. 字符串拼接使用 `+` 运算符

###### 4.2.2.2.6 作用域与冲突解决

变量求值计算时遵循**就近优先**原则：

| 优先级 | 作用域 | 示例 | 说明 |
|--------|--------|------|------|
| 1（最高） | 行为链局部变量 | `$validResult` | `as` 绑定 |
| 2 | 循环变量 | `$item`, `$index` | 子组件模板内 |
| 3 | 事件上下文 | `$context.eventData` | 事件处理函数内 |

> `$__dataModel` 虽在优先级表中属于"全局系统变量"层级，但其实际作用域为 surface 级。跨 surface 场景下，每个 surface 拥有独立的 DataModel 实例，`$__dataModel` 仅指向当前 surface 的 DataModel。

**同名冲突处理规则：**
- `as` 绑定名与 DataModel 变量同名时，`as` 绑定优先
- 建议 `as` 绑定名避免与 DataModel 变量名相同
- `$__` 双下划线前缀的全局变量不会被局部变量遮蔽

###### 4.2.2.2.7 局部变量命名规范

`itemVar`、`indexVar`、`as` 的自定义变量名须遵循以下规则：

1. **语法规则**：必须以字母或下划线开头，仅包含字母、数字、下划线（正则：`^[a-zA-Z_][a-zA-Z0-9_]*$`）。禁止以数字开头、包含空格或特殊字符。

2. **不含 `$` 前缀**：`itemVar`/`indexVar`/`as` 的值不含 `$` 前缀，`$` 在表达式引用时自动拼接（如 `itemVar: "product"` → 引用 `$product`）。

3. **同名回退**：当同一模板中 `indexVar` 与 `itemVar` 设为相同值时，两个自定义名均失效，自动回退为默认 `$item` / `$index`。

###### 4.2.2.2.8 响应式更新

当表达式引用的变量值发生变化时，表达式会重新求值并自动更新绑定的属性。响应式更新支持的范围包括：
- **组件属性**（如 `content`, `condition`, `visible` 等）
- **组件样式属性**（如 `fontSize`, `fontColor`, `width` 等）


> **表达式求值失败处理**：表达式求值失败时（如引用不存在的变量、类型不匹配等）返回空字符串 `""`，不中断页面渲染。

### 4.3 JSON Schema

请参考[form_catalog.json](json/form_catalog.json)。

