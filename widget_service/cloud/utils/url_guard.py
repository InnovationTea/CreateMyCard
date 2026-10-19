# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""远端 URL 拉取的 SSRF 防护。

服务端会按用户可控 URL（如 sourceArtifactUrl）主动发起 HTTP 下载，
必须在请求前校验协议与目标地址，防止：
- 借服务端探测内网（10/8、172.16/12、192.168/16 等）
- 访问云元数据服务（169.254.169.254）
- 访问本机端口（127.0.0.1、::1）
- 非预期协议（file/ftp/gopher/data）

配置：``download.allowed.host.suffixes``（逗号分隔域名后缀，
默认 ``.myhuaweicloud.com``）。配置非空时走白名单模式（最稳），
未配置时回退黑名单模式（DNS 解析后逐 IP 校验私网/保留段）。
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

_MODULE = "[URL Guard]"

ALLOWED_SCHEMES = {"http", "https"}


class UrlBlockedError(ValueError):
    """URL 未通过 SSRF 校验。"""


def _is_forbidden_ip(ip: str) -> bool:
    """私网/环回/链路本地/保留地址一律拒绝，解析失败也视为不安全。"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def validate_url_for_ssrf(url: str, allowed_host_suffixes: tuple[str, ...] = ()) -> None:
    """校验下载 URL，不通过抛 UrlBlockedError。

    - 协议白名单：仅 http/https
    - 主机白名单模式（配了 allowed_host_suffixes）：域名后缀必须命中，IP 字面量一律拒
    - 主机黑名单模式（未配白名单）：DNS 解析出的所有 IP 必须为公网地址
    """
    parsed = urlsplit(str(url))
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UrlBlockedError(f"仅允许 http/https 协议: {url}")
    hostname = parsed.hostname
    if not hostname:
        raise UrlBlockedError(f"URL 缺少主机名: {url}")

    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        addr = None
    if addr is not None:
        # IP 字面量直连：无域名可校验，直接按私网/保留地址规则拒
        if _is_forbidden_ip(str(addr)):
            raise UrlBlockedError(f"目标为私网/保留 IP，已拒绝: {hostname}")

    if allowed_host_suffixes:
        lowered = hostname.lower()
        for suffix in allowed_host_suffixes:
            if lowered == suffix or lowered.endswith(suffix):
                return
        raise UrlBlockedError(f"域名不在白名单: {hostname}")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise UrlBlockedError(f"主机解析失败: {hostname}") from exc
    for info in infos:
        ip = info[4][0]
        if _is_forbidden_ip(ip):
            raise UrlBlockedError(
                f"目标地址为私网/保留地址，已拒绝: {hostname} -> {ip}"
            )
