现在，需要 @genui-sdk/preprocess 添加一层预处理，

@genui-sdk/preprocess 的作用是将用户的输入进行预处理，如果用户传进来的是封装好的JSON结构，
需要对其中的某些字段进行预处理，这样后续将预处理好的JSON输入传给LLM大模型，就可以减少输入token和输出token。

目前需要预处理的字段：（你只需要处理这些字段，后续有需要我会再增加）
moreLink
listItemLink

识别到 JSON 中的上述 key 后，需要对 value 值进行映射处理，例如将moreLink对应的 value 改写成 $action_openUrl_001，然后内存里存放一个哈希表，key 值是 $action_openUrl_001, value 值就是原来的value。

这样的目的是让大模型接受比较少的参数，但是仍然可以输出内容，之后在 @genui-sdk/parser 阶段，每次处理完一个完整的 NDJSON，就需要进行后处理，若识别到形如 $action_openUrl_001 这种参数，就需要从哈希表中读取对应的 value 并从中规则提取需要的片段：

下面是目前需要提取的字段：（你只需要提取这些字段，后续有需要我会再增加）
webURL

然后，如果识别到了 webURL 字段，就需要在组件上合成 **`action.functionCall`**，例如用
```json
"action": {
  "functionCall": {
    "call": "openUrl",
    "args": {
      "url": "https://example.com/path-from-structured-webURL"
    }
  }
}
```

替换占位符
```json
"action": {
  "functionCall": {
    "call": "openUrl",
    "args": {
      "url": "$action_openUrl_001"
    }
  }
}
```

并在 parser 后处理阶段把 `$action_openUrl_001` 还原为真实 URL。
