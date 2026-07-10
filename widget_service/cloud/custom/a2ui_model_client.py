# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
from pathlib import Path
from typing import Any

from app.logger import logger
from config.config import get_settings
from models.generation import TaskSpec
from models.service import A2UIPromptPayload


class A2UIModelClient:
    """A2UI 模型调用客户端。

    mock 开关打开时读取同目录的 mock.data；关闭时预留真实模型调用入口。
    """

    def __init__(
        self,
        use_mock: bool | None = None,
        mock_data_path: str | Path | None = None,
    ) -> None:
        """初始化 A2UI 模型客户端。

        入参：
        - use_mock：是否使用 mock 数据；不传时读取全局配置。
        - mock_data_path：可选 mock 文件路径；不传时固定读取本文件同级 mock.data。
        出参：无。
        """
        settings = get_settings()
        self.use_mock = (
            settings.enable_a2ui_model_mock if use_mock is None else use_mock
        )
        self.mock_data_path = Path(mock_data_path or Path(__file__).with_name("mock.data"))

    def generate(
        self,
        task_spec: TaskSpec,
        protocol_profile: dict,
        prompt: A2UIPromptPayload,
    ) -> str:
        """生成 A2UI genui JSONL。

        入参：
        - task_spec：模型任务输入。
        - protocol_profile：A2UI 协议 profile。
        - prompt：PromptBuilder 生成的模型输入。
        出参：三行 JSONL 格式的 genui 字符串。
        """
        logger.info(
            f"a2ui_model_generate_started size={task_spec.size} "
            f"event_count={len(task_spec.eventCandidates)} "
            f"asset_count={len(task_spec.assetCandidates)} use_mock={self.use_mock}"
        )

        if self.use_mock:
            genui = self._generate_from_mock(task_spec, protocol_profile)
            logger.info(
                f"a2ui_model_generate_completed mode=mock path={self.mock_data_path}"
            )
            return genui

        return self._generate_from_real_model(task_spec, protocol_profile, prompt)

    def _generate_from_mock(
        self,
        task_spec: TaskSpec,
        protocol_profile: dict,
    ) -> str:
        """读取并渲染 mock.data 中的 genui 模板。

        入参：
        - task_spec：模型任务输入，用于填充标题、摘要和 DataModel。
        - protocol_profile：A2UI 协议 profile，用于填充版本、catalog 和尺寸。
        出参：替换运行时占位符后的三行 genui JSONL。
        """
        if not self.mock_data_path.is_file():
            raise FileNotFoundError(f"A2UI mock 数据文件不存在: {self.mock_data_path}")

        mock_lines = [
            line.strip()
            for line in self.mock_data_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(mock_lines) != 3:
            raise ValueError("A2UI mock.data 必须恰好包含三行非空 JSONL")

        surface_id = "mock-widget-surface"
        size = protocol_profile["sizes"][task_spec.size]
        replacements: dict[str, Any] = {
            "$version": protocol_profile["version"],
            "$surfaceId": surface_id,
            "$catalogId": protocol_profile["catalogId"],
            "$width": size["width"],
            "$height": size["height"],
            "$borderRadius": 18 if task_spec.size == "2x2" else 22,
            "$title": self._title(task_spec.title, task_spec.userQuery),
            "$description": self._description(
                task_spec.description,
                task_spec.userQuery,
            ),
            "$badge": "AI" if task_spec.size == "2x2" else "AI 卡片",
            "$footerText": (
                "可添加到桌面"
                if task_spec.size == "2x2"
                else "内容已准备，可添加到桌面"
            ),
            "$dataModel": task_spec.dataModel["value"],
        }
        messages = [
            self._replace_mock_tokens(json.loads(line), replacements)
            for line in mock_lines
        ]
        return "\n".join(
            json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            for message in messages
        )

    def _replace_mock_tokens(
        self,
        value: Any,
        replacements: dict[str, Any],
    ) -> Any:
        """递归替换 mock 模板中的运行时占位符。

        入参：
        - value：当前待处理的 JSON 值。
        - replacements：占位符到真实运行时值的映射。
        出参：完成替换后的 JSON 值，原有层级结构保持不变。
        """
        if isinstance(value, dict):
            return {
                key: self._replace_mock_tokens(item, replacements)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._replace_mock_tokens(item, replacements) for item in value]
        if isinstance(value, str) and value in replacements:
            return replacements[value]
        return value

    def _generate_from_real_model(
        self,
        task_spec: TaskSpec,
        protocol_profile: dict,
        prompt: A2UIPromptPayload,
    ) -> str:
        """调用真实 A2UI 模型服务。

        入参：
        - task_spec：模型任务输入。
        - protocol_profile：A2UI 协议 profile。
        - prompt：PromptBuilder 生成的模型输入。
        出参：真实模型返回的三行 genui JSONL。
        """
        # TODO: 安全区补充真实 A2UI 模型请求、鉴权、超时和响应解析逻辑。
        raise NotImplementedError("真实 A2UI 模型调用暂未接入")

    def _title(self, title: str, user_query: str) -> str:
        """从用户需求生成 mock 标题。

        入参：
        - title：主 Agent 建议的卡片标题。
        - user_query：用户原始需求。
        出参：用于 mock DSL 的短标题。
        """
        return title[:18] or user_query[:18] or "桌面卡片"

    def _description(self, description: str, user_query: str) -> str:
        """从卡片说明生成 mock 摘要。

        入参：
        - description：主 Agent 建议的卡片说明。
        - user_query：用户原始需求。
        出参：用于 mock DSL 的短摘要。
        """
        return description[:28] or user_query[:28] or "正在为你刷新最新信息"
