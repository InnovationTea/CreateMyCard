# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import base64
import hashlib
import hmac
import json
import json_repair
import time
import traceback
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
        if text.startswith('```genui'):
            content = text[len('```genui'):].strip()
            if content.endswith('```'):
                content = content[:-3].strip()
            return content
        else:
            return text

    def process_line(self, line):
        """
        处理单行 JSON 字符串，返回解析后的数据或 None
        """
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            logger.error(f"json_parse_failed line={json_for_log(line)}")
            try:
                return json_repair.loads(line)
            except Exception as e:
                logger.error(
                    f"json_repair_failed exception_type={type(e).__name__} "
                    f"exception={e!r} traceback={traceback.format_exc()}"
                )
                return None

    def convert_dsl(self, dsl_text: str) -> str:
        """
        dsl 文本处理函数
        """
        output_lines = []

        for line in dsl_text.splitlines():
            line = line.strip()
            if not line:
                continue

            data = self.process_line(line)
            if not data:
                logger.error(f"dsl_line_parse_failed line={json_for_log(line)}")
                return dsl_text

            # 修改 createSurface.catalogId
            create_surface = data.get("createSurface")
            if create_surface:
                create_surface["catalogId"] = "ohos.a2ui.extended.catalog.form"

            # 修改 root 的宽高
            update_components = data.get("updateComponents")
            if update_components:
                for component in update_components.get("components", []):
                    if component.get("id") == "root":
                        styles = component.setdefault("styles", {})
                        styles["width"] = "matchParent"
                        styles["height"] = "matchParent"
                        break

            output_lines.append(
                json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            )

        return "\n".join(output_lines)

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
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                f"a2ui_model_response_received "
                f"content_preview={full_text} "
                f"duration_ms={duration_ms}"
            )

            # 剔除···genui ```内容
            dsl_text = self.extract_genui_payload(full_text)

            # 纠正 dsl 问题，包括加桌白边和其他问题
            dsl_text = self.convert_dsl(dsl_text)

            logger.info(
                f"a2ui_dsl_processed "
                f"dsl_content={dsl_text}"
            )

            return dsl_text
        except requests.exceptions.Timeout as e:
            logger.error(
                f"a2ui_model_request_timeout "
                f"exception_type={type(e).__name__} exception={e!r} "
                f"traceback={traceback.format_exc()}"
            )
            error_detail = f"a2ui_model_error: timeout after {timeout}s, {e}"
        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"a2ui_model_connection_error "
                f"exception_type={type(e).__name__} exception={e!r} "
                f"traceback={traceback.format_exc()}"
            )
            error_detail = f"a2ui_model_error: connection failed, {e}"
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            logger.error(
                f"a2ui_model_http_error "
                f"status_code={status} "
                f"exception_type={type(e).__name__} exception={e!r} "
                f"traceback={traceback.format_exc()}"
            )
            error_detail = f"a2ui_model_error: HTTP {status}, {e}"
        except requests.exceptions.RequestException as e:
            logger.error(
                f"a2ui_model_request_exception "
                f"exception_type={type(e).__name__} exception={e!r} "
                f"traceback={traceback.format_exc()}"
            )
            error_detail = f"a2ui_model_error: request failed, {e}"
        except Exception as e:
            logger.error(
                f"a2ui_model_unexpected_error "
                f"exception_type={type(e).__name__} exception={e!r} "
                f"traceback={traceback.format_exc()}"
            )
            error_detail = f"a2ui_model_error: unexpected error, {type(e).__name__}: {e}"

        return error_detail
