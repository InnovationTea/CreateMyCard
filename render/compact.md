# Compact GenUI 协议：

模型输出极简GenUI协议，并在指令解析阶段映射回完整A2UI协议。
说明：A2UI关键指令包含以下四种：createSurface、updateComponent、updateDataModel、deleteSurface，针对以下四种格式分别设计极简协议
目的：在不丢失任何重要参数的基础上，尽可能减少模型的token输出 这段话的作用是什么

## createSurface

### A2UI指令格式：
```jsonl
{
    version: "v0.9";
    createSurface: {
        surfaceId: string;
        catalogId: string;
        theme?: object;
        send_DataModel?: boolean;
    }
}
```

### 极简GenUI协议格式如下所示：
只包含A2UI协议中最关键的三个属性：surfaceId, catalogId, theme
通过位置关系确认参数定义，无需key-value对
添加@标识符，便于在parse阶段进行指令解析

```jsonl
{
    '@'+suraceId,   // @+表面唯一标识符
    catalogId,  // 组件库唯一标识符
    {...theme...}?  // 可选，系统主题
    send_DataModel? // 可选
}
```

### 输出示例如下
```jsonl
{
    "@weather_card",
    "https://xxx/specification/ohos/extended_catalog.json",
    {"primaryColor":"#0A59F7"}
}
```

协议映射关系 (parse阶段设计方案)：
一条极简协议指令输出映射到一条createSurface指令，也就是说，一条完整的A2UI createSurface指令可视作一个固定模板，将极简协议输出的内容填入模板即可
'@'+surfaceId映射回surfaceId
catalogId映射回catalogId
theme映射回theme
parser通过检查第一个参数的第一个字符是否为@即可判断是否为一条createSurface指令
输出示例如下：
```jsonl
{
    "version": "v0.9",
    "createSurface": {
        "surfaceId": "weather_card",
        "catalogId": "https://xxx/specification/ohos/extended_catalog.json",
        "theme": {
            "primaryColor": "#0A59F7"
        }
    }
}
```

## updateComponent

### A2UI指令格式：
```jsonl
{
    version: "v0.9";
    updateCompontns: {
        surfaceId: string;  // Required: Target surface
        components: Array<{ // Required: List of components
            id: string; // Required: Component ID
            component: string; // Required: Component type name
            ...properties   // Component-specific properties (flat)
        }>
    }
}
```

### 极简GenUI协议格式如下所示：

只包含A2UI协议中最关键的五项属性：surfaceId, componentId, type, props, children
components数组中永远只有一个元素
通过位置关系确认参数含义，无需key-value对
添加'@'标识符，便于在parse阶段进行指令解析
```jsonl
{
    surfaceId,  // 表面唯一标识符
    componentId,    // 组件唯一标识符
    type,   // 组件类型
    {...props...}   // 组件属性
    [...children...]?    // 可选，子组件id数组
}
```

### 输出示例如下：
```jsonl
{
    "weather_card",
    "save_card",
    "Card",
    {
        "title": "偏好设置",
        "description": "修改后请点击保存",
        "layout": vertical",
        "gap": 12,
        "justifyContent": "center"
    },
    ["hint", "save-btn"]
}
```

### 协议映射关系（parse阶段设计方案）：
一条极简协议指令输出映射到一条updateComponent指令，也就是说，一条完整的A2UI updateComponent指令可视作一个固定模板，将极简协议输出的内容填入模板即可
parser通过检查第一个参数的第一个字符是否为'@'即可判断是否为一条updateComponent指令，即不存在'@'
parser可根据参数特性完成参数识别：id和type为字符串，由""包裹，props为json，由{}包裹，children为数组，由[]包裹
输出示例如下：
```jsonl
{
    "version": "v0.9",
    "updateComponents": {
        "surfaceId": "weathwe_session_001",
        "components": [
            {
                "id": "header",
                "component": "Extended.Column",
                "children": ["header", "price_section"],
                "space": 12,
                "styles": {
                    "width": "matchParent",
                    "boarderRadius": 20
                }
            }
        ]
    }
}
```

## updateDataModel
### A2UI指令格式：
```jsonl
{
    version: "v0.9";
    updateDataModel: {
        surfaceId: string;  // Required: Target surface
        path?: string;      // Optional: JSON Pointer path (default to "/")
        value?: any;        // Optional: Value to set (omit to delete)
    }
}
```

### 极简GenUI协议格式如下所示：
由于updateDataModel结构相对简单，极简协议参数与原参数基本对齐：surfaceId, path, value
通过位置关系确认参数含义，无需key-value对
根据第二个参数的'/'标识符，在parse阶段进行指令解析
```jsonl
{
    surfaceId,  // 表面唯一标识符
    path,       // 变量路径
    value       // 变量值
}
```

### 输出示例如下：
```jsonl
{
    "weather_card",
    "/card/xxx",
    "123"
}
```

### 协议映射关系 （parse阶段设计方案）：
一条极简协议指令输出映射到一条updateDataModel指令，也就是说，一条完整的A2UI updateDataModel指令可视作一个固定模板，将极简协议输出的内容填入模板即可
surfaceId映射回surfaceId
path映射回path
value映射回value
parser通过检查第二个参数的第一个字符是否为'/'即可判断是否为一条updateDataModel指令
输出示例如下：
```jsonl
{
    "version": "v0.9";
    "updateDataModel": {
        "surfaceId": "weather_card"
        "path": "/card/xxx"
        "value": "123"
    }
}
```

## deleteSurface
### A2UI指令格式：
```jsonl
{
    version: "v0.9";
    deleteSurface: {
        surfaceId: string;  // Required: Surface to delete
    }
}
```

### 极简GenUI协议格式如下所示：
只包含一个属性：surfaceId
通过位置关系确认参数含义，无需key-value对
添加'~'标识符，便于在parse阶段进行指令解析

```jsonl
{
    '~'+surfaceId,
}
```

### 输出示例如下：
```jsonl
{
    "~weather_card",
}
```

### 协议映射关系（parse阶段设计方案）：
一条极简协议指令输出映射到一条deleteSurface指令，也就是说，一条完整的A2UI deleteSurface指令可视作一个固定模板，将极简协议输出的内容填入模板即可
'~'+surfaceId映射回surfaceId
parser通过检查第一个参数的第一个字符是否为'~'即可判断是否为一条deleteSurface指令
输出示例如下：
{
    "version": "v0.9";
    "deleteSurface": {
        surfaceId: "weather_card"
    }
}
