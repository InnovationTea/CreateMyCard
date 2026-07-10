# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from pathlib import Path

from app.logger import logger
from config.config import get_settings
from models.generation import TaskSpec
from models.service import A2UIPromptPayload


class A2UIModelClient:
    """A2UI 模型调用客户端。

    mock 开关打开时直接返回同目录 mock.dat 的原始内容；
    关闭时进入预留的真实模型调用入口。
    """

    def __init__(
        self,
        use_mock: bool | None = None,
        mock_data_path: str | Path | None = None,
    ) -> None:
        """初始化 A2UI 模型客户端。

        入参：
        - use_mock：是否使用 mock 数据；不传时读取全局配置。
        - mock_data_path：可选 mock 文件路径；不传时读取本文件同级 mock.dat。
        出参：无。
        """
        settings = get_settings()
        self.use_mock = (
            settings.enable_a2ui_model_mock if use_mock is None else use_mock
        )
        self.mock_data_path = Path(mock_data_path or Path(__file__).with_name("mock.dat"))

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
        出参：A2UI genui JSONL 字符串。
        """
        logger.info(
            f"a2ui_model_generate_started size={task_spec.size} "
            f"event_count={len(task_spec.eventCandidates)} "
            f"asset_count={len(task_spec.assetCandidates)} use_mock={self.use_mock}"
        )

        if self.use_mock:
            return self._load_mock_data()

        return self._generate_from_real_model(task_spec, protocol_profile, prompt)

    def _load_mock_data(self) -> str:
        """直接读取 mock.dat 原始内容。

        入参：无。
        出参：mock.dat 的完整 UTF-8 文本，不做替换或结构调整。
        """
        if not self.mock_data_path.is_file():
            raise FileNotFoundError(f"A2UI mock 数据文件不存在: {self.mock_data_path}")

        mock_data = self.mock_data_path.read_text(encoding="utf-8")
        logger.info(
            f"a2ui_model_generate_completed mode=mock path={self.mock_data_path}"
        )
        return mock_data

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
        出参：真实模型返回的 genui JSONL。
        """
        # TODO: 安全区补充真实 A2UI 模型请求、鉴权、超时和响应解析逻辑。
        raise NotImplementedError("真实 A2UI 模型调用暂未接入")
