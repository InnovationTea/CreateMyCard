# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

import requests

from app.logger import json_for_log, logger
from config.config import get_settings
from services.compact_dsl_protocol import is_compact_dsl
from utils.base_utils import sts_config


class A2UIModelClient:
    """A2UI 模型调用客户端。

    mock 开关打开时按协议 profile 返回对应 mock 文件的原始内容；
    关闭时调用真实小模型接口。
    """

    def __init__(
            self,
            use_mock: bool | None = None,
            mock_data_path: str | Path | None = None,
    ) -> None:
        """初始化 A2UI 模型客户端。

        入参：
        - use_mock：是否使用 mock 数据；不传时读取全局配置。
        - mock_data_path：可选 mock 文件路径；不传时按协议选择同目录 mock 文件。
        出参：无。
        """
        settings = get_settings()
        self.settings = settings
        self.use_mock = (
            settings.enable_a2ui_model_mock if use_mock is None else use_mock
        )
        self.mock_data_path = Path(mock_data_path) if mock_data_path else None

    def generate(
            self,
            prompt: list[dict[str, str]],
            protocol_profile: dict | None = None,
    ) -> str:
        """生成 A2UI genui JSONL。

        入参：
        - prompt：PromptBuilder 生成的模型输入。
        - protocol_profile：用于选择协议对应的 mock；真实模型直接消费 prompt。
        出参：A2UI genui JSONL 字符串。
        """
        logger.info(
            f"a2ui_model_generate_started use_mock={json_for_log(self.use_mock)} "
            f"system_prompt={json_for_log(prompt)}"
        )

        if self.use_mock:
            return self._load_mock_data(protocol_profile)

        return self._generate_from_real_model(prompt)

    def _load_mock_data(self, protocol_profile: dict | None = None) -> str:
        """直接读取当前协议对应的 mock 原始内容。

        入参：无。
        出参：mock 文件的完整 UTF-8 文本，不做替换或结构调整。
        """
        mock_data_path = self.mock_data_path
        if mock_data_path is None:
            filename = (
                "mock.compact-dsl.dat"
                if is_compact_dsl(protocol_profile or {})
                else "mock.dat"
            )
            mock_data_path = Path(__file__).with_name(filename)
        if not mock_data_path.is_file():
            raise FileNotFoundError(f"A2UI mock 数据文件不存在: {mock_data_path}")

        mock_data = mock_data_path.read_text(encoding="utf-8")
        logger.info(
            f"a2ui_model_generate_completed mode=mock path={mock_data_path}"
        )
        return mock_data

    def calc_sign(self, payload, method="POST", path=None, query_params=None):
        path = path or self.settings.model_path
        appid = self.settings.model_appid
        sign_key = sts_config.get_sts_config("genui.model.secret.key")
        if isinstance(sign_key, str):
            sign_key = sign_key.encode("utf-8")

        # 1. 处理请求体：空或 None 时为空字符串
        if payload is None or payload == '':
            playload = ''
        else:
            playload = payload

        # 2. 处理查询参数：按 key 排序并拼接为 key=value 串
        if query_params:
            sorted_keys = sorted(query_params.keys())
            kv_list = [f"{k}={query_params[k]}" for k in sorted_keys]
            query_str = '&'.join(kv_list)
        else:
            query_str = ''

        # 3. 路径：确保以 '/' 开头
        if not path.startswith('/'):
            path = '/' + path

        # 4. 毫秒级时间戳
        timestamp = str(int(time.time() * 1000))

        # 5. 拼接待签名字符串（注意保留原 JS 中可能出现的连续 &）
        sign_str = f"{method}&{path}&{query_str}&{playload}&appid={appid}&timestamp={timestamp}"

        # 6. HMAC-SHA256 计算并 Base64 编码
        signature_bytes = hmac.new(
            sign_key,
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).digest()
        signature = base64.b64encode(signature_bytes).decode('utf-8')

        # 7. 组装最终的 Authorization 值
        authorization = (
            f"CLOUDSOA-HMAC-SHA256 appid={appid}, timestamp={timestamp}, "
            f'signature="{signature}"'
        )
        return authorization

    def extract_genui_payload(self, text):
        """
        如果响应以'''genui 开头，则剔除前后标记，返回中间的JSON字符串
        否则原样返回。
        """
        text = text.strip()
        # 匹配三种引号开头（可能是三个双引号或三个单引号，此处按三个双引号处理）
        if text.startswith('```genui'):
            # 去掉开头 """genui （注意可能有换行）
            content = text[len('```genui'):].strip()
            # 如果结尾有 """，去掉它
            if content.endswith('```'):
                content = content[:-3].strip()
            return content
        else:
            return text

    def _generate_from_real_model(
            self,
            messages: list,
            max_tokens: int = 128000,
            stream: bool = True,
            timeout: int = 600,
    ) -> str:
        """
        调用小模型接口生成 DSL

        参数：
            messages     : 对话消息列表，如 [{"role":"user","content":"你好"}]
            max_tokens   : 最大生成token数
            stream       : 是否流式
            timeout      : 请求超时（秒）
        返回：
            服务端返回的str字典。
        """
        payload = {
            "model": self.settings.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": stream
        }
        payload_str = json.dumps(payload, ensure_ascii=False)

        authorization = self.calc_sign(payload_str)

        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }

        collected_texts = []
        reasoning_parts = []
        start = time.perf_counter()
        try:
            with requests.post(
                    self.settings.model_url,
                    data=payload_str,
                    headers=headers,
                    timeout=timeout,
                    stream=True
            ) as response:
                for line in response.iter_lines(decode_unicode=True):
                    logger.info(line)
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk.get("choices")
                        if not choices or len(choices) == 0:
                            continue

                        first_choice = choices[0]
                        delta = first_choice.get("delta")
                        if not delta:
                            continue

                        text = delta.get("content", "")
                        reasoning = delta.get("reasoning", "")
                        collected_texts.append(text)
                        reasoning_parts.append(reasoning)

            content_text = "".join(collected_texts)
            reason_text = "".join(reasoning_parts)
            full_text = content_text if content_text else reason_text
            logger.info(f"小模型返回的内容：{full_text}")

            dsl_text = self.extract_genui_payload(full_text)
            logger.info(f"生成的dsl语句：\n{dsl_text}")
            logger.info(f"小模型耗时: {time.perf_counter() - start:.4f} 秒")

            return dsl_text
        except requests.exceptions.Timeout:
            logger.error("\n请求超时，请检查网络或增加 timeout 值")
        except requests.exceptions.ConnectionError:
            logger.error("\n连接错误，请检查 URL、代理或网络设置")
        except requests.exceptions.HTTPError as e:
            logger.error(f"\n服务器返回错误状态码: {e}")
        except requests.exceptions.RequestException as e:
            # 其他所有 requests 异常
            logger.error(f"\n请求发生未知错误: {e}")
        except Exception as e:
            # 兜底，捕获非 requests 异常
            logger.error(f"\n发生未预料到的错误: {e}")

        return ""
