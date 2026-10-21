"""已加桌双卡片与应用入口的同页检查；不执行翻页、加桌或删除。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .commands import DeviceError

SAME_PAGE_MESSAGE = (
    "请将“AI卡片调试”应用入口图标、2x2 和 2x4 卡片放在同一个桌面页面，"
    "停留在该页面并关闭卡片菜单后重试；截图流程不会自动翻页"
)
LOGGER = logging.getLogger(__name__)


class DesktopEnvironmentError(DeviceError):
    """设备环境故障，必须停止后续桌面截图。"""


class Selector(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    attributes: dict[str, str] = Field(min_length=1)


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return self.left + self.width // 2, self.top + self.height // 2

    def contains(self, other: Rect) -> bool:
        horizontal = self.left <= other.left and other.left + other.width <= self.left + self.width
        vertical = self.top <= other.top and other.top + other.height <= self.top + self.height
        return horizontal and vertical

    def overlaps(self, other: Rect) -> bool:
        horizontal = self.left < other.left + other.width and other.left < self.left + self.width
        vertical = self.top < other.top + other.height and other.top < self.top + self.height
        return horizontal and vertical

    def point(self, normalized: tuple[float, float]) -> tuple[int, int]:
        x, y = normalized
        return round(self.left + x * self.width), round(self.top + y * self.height)


@dataclass(frozen=True)
class Node:
    attributes: dict[str, Any]
    children: tuple[Node, ...]

    def matches(self, selector: Selector) -> bool:
        for key, value in selector.attributes.items():
            if self.attributes.get(key) != value:
                return False
        return True

    def flatten(self) -> list[Node]:
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def rect(self) -> Rect:
        bounds = self.attributes.get("bounds")
        if not isinstance(bounds, str):
            raise DesktopEnvironmentError("UiTest 节点缺少物理像素边界")
        numbers = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", bounds)
        if numbers is None:
            raise DesktopEnvironmentError("UiTest 节点边界格式不支持")
        left, top, right, bottom = map(int, numbers.groups())
        invalid_origin = left < 0 or top < 0
        invalid_size = right <= left or bottom <= top
        if invalid_origin or invalid_size:
            raise DesktopEnvironmentError("UiTest 节点边界无效")
        return Rect(left, top, right - left, bottom - top)


def parse_layout(value: Any) -> Node:
    if not isinstance(value, dict):
        raise DesktopEnvironmentError("UiTest 控件树不是对象")
    attributes = value.get("attributes", {})
    children = value.get("children", [])
    if not isinstance(attributes, dict) or not isinstance(children, list):
        raise DesktopEnvironmentError("UiTest 控件树结构无效")
    parsed = []
    for child in children:
        parsed.append(parse_layout(child))
    return Node(attributes, tuple(parsed))


def select(root: Node, selector: Selector) -> Node:
    matches = []
    for node in root.flatten():
        if node.matches(selector):
            matches.append(node)
    if len(matches) != 1:
        raise DesktopEnvironmentError(f"桌面控件定位不唯一：{selector.attributes} / {len(matches)}")
    return matches[0]


class DesktopDriver:
    id = "sceneboard-existing-forms"
    version = "3"
    launcher_bundle = "com.ohos.sceneboard"

    def __init__(self, session: Any, screen: Rect) -> None:
        self.session = session
        self.screen = screen
        self.card: Rect | None = None
        self._inline_layout = True

    async def hdc(self, arguments: list[str]) -> str:
        output = await self.session.devices.hdc(
            self.session.target.serial, arguments, log=self.session.log
        )
        self.session._require_hdc_success(output, "桌面定位")
        return output

    async def layout(self) -> Node:
        started = time.perf_counter()
        if self._inline_layout:
            try:
                root = await self.inline_layout()
            except ValueError as exc:
                LOGGER.info("控件树直接读取不可用，回退文件传输：%s", exc)
                self._inline_layout = False
                root = await self.file_layout()
        else:
            root = await self.file_layout()
        timing = {
            "mode": "inline" if self._inline_layout else "file",
            "elapsedMs": round((time.perf_counter() - started) * 1000, 3),
        }
        with self.session.log.open("a", encoding="utf-8") as stream:
            stream.write(f"A2UI_LAYOUT {json.dumps(timing)}\n")
        return root

    async def inline_layout(self) -> Node:
        remote = f"/data/local/tmp/a2ui-layout-{uuid.uuid4().hex}.json"
        # 路径只含固定前缀和内部UUID，不拼接设备、DSL或用户输入。
        command = (
            f"uitest dumpLayout -p {remote} && cat {remote}; "
            f"result=$?; rm -f {remote}; exit $result"
        )
        output = await self.session.devices.hdc(self.session.target.serial, ["shell", command])
        self.session._require_hdc_success(output, "桌面控件树读取")
        start = output.index("{")
        return parse_layout(json.loads(output[start:]))

    async def file_layout(self) -> Node:
        token = uuid.uuid4().hex
        remote = f"/data/local/tmp/a2ui-layout-{token}.json"
        local = self.session.log.parent / f"layout-{token}.json"
        try:
            await self.hdc(["shell", "uitest", "dumpLayout", "-p", remote])
            await self.hdc(["file", "recv", remote, str(local)])
            return parse_layout(json.loads(local.read_text(encoding="utf-8")))
        finally:
            local.unlink(missing_ok=True)
            await self.hdc(["shell", "rm", "-f", remote])

    @staticmethod
    def desktop(root: Node) -> bool:
        return any(
            item.attributes.get("id") == "SCBDesktop_Flex_Desktop" for item in root.flatten()
        )

    def form_selector(self) -> Selector:
        instance = self.session.instance
        if instance is None:
            raise DesktopEnvironmentError("尚未选择已加桌卡片")
        return Selector(attributes={"description": f"A2UI_FORM:{instance.get('formId')}"})

    def same_page_workspace(self, root: Node) -> Node:
        workspace = select(root, Selector(attributes={"type": "Grid"}))
        info = self.session.project.info
        selectors = [Selector(attributes={"id": f"AppIconCommonView_{info.bundle}.{info.ability}"})]
        for size in ("2x2", "2x4"):
            form = self.session.instances.get(size)
            if form is None:
                raise DesktopEnvironmentError(SAME_PAGE_MESSAGE)
            selectors.append(
                Selector(attributes={"description": f"A2UI_FORM:{form.get('formId')}"})
            )
        page_bounds = workspace.rect()
        for selector in selectors:
            matches = []
            for node in workspace.flatten():
                if node.matches(selector) and node.attributes.get("visible") != "false":
                    matches.append(node)
            if len(matches) != 1:
                raise DesktopEnvironmentError(SAME_PAGE_MESSAGE)
            if not page_bounds.contains(matches[0].rect()):
                raise DesktopEnvironmentError(SAME_PAGE_MESSAGE)
        return workspace

    async def navigate(self) -> Node:
        root = await self.layout()
        if not self.desktop(root):
            # 命令会短暂拉起调试应用；返回可保留桌面原页，Home 会回到默认页。
            bundle = self.session.project.info.bundle
            own_window = any(item.attributes.get("bundleName") == bundle for item in root.flatten())
            key = "Back" if own_window else "Home"
            await self.hdc(["shell", "uitest", "uiInput", "keyEvent", key])
            deadline = time.monotonic() + self.session.config.render_timeout
            while time.monotonic() < deadline:
                root = await self.layout()
                if self.desktop(root):
                    break
                await asyncio.sleep(0.2)
            else:
                raise DesktopEnvironmentError("无法返回桌面，请解锁设备并关闭遮挡窗口")
        self.same_page_workspace(root)
        select(root, self.form_selector())
        return root

    async def navigate_and_inspect(self, *, marker: str | None = None) -> dict[str, Any]:
        root = await self.navigate()
        return self.inspect_root(root, marker=marker)

    async def inspect(self, *, marker: str | None = None) -> dict[str, Any]:
        root = await self.layout()
        return self.inspect_root(root, marker=marker)

    def inspect_root(self, root: Node, *, marker: str | None = None) -> dict[str, Any]:
        if not self.desktop(root):
            raise DesktopEnvironmentError("当前窗口不属于桌面")
        if root.rect() != self.screen:
            raise DesktopEnvironmentError("截图期间屏幕尺寸或方向发生变化")
        for item in root.flatten():
            identity = item.attributes.get("id", "")
            if identity.startswith(("AppMenu_", "HorizontalMenuItem_", "FormManagerTitle_")):
                raise DesktopEnvironmentError("请关闭桌面卡片菜单或选择器后再运行截图")
        workspace = self.same_page_workspace(root)
        target = select(workspace, self.form_selector())
        if self.card is None or self.card != target.rect():
            raise DesktopEnvironmentError("卡片节点与实际边界不一致")
        if marker is not None:
            select(target, Selector(attributes={"description": marker}))
        for item in workspace.children:
            if item.rect().contains(target.rect()):
                continue
            if item.rect().overlaps(self.card):
                raise DesktopEnvironmentError("目标卡片存在遮挡或重叠")
        return {"formBounds": target.rect().__dict__}
