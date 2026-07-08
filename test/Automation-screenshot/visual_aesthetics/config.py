"""
审美打分模块配置
和现有Automation配置体系完全兼容，支持命令行参数>环境变量>默认值三层优先级
"""
from dataclasses import dataclass
from pathlib import Path
import os
from typing import Optional

@dataclass(frozen=True)
class AestheticsConfig:
    enable: bool = False
    base_url: str = ""
    api_key: str = ""
    model: str = "doubao-seed-2-0-lite"
    output_mode: str = "full"  # full/score-only
    timeout: int = 360
    max_retries: int = 3
    max_tokens: int = 1200
    temperature: float = 0.0
    enable_cache: bool = False  # 是否开启本地缓存，相同MD5的图片不用重复打分
    cache_dir: Path = Path(".")  # 注意：必须通过 from_env/from_args 设置正确路径
    max_workers: int = 2  # 打分最大并发数
    fail_fast: bool = False  # 打分失败是否中断主流程
    
    @classmethod
    def from_env(cls, project_root: Path = None) -> "AestheticsConfig":
        """从环境变量加载配置"""
        if project_root is None:
            project_root = Path(__file__).parent.parent
        cache_dir = project_root / "Automation" / ".work" / "aesthetics_cache"
        return cls(
            base_url=os.environ.get("AESTHETICS_BASE_URL", ""),
            api_key=os.environ.get("AESTHETICS_API_KEY", ""),
            model=os.environ.get("AESTHETICS_MODEL", "doubao-seed-2-0-lite"),
            output_mode=os.environ.get("AESTHETICS_OUTPUT_MODE", "full"),
            timeout=int(os.environ.get("AESTHETICS_TIMEOUT", "360")),
            max_retries=int(os.environ.get("AESTHETICS_MAX_RETRIES", "3")),
            max_tokens=int(os.environ.get("AESTHETICS_MAX_TOKENS", "1200")),
            temperature=float(os.environ.get("AESTHETICS_TEMPERATURE", "0.0")),
            enable_cache=os.environ.get("AESTHETICS_ENABLE_CACHE", "false").lower() == "true",
            cache_dir=Path(os.environ.get("AESTHETICS_CACHE_DIR", str(cache_dir))),
            max_workers=int(os.environ.get("AESTHETICS_MAX_WORKERS", "2")),
            fail_fast=os.environ.get("AESTHETICS_FAIL_FAST", "false").lower() == "true"
        )
    
    @classmethod
    def from_args(cls, args, project_root: Path = None) -> "AestheticsConfig":
        """从命令行参数加载配置，优先级高于环境变量"""
        env_config = cls.from_env(project_root)
        def arg_or_env(name: str, env_value):
            value = getattr(args, name, None)
            return env_value if value is None else value

        return cls(
            enable=getattr(args, "enable_aesthetics", False),
            base_url=arg_or_env("aesthetics_base_url", env_config.base_url),
            api_key=arg_or_env("aesthetics_api_key", env_config.api_key),
            model=arg_or_env("aesthetics_model", env_config.model),
            output_mode=arg_or_env("aesthetics_output_mode", env_config.output_mode),
            timeout=arg_or_env("aesthetics_timeout", env_config.timeout),
            max_retries=arg_or_env("aesthetics_max_retries", env_config.max_retries),
            max_tokens=arg_or_env("aesthetics_max_tokens", env_config.max_tokens),
            temperature=arg_or_env("aesthetics_temperature", env_config.temperature),
            enable_cache=getattr(args, "aesthetics_enable_cache", env_config.enable_cache),
            cache_dir=getattr(args, "aesthetics_cache_dir", env_config.cache_dir),
            max_workers=arg_or_env("aesthetics_max_workers", env_config.max_workers),
            fail_fast=getattr(args, "aesthetics_fail_fast", env_config.fail_fast)
        )
    
    def to_model_config(self) -> dict:
        """转换成模型初始化配置"""
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "model": self.model,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "output_mode": self.output_mode
        }

