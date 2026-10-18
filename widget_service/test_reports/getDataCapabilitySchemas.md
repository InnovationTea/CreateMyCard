# getDataCapabilitySchemas 测试报告

- 生成时间：2026-07-10T02:03:51.678293+00:00
- 接口名：`getDataCapabilitySchemas`
- WebSocket path：`/api/v1/ws/tools/getDataCapabilitySchemas`
- 请求协议：content/deviceInfo/session 外层包络
- requestId：`7676c2c8-a6d3-413c-8074-c62ed30db8de&2`
- 消息状态：`result`
- 业务状态：`success`

## 入参

```json
{
  "content": {
    "odid": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
    "bundleName": "com.omega_w_0823.hmservice",
    "dataCapabilityIds": [
      "ViewWeather"
    ]
  },
  "deviceInfo": {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "prdVer": "11.7.5.205",
    "sysVer": "EmotionUI_9.0.0",
    "romVersion": "CLS-AL30 6.0.0.328",
    "time": "20260707115342975"
  },
  "pagination": {
    "limit": 5,
    "start": ""
  },
  "session": {
    "interactionId": "2",
    "isNew": false,
    "sessionId": "7676c2c8-a6d3-413c-8074-c62ed30db8de"
  },
  "userAuth": {
    "user": {
      "userId": "test-user-001"
    }
  },
  "utterance": {
    "original": "",
    "type": "text"
  },
  "version": "1.0",
  "bundleName": "com.omega_w_0823.hmservice"
}
```

## 出参

```json
{
  "errorCode": "0",
  "errorMessage": "",
  "reply": {
    "streamInfo": {
      "streamContent": "type='result' tool='getDataCapabilitySchemas' operation='getDataCapabilitySchemas' requestId='7676c2c8-a6d3-413c-8074-c62ed30db8de&2' data={'apiVersion': 'v1', 'capabilityRegistryVersion': 'app-11.7.5.205_rom-6.0', 'dataCapabilities': [{'id': 'ViewWeather', 'type': 'data', 'description': '查询指定地区或用户当前位置的当前天气与未来数日天气预报。', 'descriptionForLLM': '', 'inputSchema': {'type': 'object', 'properties': {'districtName': {'type': 'string', 'description': '区县名。'}, 'prefectureName': {'type': 'string', 'description': '城市名，用于同名区县消歧，可不传。'}, 'forecastDays': {'type': 'integer', 'description': '返回预报天数，支持1至5天；不传时默认返回3天。'}}, 'required': ['districtName']}, 'outputSchema': {'type': 'object', 'description': '适合桌面卡片展示的标准化天气概要。current 是固定对象，daily 是数量由 forecastDays 决定的数组。', 'properties': {'location': {'type': 'object', 'description': '实际查询成功的地区。', 'properties': {'cityCode': {'type': 'string', 'description': '城市代码，如60814代表青浦区', 'sampleValue': '60814'}, 'districtName': {'type': 'string', 'description': '区或县名称', 'sampleValue': '青浦区'}, 'prefectureName': {'type': 'string', 'description': '城市名称', 'sampleValue': '上海市'}}}, 'current': {'type': 'object', 'description': '当日天气实况', 'properties': {'temperatureC': {'type': 'number', 'description': '当前摄氏温度。', 'sampleValue': 29}, 'temperatureText': {'type': 'string', 'description': '适合直接显示的温度文本，例如“29°C”。', 'sampleValue': '29°C'}, 'condition': {'type': 'string', 'description': '当前天气现象，例如“阴”“多云”“小雨”。', 'sampleValue': '多云'}, 'feelsLikeC': {'type': 'number', 'description': '当前体感摄氏温度。', 'sampleValue': 31}, 'humidityPercent': {'type': 'number', 'minimum': 0, 'maximum': 100, 'description': '当前相对湿度百分比。', 'sampleValue': 68}, 'airQuality': {'type': 'string', 'description': '当前空气质量等级，例如“优”“良”。', 'sampleValue': '良'}, 'windDirection': {'type': 'string', 'description': '当前风向。', 'sampleValue': '东南风'}, 'windLevel': {'type': 'integer', 'minimum': 0, 'description': '当前风力等级。', 'sampleValue': 2}, 'uvIndex': {'type': 'string', 'description': '当前紫外线等级，例如“弱”“中等”“强”。', 'sampleValue': '中等'}, 'coldLevel': {'type': 'string', 'description': '感冒指数。', 'sampleValue': '低'}, 'alertLevel': {'type': 'string', 'description': '预警信息。', 'sampleValue': ''}}}, 'daily': {'type': 'array', 'description': '从今天开始按日期升序排列的每日预报。', 'items': {'type': 'object', 'properties': {'date': {'type': 'string', 'description': '预报日期，来源于 day_time。', 'sampleValue': '2026-08-06'}, 'weekday': {'type': 'string', 'description': '星期文本，例如“星期日”。', 'sampleValue': '星期四'}, 'condition': {'type': 'string', 'description': '白天天气现象，来源于weather_icon。', 'sampleValue': '多云'}, 'temperatureRangeText': {'type': 'string', 'description': '适合直接显示的温度范围，例如“24° / 32°”。', 'sampleValue': '25° / 32°'}, 'rainProbabilityPercent': {'type': 'string', 'description': '白天降雨概率百分比。如：73%', 'sampleValue': '20%'}, 'airQuality': {'type': 'string', 'description': '当天空气质量等级。', 'sampleValue': '良'}, 'uvIndex': {'type': 'string', 'description': '当天紫外线等级。', 'sampleValue': '中等'}, 'coldLevel': {'type': 'string', 'description': '感冒指数。', 'sampleValue': '低'}}}}, 'updatedAt': {'type': 'string', 'description': '端侧完成天气查询和归一化的时间。如：2026-06-14 15:30', 'sampleValue': '2026-08-06 09:00'}}}, 'defaultWriteResultTo': '/data/weather', 'dataModelSkeleton': {}, 'dependencies': {'requiredPackages': [{'packageName': 'com.huawei.hmos.weather'}]}}], 'missingCapabilityIds': []} status='success' errorCode='' error={}",
      "streamingTextId": "7676c2c8-a6d3-413c-8074-c62ed30db8de&2",
      "streamType": "final",
      "textType": "plainText"
    },
    "items": []
  }
}
```
