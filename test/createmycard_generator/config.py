"""Configuration helpers for the A2UI batch generator."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_BASE_URL = "https://yunwu.ai"
DEFAULT_TEMPERATURE = None
DEFAULT_MAX_TOKENS = 32768
DEFAULT_TIMEOUT = 120
DEFAULT_DELAY = 1.0
DEFAULT_ITEM_OUTPUT_DIR = "output"


def load_env_file(script_dir: Path = SCRIPT_DIR) -> None:
    """加载 .env/env，覆盖已有环境变量，避免旧 shell 环境污染本次运行。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("提示：未安装 python-dotenv，将使用系统环境变量")
        return

    env_path = script_dir / ".env"
    if not env_path.exists():
        env_path = script_dir / "env"
    if not env_path.exists():
        print("提示：未找到配置文件")
        print("请在脚本目录下创建 '.env' 或 'env' 文件")
        print("格式: ANTHROPIC_AUTH_TOKEN=你的密钥")
        return

    try:
        load_dotenv(env_path, override=True)
        print(f"已加载配置: {env_path.name}")
    except Exception as exc:
        print(f"警告：加载配置文件失败: {exc}")


def load_api_config(config_path: str | Path | None = None) -> dict[str, str]:
    """加载 API 配置，优先级：环境变量 > settings.local.json > 默认值。"""
    config: dict[str, str] = {}
    config_file = Path(config_path or ".claude/settings.local.json")
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            env = data.get("env", {})
            if env.get("ANTHROPIC_BASE_URL"):
                config["base_url"] = env["ANTHROPIC_BASE_URL"]
            if env.get("ANTHROPIC_AUTH_TOKEN"):
                config["auth_token"] = env["ANTHROPIC_AUTH_TOKEN"]
            if env.get("ANTHROPIC_MODEL"):
                config["model"] = env["ANTHROPIC_MODEL"]
        except (json.JSONDecodeError, OSError) as exc:
            print(f"警告：无法读取配置文件 {config_file}：{exc}", file=sys.stderr)

    if os.environ.get("ANTHROPIC_BASE_URL"):
        config["base_url"] = os.environ["ANTHROPIC_BASE_URL"]
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        config["auth_token"] = os.environ["ANTHROPIC_AUTH_TOKEN"]
    if os.environ.get("ANTHROPIC_MODEL"):
        config["model"] = os.environ["ANTHROPIC_MODEL"]

    config.setdefault("base_url", DEFAULT_BASE_URL)
    config.setdefault("model", DEFAULT_MODEL)
    if not config.get("auth_token"):
        sys.exit(
            "错误：未找到 API auth_token。"
            "请在 .env、env、.claude/settings.local.json 中配置或设置环境变量 ANTHROPIC_AUTH_TOKEN。"
        )
    return config


def mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "***"
    return f"{secret[:4]}...{secret[-4:]}"


def resolve_path(path: str | Path, base_dir: Path = SCRIPT_DIR) -> Path:
    resolved = Path(path)
    return resolved if resolved.is_absolute() else base_dir / resolved


def disable_proxy_env() -> None:
    """禁用代理环境变量，避免部分环境下出现 ProxyError。"""
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(key, None)
