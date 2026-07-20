# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import functools
import json
import os
import sys
import threading
import time
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import psutil
from loguru import logger as _logger

from config.config import get_settings, LoggingConfig

_MODULE = "[Logger]"

# 创建上下文变量来存储task ID
task_id_context: ContextVar[Optional[str]] = ContextVar('task_id', default=None)
session_id_context: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
interaction_id_context: ContextVar[Optional[str]] = ContextVar('interaction_id', default=None)
message_id_context: ContextVar[Optional[str]] = ContextVar('message_id', default=None)
message_content_context: ContextVar[Optional[str]] = ContextVar('message_content', default=None)
package_name_context: ContextVar[Optional[str]] = ContextVar('package_name', default=None)
ip_address_context: ContextVar[Optional[str]] = ContextVar('ip_address', default=None)
device_id_context: ContextVar[Optional[str]] = ContextVar('device_id', default=None)
u_id_context: ContextVar[Optional[str]] = ContextVar('u_id', default=None)
client_version_context: ContextVar[Optional[str]] = ContextVar('client_version', default=None)
phone_type_context: ContextVar[Optional[str]] = ContextVar('phone_type', default=None)
device_type_context: ContextVar[Optional[str]] = ContextVar('device_type', default=None)
device_model_context: ContextVar[Optional[str]] = ContextVar('device_model', default=None)
dialog_page_id_context: ContextVar[Optional[str]] = ContextVar('dialog_page_id', default="")
deepsearch_plan_context: ContextVar[Optional[dict]] = ContextVar('deepsearch_plan', default={})
user_confirm_plan_time_context: ContextVar[Optional[float]] = ContextVar('user_confirm_plan_time', default=None)
session_info_content: ContextVar[Optional[dict]] = ContextVar('session_info', default={})
system_device_content: ContextVar[Optional[dict]] = ContextVar('system_device', default={})
country_code_content: ContextVar[Optional[str]] = ContextVar('country_code', default="")
is_multi_rounds_succession_content: ContextVar[Optional[bool]] = ContextVar('is_multi_rounds_succession', default=False)
historical_task_records_content: ContextVar[Optional[list]] = ContextVar('historical_task_records', default=[])
generated_image_urls_content: ContextVar[Optional[list]] = ContextVar('generated_image_urls', default=[])
task_info_multi_round_context: ContextVar[Optional[dict]] = ContextVar('task_info_multi_round', default={})
task_info_mutil_round_url_context: ContextVar[Optional[str]] = ContextVar('task_info_mutil_round_url', default="")
agent_id_content: ContextVar[Optional[str]] = ContextVar('agent_id', default=None)
is_unmanned_context: ContextVar[Optional[bool]] = ContextVar('is_unmanned', default=False)

PROJECT_ROOT = get_settings().PROJECT_ROOT
PRINT_LEVEL = "INFO"


def _json_log_default(value: Any) -> Any:
    """把常见 Python 对象转换为可写入日志的 JSON 值。"""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    return str(value)


def _is_sensitive_identifier_log_key(key: Any) -> bool:
    """判断结构化日志键是否承载用户或设备标识。"""
    normalized = "".join(
        character for character in str(key).casefold() if character.isalnum()
    )
    return normalized in {"uid", "userid", "useruid", "callinguid", "odid"}


def _sanitize_json_log_value(value: Any) -> Any:
    """递归移除用户 UID、服务调用 UID 和设备 odid 字段。"""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        sanitized = {
            key: _sanitize_json_log_value(item)
            for key, item in value.items()
            if not _is_sensitive_identifier_log_key(key)
        }
        location = value.get("loc")
        if isinstance(location, (list, tuple)) and any(
            _is_sensitive_identifier_log_key(item) for item in location
        ):
            sanitized.pop("input", None)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize_json_log_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_sanitize_json_log_value(item) for item in value),
            key=str,
        )
    return value


def json_for_log(value: Any) -> str:
    """将结构化日志字段序列化为紧凑的标准 JSON。"""
    return json.dumps(
        _sanitize_json_log_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_log_default,
    )


class TaskLogger:
    """任务日志管理器"""

    def __init__(self):
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """设置日志格式, 包含taskID"""
        # 移除默认处理器
        _logger.remove()

        # 确保日志目录存在
        log_dir = Path(LoggingConfig.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        def format_with_task_id(record):
            session_id = session_id_context.get() or "None"
            page_id = dialog_page_id_context.get() or "None"
            return (
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <5} | {thread.name} | "
                f"{page_id} # {session_id} | {{message}} | {{file.name}}:{{line}}\n"
            )

        def colorful_format_with_task_id(record):
            """彩色格式化函数"""
            session_id = session_id_context.get() or "None"
            page_id = dialog_page_id_context.get() or "None"
            return (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <5}</level> | "
                "<cyan>{thread.name}</cyan> | "
                f"<magenta>{page_id} # {session_id}</magenta> | "
                "<level>{message}</level> | "
                "<blue>{file.name}:{line}</blue>\n"
            )

        # 控制台输出 : 使用彩色格式
        _logger.add(
            sys.stderr,
            format=colorful_format_with_task_id,
            level=PRINT_LEVEL,
            colorize=True,  # 启用彩色输出
            enqueue=True  # 异步安全写入
        )

        # 文件输出 - 按大小轮转
        current_date = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        if get_settings().LOCAL_FLAG:
            log_file = os.path.join(log_dir, f"agent_{current_date}.log")
        else:
            log_file = os.path.join(log_dir, "debug_python.log")
        _logger.add(
            str(log_file),
            format=format_with_task_id,
            level=PRINT_LEVEL,
            colorize=False,
            enqueue=True,  # 异步安全写入
            backtrace=True,  # 记录异常堆栈
            diagnose=True,  # 显示变量值
            catch=True,  # 捕获日志过程中的异常
            rotation="100 MB",  # 单个日志文件最大100 MB，超过则轮转
            retention="30 days",  # 保留最近 30天的日志
            compression="zip"
        )

        return _logger

    def set_task_id(self, task_id: str):
        """设置当前任务 task ID"""
        task_id_context.set(task_id)

    def set_session_id(self, session_id: str):
        """设置当前任务 sessionID"""
        session_id_context.set(session_id)

    def set_interaction_id(self, interaction_id: str):
        """设置当前任务 interaction ID"""
        interaction_id_context.set(interaction_id)

    def set_message_id(self, message_id: str):
        """设置当前任务 message ID"""
        message_id_context.set(message_id)

    def set_message_content(self, message_content: str):
        """设置当前任务 message Content"""
        message_content_context.set(message_content)

    def set_package_name(self, package_name: str):
        """设置当前用户设备的 package name"""
        package_name_context.set(package_name)

    def set_ip_address(self, ip_address: str):
        """设置当前用户设备的 ip address"""
        ip_address_context.set(ip_address)

    def set_device_id(self, device_id: str):
        """设置当前任务的 device id"""
        device_id_context.set(device_id)

    def set_u_id(self, u_id: str):
        """设置当前用户设备的 uid """
        u_id_context.set(u_id)

    def set_client_version(self, client_version: str):
        """设置当前用户设备的 客户端版本"""
        client_version_context.set(client_version)

    def set_phone_type(self, phone_type: str):
        """设置当前任务的客户设备机型"""
        phone_type_context.set(phone_type)

    def set_device_model(self, device_model: str):
        device_model_context.set(device_model)

    def set_is_unmanned(self, is_unmanned: bool):
        is_unmanned_context.set(is_unmanned)

    def set_device_type(self, device_type: str):
        """设置当前任务的客户设备机型"""
        device_type_context.set(device_type)

    def set_dailog_page_id(self, dialog_page_id: str):
        """设置当前任务的页面Id"""
        dialog_page_id_context.set(dialog_page_id)

    def set_deepsearch_plan(self, query, deepsearch_plan):
        """设置当前任务的  deepsearch-plan """
        current_dict = deepsearch_plan_context.get().copy()
        current_dict[query] = deepsearch_plan
        deepsearch_plan_context.set(current_dict)

    def set_user_confirm_plan_time(self, confirm_time: float):
        user_confirm_plan_time_context.set(confirm_time)

    def set_session_info(self, session_info):
        """设置当前任务 sessionInfo """
        session_info_content.set(session_info)

    def set_system_device(self, system_device):
        """设置当前任务的 system_device """
        system_device_content.set(system_device)

    def set_country_code(self, country_code: str):
        """设置当前任务的 country_code """
        country_code_content.set(country_code)

    def set_is_multi_rounds_succession(self, is_multi_rounds_succession: bool):
        """设置当前任务的 is_multi_rounds_succession """
        is_multi_rounds_succession_content.set(is_multi_rounds_succession)

    def set_historical_task_records(self, historical_task_records: list):
        """设置当前任务的historical_task_records"""
        historical_task_records_content.set(historical_task_records)

    def set_generated_image_urls(self, generated_image_urls: list):
        """设置当前任务的 generated_image_urls"""
        generated_image_urls_content.set(generated_image_urls)

    def set_task_info_multi_round(self, task_info_multi_round):
        """设置当前任务的task_info_multi_round用于存储"""
        task_info_multi_round_context.set(task_info_multi_round)

    def set_task_info_mutil_round_url(self, task_info_mutil_round_url):
        """设置当前任务的 task_info_mutil_round_url 用于存储"""
        task_info_mutil_round_url_context.set(task_info_mutil_round_url)

    def set_agent_id(self, agent_id: str):
        """设置当前任务的 agent id用于存储"""
        agent_id_content.set(agent_id)

    def get_deepsearch_plan(self) -> Optional[dict]:
        """获取当前任务的 deepsearch-plan"""
        return deepsearch_plan_context.get().copy()

    def get_task_id(self) -> Optional[str]:
        """获取当前任务ID"""
        return task_id_context.get()

    def get_session_id(self) -> Optional[str]:
        """获取当前任务 session ID"""
        return session_id_context.get()

    def get_interaction_id(self) -> Optional[str]:
        """获取当前任务 interaction ID"""
        return interaction_id_context.get()

    def get_message_id(self) -> Optional[str]:
        """获取当前任务 message ID"""
        return message_id_context.get()

    def get_message_content(self) -> Optional[str]:
        """获取当前任务 message Content"""
        message_content = message_content_context.get()
        return message_content if isinstance(message_content, str) else "Default Query"

    def get_package_name(self) -> Optional[str]:
        """获取当前用户手机的 package(包）name"""
        return package_name_context.get()

    def get_ip_address(self) -> Optional[str]:
        """获取当前用户手机的 ip address"""
        return ip_address_context.get()

    def get_device_id(self) -> Optional[str]:
        """获取当前任务的 device id"""
        return device_id_context.get()

    def get_u_id(self) -> Optional[str]:
        """获取当前设备的 uid"""
        return u_id_context.get()

    def get_client_version(self) -> Optional[str]:
        """获取当前任务的客户端版本"""
        return client_version_context.get()

    def get_phone_type(self) -> Optional[str]:
        """获取当前任务的客户设备机型"""
        return phone_type_context.get()

    def get_is_unmanned(self) -> Optional[bool]:
        return bool(is_unmanned_context.get())

    def get_device_type(self) -> Optional[str]:
        """获取当前任务的客户设备机型"""
        return device_type_context.get()

    def get_dialog_page_id(self) -> Optional[str]:
        """获取当前任务的页面Id"""
        return dialog_page_id_context.get()

    def get_user_confirm_plan_time(self):
        return user_confirm_plan_time_context.get()

    def get_is_multi_rounds_succession(self):
        """获取当前任务的 is_multi_rounds_succession """
        return is_multi_rounds_succession_content.get()

    def get_historical_task_records(self):
        """设置当前任务的 historical_task_records"""
        return historical_task_records_content.get()

    def get_generated_image_urls(self):
        """获取当前任务的 generated_image_urls"""
        return generated_image_urls_content.get()

    def get_task_info_multi_round(self):
        """获取当前任务的task_info_multi_round用于存储"""
        return task_info_multi_round_context.get()

    def get_task_info_mutil_round_url(self):
        """获取当前任务的task_info_mutil_round_url"""
        return task_info_mutil_round_url_context.get()

    def get_agent_id(self):
        """获取当前任务的 agent id 用于存储"""
        return agent_id_content.get()

    def get_session_info(self):
        """设置当前任务 session Info """
        return session_info_content.get()

    def get_system_device(self):
        """设置当前任务 system_device """
        return system_device_content.get()

    def get_country_code(self):
        """设置当前任务 country_code"""
        return country_code_content.get()

    def get_device_model(self):
        """获取设备模型"""
        return device_model_context.get()


# 创建全局任务日志实例
task_logger = TaskLogger()
logger = task_logger.logger


def log_func(func_name: Optional[str] = None, log_args: bool = True, log_result: bool = True, raise_err: bool = True):
    """
    任务日志装饰器, 支持同步和异步函数

    Args:
        func_name: 自定义函数名称，默认使用函数实际名称
        log_args: 是否记录函数参数
        log_result: 是否记录函数返回值
        raise_err: 是否向上抛出异常信息，如果否仅记录日志
    """

    def decorator(func: Callable) -> Callable:
        """普通函数装饰器"""
        name = func_name or func.__name__
        module = func.__module__

        # 构建基础日志字典
        def _base_log_dict(type_str: str, task_id: str) -> dict:
            return {
                "module": module,
                "function": name,
                "task_id": task_id,
                "type": type_str
            }

        # 序列化函数参数
        def _serialize_args(log_data: dict, args: tuple, kwargs: dict) -> None:
            if not log_args:
                return
            try:
                log_data["kwargs"] = {k: str(v) for k, v in kwargs.items()}
            except Exception as e:
                log_data["args_error"] = f"Failed to serialize args: {str(e)}"

        # 处理并记录函数结果
        def _process_result(log_data: dict, result: Any) -> None:
            """处理结果"""
            if not log_result:
                return
            try:
                result_str = str(result)
                log_data["result"] = result_str[:2048] + "（剩余部分超出长度，已截断）" \
                    if len(result_str) >= 2048 else result_str
            except Exception:
                log_data["result"] = "Result serialization failed"

        # 处理异常情况
        def _handle_error(task_id: str, e: Exception) -> None:
            error_data = _base_log_dict("function_call_error", task_id)
            error_data.update({
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            logger.error(f"{_MODULE} 函数执行失败: {json.dumps(error_data, ensure_ascii=False)}")

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # ===== 新增：性能监控开始 =====
            process = psutil.Process()
            start_time = time.time()
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            start_threads = threading.active_count()
            start_connections = len(psutil.net_connections())
            """异步"""
            task_id = task_id_context.get() or "None"
            page_id = dialog_page_id_context.get() or "None"
            # 记录开始执行
            start_data = _base_log_dict("function_call_start", page_id + "#" + task_id)
            _serialize_args(start_data, args, kwargs)
            start_data.update({
                "start_memory_mb": round(start_memory, 2),
                "start_threads": start_threads,
                "start_connections": start_connections
            })

            logger.info(f"{_MODULE} 开始执行函数: {json.dumps(start_data, ensure_ascii=False)}")

            try:
                result = await func(*args, **kwargs)
                # ===== 新增：性能监控结束 =====
                end_time = time.time()
                end_memory = process.memory_info().rss / 1024 / 1024
                end_threads = threading.active_count()
                end_connections = len(psutil.net_connections())

                execution_time = round(end_time - start_time, 4)
                memory_delta = round(end_memory - start_memory, 2)
                thread_delta = end_threads - start_threads
                connection_delta = end_connections - start_connections
                # 记录成功执行
                success_data = _base_log_dict("function_call_success", page_id + "#" + task_id)
                _process_result(success_data, result)
                # 新增：添加性能结束数据
                success_data.update({
                    "execution_time_s": execution_time,
                    "end_memory_mb": round(end_memory, 2),
                    "memory_delta_mb": memory_delta,
                    "end_threads": end_threads,
                    "thread_delta": thread_delta,
                    "end_connections": end_connections,
                    "connection_delta": connection_delta
                })
                logger.info(f"{_MODULE} 函数执行成功: {json.dumps(success_data, ensure_ascii=False)}")
                return result
            except Exception as e:
                # ===== 新增：错误时的性能数据 =====
                end_time = time.time()
                end_memory = process.memory_info().rss / 1024 / 1024
                execution_time = round(end_time - start_time, 4)

                _handle_error(f"{page_id}#{task_id}", e)
                if raise_err:
                    raise e

                # 记录错误时的性能数据
                error_perf_data = {
                    "event": "function_call_error_with_perf",
                    "identifier": f"{page_id}#{task_id}",
                    "execution_time_s": execution_time,
                    "memory_used_mb": round(end_memory - start_memory, 2),
                    "error_timestamp": time.time()
                }
                logger.error(f"{_MODULE} 函数执行失败(含性能): {json.dumps(error_perf_data, ensure_ascii=False)}")
                # ===== 新增结束 =====
                return None

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            """同步"""
            task_id = task_id_context.get()
            page_id = dialog_page_id_context.get() or "None"
            # 记录开始执行
            start_data = _base_log_dict("function_call_start", page_id + "#" + task_id)
            _serialize_args(start_data, args, kwargs)
            logger.info(f"{_MODULE} 开始执行函数: {json.dumps(start_data, ensure_ascii=False)}")

            try:
                result = func(*args, **kwargs)
                # 记录成功执行
                success_data = _base_log_dict("function_call_success", page_id + "#" + task_id)
                _process_result(success_data, result)
                logger.info(f"{_MODULE} 函数执行成功: {json.dumps(success_data, ensure_ascii=False)}")
                return result
            except Exception as e:
                _handle_error(page_id + "#" + task_id, e)
                if raise_err:
                    raise e
                return None

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator






