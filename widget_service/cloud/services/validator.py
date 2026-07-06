import importlib.util
import json
from types import ModuleType
from typing import Any

from core.config import get_settings
from core.logger import get_logger
from models.artifact import WidgetArtifact

logger = get_logger(__name__)


class ArtifactValidator:
    def __init__(self) -> None:
        """初始化 artifact 校验器。

        入参：无。
        出参：无；实例会定位 datamodel-first skill 的 validate_card.py，
        后续校验直接复用该脚本逻辑。
        """
        # validate_card.py 是当前 datamodel-first skill 的权威静态校验脚本，
        # 服务侧只做适配，不复制规则。
        self.settings = get_settings()
        self.validator_script_path = (
            self.settings.repo_root
            / "skills"
            / "harmony-card-generation-datamodel-first"
            / "scripts"
            / "validate_card.py"
        )
        self._validator_module: ModuleType | None = None

    def validate(self, artifact: WidgetArtifact, protocol_profile: dict) -> list[str]:
        """校验完整 artifact。

        入参：
        - artifact：待校验的完整卡片产物。
        - protocol_profile：当前 A2UI 协议 profile。
        出参：错误信息列表；空列表表示校验通过。
        """
        # 校验入口仍接收完整 artifact，但具体协议、组件、布局和绑定规则全部交给 skill 脚本处理。
        logger.info(
            "artifact_validation_started",
            protocol_profile_id=protocol_profile["id"],
            validator_script=str(self.validator_script_path),
        )

        try:
            validator = self._load_validator_module()
            reporter = validator.Reporter()

            # 复用 skill 脚本的 JSONL 解析逻辑，保证行数、JSON 对象形状和错误文案与脚本一致。
            messages = validator.load_jsonl(artifact.genui, reporter)
            # CardSpec 也通过脚本的 JSON 加载方法进入校验，保持 CLI 和服务侧解析口径一致。
            card_spec = validator.load_cardspec(
                json.dumps(artifact.cardSpec, ensure_ascii=False),
                reporter,
            )
            if len(messages) >= 3:
                # check_protocol 会校验消息顺序、版本、surface、catalog、
                # 尺寸和 CardSpec 点击行为边界。
                _, update_components, update_data_model = validator.check_protocol(
                    messages,
                    card_spec,
                    reporter,
                )
                if update_components:
                    # check_components 会校验组件白名单、children、事件、
                    # 绑定、样式、文本和布局风险。
                    validator.check_components(
                        update_components,
                        update_data_model,
                        card_spec,
                        reporter,
                    )
        except Exception as exc:
            # 动态加载或脚本执行异常属于服务侧校验链路异常，需要返回为校验失败，避免产物绕过校验。
            errors = [f"validator execution failed: {exc}"]
            logger.error(
                "artifact_validation_failed",
                errors=errors,
                validator_script=str(self.validator_script_path),
            )
            return errors

        errors = self._normalize_messages(reporter.errors)
        warnings = self._normalize_messages(reporter.warnings)
        if errors:
            logger.error(
                "artifact_validation_failed",
                errors=errors,
                warnings=warnings,
            )
        else:
            logger.info(
                "artifact_validation_completed",
                warning_count=len(warnings),
                warnings=warnings,
            )
        return errors

    def _load_validator_module(self) -> ModuleType:
        """加载 datamodel-first skill 的 validate_card.py。

        入参：无。
        出参：已加载的 Python module；包含 Reporter、load_jsonl、
        load_cardspec、check_protocol、check_components 等脚本方法。
        """
        # 同一个 ArtifactValidator 实例内缓存 module，避免一次生成重试过程中重复解析脚本文件。
        if self._validator_module is not None:
            return self._validator_module
        if not self.validator_script_path.exists():
            raise FileNotFoundError(f"validator script not found: {self.validator_script_path}")

        spec = importlib.util.spec_from_file_location(
            "harmony_card_generation_datamodel_first_validate_card",
            self.validator_script_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load validator script: {self.validator_script_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._assert_validator_contract(module)
        self._validator_module = module
        return module

    def _assert_validator_contract(self, module: ModuleType) -> None:
        """确认被复用脚本暴露服务所需的方法。

        入参：
        - module：动态加载到的 validate_card.py module。
        出参：无；缺少方法时抛出异常，让调用方按校验失败处理。
        """
        # 这里不重新实现任何校验规则，只确认脚本 API 足够支撑服务侧适配。
        required_names = [
            "Reporter",
            "load_jsonl",
            "load_cardspec",
            "check_protocol",
            "check_components",
        ]
        missing_names = [name for name in required_names if not hasattr(module, name)]
        if missing_names:
            raise AttributeError(f"validator script missing methods: {missing_names}")

    def _normalize_messages(self, messages: list[Any]) -> list[str]:
        """归一化校验脚本返回的问题列表。

        入参：
        - messages：Reporter 中的 errors 或 warnings。
        出参：字符串列表，便于日志和响应统一处理。
        """
        # Reporter 当前返回字符串；保留兜底转换，方便脚本后续扩展结构化问题对象时服务不中断。
        return [str(message) for message in messages]
