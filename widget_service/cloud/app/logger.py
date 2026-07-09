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
from typing import Any, Callable, List, Optional

import psutil
from loguru import logger as _logger

from app.schema import Message
from config.config import get_settings, LoggingConfig

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

    def _websocket_format(self, record):
        """ WebSocket专用日志格式"""
        task_id = session_id_context.get() or "None"
        page_id = dialog_page_id_context.get() or "None"
        # 简化格式，只保留关键信息
        return (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <5} | {thread.name} | "
            f"{page_id} # {task_id} | {{message}} | {{file.name}}:{{line}}\n"
        )

    def get_user_confirm_plan_time(self):
        """获取当前任务的 user_confirm_plan_time """
        return user_confirm_plan_time_context.get()

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
            logger.error(f"函数执行失败: {json.dumps(error_data, ensure_ascii=False)}")

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

            logger.info(f"开始执行函数: {json.dumps(start_data, ensure_ascii=False)}")

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
                logger.info(f"函数执行成功: {json.dumps(success_data, ensure_ascii=False)}")
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
                logger.error(f"函数执行失败(含性能): {json.dumps(error_perf_data, ensure_ascii=False)}")
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
            logger.info(f"开始执行函数: {json.dumps(start_data, ensure_ascii=False)}")

            try:
                result = func(*args, **kwargs)
                # 记录成功执行
                success_data = _base_log_dict("function_call_success", page_id + "#" + task_id)
                _process_result(success_data, result)
                logger.info(f"函数执行成功: {json.dumps(success_data, ensure_ascii=False)}")
                return result
            except Exception as e:
                _handle_error(page_id + "#" + task_id, e)
                if raise_err:
                    raise e
                return None

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


class LLMCallLogger:
    """LLM 调用日志记录器"""

    def __init__(
            self,
            log_dir: str = os.path.join(PROJECT_ROOT, "llm_logs"),
            log_to_file: bool = True,
            log_to_console: bool = True,
            include_messages: bool = True,
            include_response: bool = True,
            max_message_length: Optional[int] = None,
            max_response_length: Optional[int] = None
    ):
        """
        初始化 LLM 日志记录器

        Args:
            log_dir: 日志文件目录
            log_to_file: 是否写入文件
            log_to_console: 是否输出到控制台
            include_messages: 是否记录完整消息内容
            include_response: 是否记录完整响应内容
            max_message_length: 消息最大记录长度（None表示不限制）
            max_response_length: 响应最大记录长度（None 表示不限制）
        """
        self.log_dir = Path(log_dir)
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console
        self.include_messages = include_messages
        self.include_response = include_response
        self.max_message_length = max_message_length
        self.max_response_length = max_response_length

        if self.log_to_file:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def _truncate_content(self, content: str, max_length: Optional[int]) -> str:
        """截断内容到指定长度"""
        if max_length is None or len(content) <= max_length:
            return content
        return content[:max_length] + f"... (truncated, total length: {len(content)})"

    def _serialize_messages(self, messages: List) -> List:
        """序列化消息列表"""
        if not messages:
            return []

        if isinstance(messages, Message):
            return [messages.to_dict()]

        serialized = []
        for msg in messages:
            if isinstance(msg, dict):
                serialized.append(msg.copy())
            else:
                try:
                    serialized.append(msg.to_dict() if hasattr(msg, 'to_dict') else str(msg))
                except Exception:
                    serialized.append(str(msg))
        return serialized

    def _create_log_entry(self, func, self_instance, args, kwargs):
        """创建基础日志条目"""
        task_id = task_id_context.get() or "None"
        page_id = dialog_page_id_context.get() or "None"

        return {
            "task_id": page_id + "#" + task_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "method": func.__name__,
            "model": getattr(self_instance, 'model', 'unknown llm model'),
            "parameters": {
                "temperature": getattr(self_instance, 'temperature', None),
                "max_tokens": getattr(self_instance, 'max_tokens', None),
                "stream": kwargs.get('stream', True),
            },
            "input": self._get_input_info(kwargs),
            "status": "success",
            "response": {"content": None, "functions": None},
            "execution_time": 0.0
        }

    def _get_input_info(self, kwargs):
        """获取输入信息"""
        input_info = {}
        user_msgs = kwargs.get('messages', [])
        system_msgs = kwargs.get('system_msgs', [])
        tools = kwargs.get('tools', [])

        if self.include_messages:
            input_info["user_msgs"] = self._serialize_messages(user_msgs)
            input_info["system_msgs"] = self._serialize_messages(system_msgs) if system_msgs else ""
            input_info["tools"] = tools
        else:
            input_info["user_msgs_count"] = len(user_msgs)
            input_info["system_msg_count"] = len(system_msgs) if system_msgs else 0
            input_info["user_msgs"] = ""
            input_info["system_msgs"] = ""

        return input_info

    def _record_response(self, log_entry, response):
        """记录响应信息"""
        logger.info(f"LLM response: {response}")
        if "response" not in log_entry:
            log_entry["response"] = {}
        if self.include_response:
            if isinstance(response, tuple):
                log_entry["response"]["content"] = self._truncate_content(
                    response[0],
                    self.max_response_length
                )
                func_list = []
                for func in response[1]:
                    func_list.append({
                        "name": func.function.name,
                        "args": json.loads(func.function.arguments),
                    })
                log_entry["response"]["functions"] = func_list
            else:
                log_entry["response"]["content"] = self._truncate_content(
                    str(response) if not isinstance(response, str) else response,
                    self.max_response_length
                )
        else:
            if isinstance(response, tuple):
                log_entry["response_length"] = sum([len(str(func)) for func in response[1]]) if response[1] else 0
            else:
                log_entry["response_length"] = len(response) if response else 0

        return log_entry

    def _record_error(self, log_entry, e):
        """记录错误信息"""
        log_entry["status"] = "error"
        log_entry["error"] = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        return log_entry

    def _write_log_entry(self, log_entry):
        """写入日志条目"""
        # 输出到控制台
        if self.log_to_console:
            summary = (
                f"Model: {log_entry['model']} | "
                f"Status: {log_entry['status']} | "
                f"Time: {log_entry['execution_time']}s | "
                f"llm response: '{log_entry.get('response', '')}'"
            )

            if log_entry['status'] == 'success':
                logger.info(json.dumps(summary, ensure_ascii=False))
            else:
                logger.error(f"{json.dumps(summary, ensure_ascii=False)} | Error: {log_entry['error']['type']}")

        # 写入文件
        if self.log_to_file:
            log_file = self.log_dir / f"llm_calls_{datetime.now(tz=timezone.utc).strftime('%Y%m%d')}.jsonl"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def __call__(self, func):
        """装饰器实现"""

        @functools.wraps(func)
        async def wrapper(self_instance, *args, **kwargs):
            try:
                start_time = time.time()
                log_entry = self._create_log_entry(func, self_instance, args, kwargs)
                # 调用原始方法
                response = await func(self_instance, *args, **kwargs)
                self._record_response(log_entry, response)
                return response
            except Exception as e:
                self._record_error(log_entry, e)
                raise
            finally:
                # 记录执行时间
                log_entry["execution_time"] = round(time.time() - start_time, 3)
                self._write_log_entry(log_entry)

        return wrapper


class MonitorLogger:
    """监控日志管理器"""

    def __init__(self):
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """设置监控日志格式"""

        # 确保日志目录存在
        log_dir = Path(LoggingConfig.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        def format_with_task_id(record):
            """监控日志格式化函数"""
            task_id = task_id_context.get() or "None"
            return (
                f"{{time:YYYY-MM-DD HH:mm:ss.SSS}} | {task_id} | {{thread.name}} | "
                f"{{message}} | {{file.name}}:{{line}}\n"
            )

        def colorful_format_with_task_id(record):
            """彩色格式化函数"""
            task_id = task_id_context.get() or "None"
            return (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "  # 时间戳(绿色)
                f"<green>{task_id}</green> | "  # 任务id(绿色)
                "<green>{thread.name}</green> | "  # 线程名(绿色)
                "<green> {message} </green> | "  # 日志内容(绿色)
                "<green>{file.name}:{line}</green>\n"  # 文件名和行号(绿色)
            )

        # 控制台输出 - 使用彩色格式
        _logger.add(
            sys.stderr,
            format=colorful_format_with_task_id,
            level="CRITICAL",
            colorize=True,  # 启用彩色输出
            enqueue=True  # 异步安全写入
        )
        # 文件输出 - 按大小轮转
        log_file = os.path.join(log_dir, "monitor_python.log")
        _logger.add(
            str(log_file),
            format=format_with_task_id,
            level="CRITICAL",
            colorize=False,
            enqueue=True,  # 异步安全写入
            backtrace=True,  # 记录异常堆栈
            diagnose=True,  # 显示变量值
            catch=True,  # 捕获日志过程中的异常
            rotation="1024 MB",  # 单个日志文件最大1024MB，超过则轮转
            retention="30 days",  # 保留最近30天的日志
            compression="zip"
        )

        return _logger

    def set_task_id(self, task_id: str):
        """设置当前任务 taskID"""
        task_id_context.set(task_id)

    def get_task_id(self) -> Optional[str]:
        """获取当前任务ID"""
        return task_id_context.get()


# 创建全局监控日志实例
monitor_logger = MonitorLogger()
monitor = monitor_logger.logger


def dict_to_log_message(data_dict):
    """
    将字典转换为日志消息格式

    Args:
        data_dict: 包含监控信息的字典，如{"start":1, "end": 2, "cost" : 3}

    Returns:
        str: 格式化后的日志消息，如"1 | 2 | 3"
    """
    # 提取字段值，如果不存在则使用默认值
    task_time = data_dict.get('taskTime', '')  # 任务完成时长
    agent_name = data_dict.get('agentName', '')  # 调用的agent名
    agent_start_time = data_dict.get('agentStartTime', '')  # agent启动时间
    agent_cost_time = data_dict.get('agentCostTime', '')  # agent结束时间
    input_token = data_dict.get('inputToken', '')  # 输入token消耗
    output_token = data_dict.get('outputToken', '')  # 输出token消耗
    first_token = data_dict.get('firstToken', '')  # 首token时延
    failed_code = data_dict.get('webFailed', '')  # 网络失败码
    fail_type = data_dict.get('failType', '')  # 失败类型
    task_type = data_dict.get('taskType', '')  # 任务类型
    risk_cost_time = data_dict.get('riskCostTime', '')  # 风险触发时任务耗时

    return (f"{task_type} | {task_time} | {failed_code} | {fail_type} | "
            f"{agent_name} | {agent_start_time} | {agent_cost_time} | "
            f"{first_token} | {input_token} | {output_token} | {risk_cost_time}"
            )
