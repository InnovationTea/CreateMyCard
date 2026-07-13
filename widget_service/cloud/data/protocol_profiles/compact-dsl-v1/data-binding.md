# Compact DSL Data Binding

字符串属性有两种赋值方式：

```genui
["title","Text",{"content":"天气速览"}]
```

```genui
["title","Text",{"content":{"path":"/title"}}]
["/title","天气速览"]
```

- `Text.content` 的语义类型仍是 string；`{"path":"/title"}` 是协议层的取值方式。
- path 必须是以 `/` 开头的 JSON Pointer，禁止点记法。
- 属性引入 path 绑定后，同一个 genui 必须包含该 path 的数据行。
- UI 属性绑定的初始数据行必须出现在对应组件行之后。
- data 行的 value 可以是 string、number、boolean、object、array 或 null。
- `TextInput.text` 必须使用 path 绑定。
