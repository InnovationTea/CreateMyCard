#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调用 GenUI Agent MQ 触发接口，发送 DMQ 消息。
"""

import uuid

import requests
import platform

from app.logger import logger, task_logger
from config.config import get_container_ip, Settings

TRIGGER_PATH = "/genui/agent/mq/trigger"


def trigger_mq(body: dict, port: int = 8080, host: str = None, session_id: str = None):
    """调用 MQ 触发接口，记录响应日志

    Args:
        body: DMQ消息体，指标字段子集
        port: 服务端口
        host: 服务地址，Windows 默认 127.0.0.1，容器默认取 get_container_ip()
        session_id: 会话标识，作为DMQ消息key；为None时自动生成UUID
    """

    session_id = task_logger.get_session_id()
    if not Settings().ai_widget_data_huashan_enable:
        logger.info("MQ 推送已关闭：ai_widget_data_huashan_enable=False")
        return

    if session_id is None:
        session_id = str(uuid.uuid4())

    if platform.system() == "Windows":
        host = "127.0.0.1"

    if host is None:
        host = get_container_ip()

    url = f"http://{host}:{port}{TRIGGER_PATH}"
    headers = {"Content-Type": "application/json"}
    payload = {"sessionId": session_id, "body": body}

    try:
        logger.info(f"MQ trigger, sessionId={session_id}, payload={payload}")
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f"MQ trigger success, response={resp.json()}")
    except Exception as e:
        logger.error(f"MQ trigger failed, sessionId={session_id}, host={host}, error={e}")