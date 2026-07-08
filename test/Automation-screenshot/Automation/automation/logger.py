"""
日志模块
设计原则：
- 三级日志级别：INFO(控制台+文件) / WARNING(控制台+文件) / ERROR(控制台+文件) / DEBUG(仅文件，--debug开启)
- 多设备自动隔离：每个SN独立日志文件，并行时互不干扰
- 统一格式：时间 [SN] 模块 事件
- 支持控制台实时进度 + 文件完整追溯
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 全局缓存，按日志文件路径缓存 logger 实例
_loggers: dict[str, logging.Logger] = {}

# 统一的日志格式
_LOG_FORMAT = "%(asctime)s [%(sn)s] %(name)s %(levelname)s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class SNFormatter(logging.Formatter):
    """自定义 Formatter，支持 %(sn)s 和 %(qid)s 占位符"""
    def __init__(self, fmt=None, datefmt=None, sn="", qid=""):
        super().__init__(fmt, datefmt)
        self.sn = sn
        self.qid = qid

    def format(self, record):
        record.sn = self.sn
        record.qid = self.qid
        return super().format(record)


def get_logger(
    name: str = "pipeline",
    sn: str = "",
    qid: str = "",
    log_dir: Optional[Path] = None,
    debug: bool = False,
) -> logging.Logger:
    """
    获取一个 logger 实例。
    
    Args:
        name: 模块名，如 "hdc", "xiaoyi", "arkts", "pipeline", "judge", "main"
        sn: 设备SN，用于日志隔离，空字符串表示无设备
        qid: Query ID，用于全链路关联，空字符串表示无关联
        log_dir: 日志文件输出目录，为 None 时仅输出到控制台
        debug: 是否开启 DEBUG 级别
    
    Returns:
        配置好的 logger 实例
    
    缓存策略：同一个 (name, sn, log_dir) 组合只会创建一次 logger。
    """
    log_path = str(log_dir / "pipeline.log") if log_dir else ""
    cache_key = f"{name}|{sn}|{qid}|{log_path}|{debug}"
    
    if cache_key in _loggers:
        return _loggers[cache_key]
    
    logger = logging.getLogger(f"{name}.{sn}" if sn else name)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    
    safe_sn = sn or "default"
    
    # 控制台 handler：INFO 及以上
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(SNFormatter(_LOG_FORMAT, _DATE_FORMAT, safe_sn, qid))
    logger.addHandler(console_handler)
    
    # 文件 handler：写入日志文件
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "pipeline.log"
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        file_handler.setFormatter(SNFormatter(_LOG_FORMAT, _DATE_FORMAT, safe_sn, qid))
        logger.addHandler(file_handler)
    
    _loggers[cache_key] = logger
    return logger


def reset_loggers() -> None:
    """清空 logger 缓存，用于测试或重新初始化"""
    _loggers.clear()