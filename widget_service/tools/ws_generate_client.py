import asyncio
import json

import websockets


async def main() -> None:
    """本地测试 WebSocket 生成接口。

    入参：无。
    出参：无；函数会打印 ready 消息和生成结果消息。
    """
    uri = "ws://127.0.0.1:8000/api/v1/ws/widget/generate"
    async with websockets.connect(uri) as websocket:
        print(await websocket.recv())
        await websocket.send(
            json.dumps(
                {
                    "requestId": "local-test-1",
                    "arguments": {
                        "userQuery": "帮我做通勤卡片，包含天气和今日日程",
                        "size": "2x4",
                        "appVersion": "1.0.0",
                        "romVersion": "7.0.0",
                        "candidateDataBindings": [
                            {
                                "capabilityId": "ViewWeather",
                                "arguments": {"districtName": "上海", "forecastDays": 1},
                                "writeResultTo": "/data/weather",
                            },
                            {
                                "capabilityId": "calendar.events.search",
                                "arguments": {"timeRange": "today"},
                                "writeResultTo": "/data/calendar",
                            },
                        ],
                        "candidateEventCapabilityIds": ["event.open.weather"],
                        "candidateEventActions": [
                            {
                                "call": "clickToDeeplink",
                                "args": {"uri": "hww://weather"},
                            }
                        ],
                        "candidateAssetIds": ["asset.drop_1"],
                        "options": {"returnArtifactInline": True},
                    },
                },
                ensure_ascii=False,
            )
        )
        print(await websocket.recv())


if __name__ == "__main__":
    asyncio.run(main())
