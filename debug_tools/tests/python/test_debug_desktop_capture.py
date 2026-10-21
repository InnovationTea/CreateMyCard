from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from debug_tools.device_debug.api import PrepareRequest, RunRequest
from debug_tools.device_debug.commands import DeviceError
from debug_tools.device_debug.desktop import (
    DesktopCommandError,
    DesktopRenderSession,
    desktop_envelope,
    parse_desktop_events,
    physical_rect,
)
from debug_tools.device_debug.desktop_ui import (
    DesktopDriver,
    DesktopEnvironmentError,
    Rect,
    parse_layout,
)
from debug_tools.device_debug.locks import DeviceProcessLock
from debug_tools.postprocess_plugins.gallery.report import compatible_capture
from PIL import Image

DSL = '{"version":"v0.9","createSurface":{"surfaceId":"test"}}'
SMALL = {"formId": "small", "dimension": 2}
LARGE = {"formId": "large", "dimension": 3}


def screen_reply(**changes):
    return {
        "density": 2.0,
        "displayWidth": 1000,
        "displayHeight": 1000,
        "rotation": 0,
        "rectVp": {"left": 0, "top": 0, "width": 200, "height": 200},
        **changes,
    }


class MemoryDriver:
    id = "readonly"
    version = "2"

    def __init__(self, *_args):
        self.card = Rect(0, 0, 400, 400)
        self.navigations = 0

    async def navigate(self):
        self.navigations += 1

    async def inspect(self, *, marker=None):
        return {"formBounds": self.card.__dict__}

    async def navigate_and_inspect(self, *, marker=None):
        await self.navigate()
        return await self.inspect(marker=marker)


class MemorySession(DesktopRenderSession):
    def __init__(self, root):
        self.config = SimpleNamespace(
            output=root, project=root, render_timeout=0.01, capture_attempts=6
        )
        self.target = SimpleNamespace(id="device", serial="one")
        self.driver = MemoryDriver()
        self.instances = {"2x2": dict(SMALL), "2x4": dict(LARGE)}
        self.instance = dict(SMALL)
        self.forms = [dict(SMALL), dict(LARGE)]
        self.form_rects = {"small": Rect(0, 0, 400, 400), "large": Rect(0, 0, 400, 400)}
        self.marker = None
        self.run_id = "run"
        self.revision = 0
        self.current_envelope = None
        self.workspace = {}
        self.screen_signature = None
        self.app_version = "1"
        self.renderer_digest = "digest"
        self.commands = []
        self.notify = None
        self._prepared = True
        self._sandbox_transport = True

    async def bridge(self, operation, envelope=None):
        self.commands.append((operation, self.instance.get("formId")))
        if operation == "replace":
            self.current_envelope = envelope
        reply = screen_reply(forms=self.forms, desktopProtocolVersion=3, desktopBatchUpdate=True)
        if operation == "replace":
            reply.update(envelope)
            for key in ("beforeRectVp", "stagedRectVp", "updatedRectVp"):
                reply[key] = reply.get("rectVp")
        return reply

    async def events(self, _identity):
        return [
            {**self.current_envelope, "formId": self.instance.get("formId"), "state": "APPLIED"}
        ]

    async def capture_stable(self, *_args):
        return self.driver.card


def test_api_keeps_preview_default_and_has_independent_prepare_request():
    assert RunRequest(targetId="one", source="{}").captureMode == "preview"
    assert PrepareRequest(targetId="one").targetId == "one"
    with pytest.raises(ValueError):
        PrepareRequest(targetId="one", command="shell")


def test_same_dsl_has_new_revision_and_same_digest():
    first = desktop_envelope("中文", "run", "Q001", 1, "2x2")
    second = desktop_envelope("中文", "run", "Q001", 2, "2x2")
    assert first.get("digest") == hashlib.sha256("中文".encode()).hexdigest()
    assert first.get("digest") == second.get("digest")
    assert first.get("revision") != second.get("revision")


@pytest.mark.parametrize("forms", [[], [SMALL], [LARGE], [SMALL, SMALL], [SMALL, LARGE, LARGE]])
@pytest.mark.asyncio
async def test_preflight_requires_exactly_one_of_each_dimension(tmp_path, forms):
    session = MemorySession(tmp_path)
    session.instances = {}
    with pytest.raises(DesktopEnvironmentError):
        await session.reconcile({"forms": forms})
    assert session.commands == []


@pytest.mark.asyncio
async def test_deleted_or_replaced_form_stops_session(tmp_path):
    session = MemorySession(tmp_path)
    replacement = {**SMALL, "formId": "different"}
    with pytest.raises(DesktopEnvironmentError, match="删除或替换"):
        await session.reconcile({"forms": [replacement, LARGE]})


@pytest.mark.asyncio
async def test_mixed_sizes_and_repeat_reuse_only_existing_forms(tmp_path):
    session = MemorySession(tmp_path)
    source = tmp_path / "Q001/attempt_000/genui.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text(DSL, encoding="utf-8")
    results = []
    for size in ("2x2", "2x4", "2x2", "2x2"):
        result = await session.render(source, size, tmp_path / "card.png", tmp_path / "full.png")
        results.append(result.public())
    updates = [identity for operation, identity in session.commands if operation == "replace"]
    assert updates == ["small", "large", "small", "small"]
    assert [item.get("revision") for item in results] == [1, 2, 3, 4]
    assert all(item.get("sampleId") == "Q001" for item in results)
    assert all(item.get("captureMode") == "desktop" for item in results)
    assert not hasattr(DesktopRenderSession, "add")
    assert not hasattr(DesktopRenderSession, "remove")
    assert not hasattr(DesktopDriver, "add")
    assert not hasattr(DesktopDriver, "remove")


@pytest.mark.asyncio
async def test_moved_card_stops_before_updating(tmp_path):
    session = MemorySession(tmp_path)
    session.form_rects["small"] = Rect(10, 10, 400, 400)
    source = tmp_path / "source.jsonl"
    source.write_text(DSL, encoding="utf-8")
    with pytest.raises(DesktopEnvironmentError, match="位置或尺寸"):
        await session.render(source, "2x2", tmp_path / "c.png", tmp_path / "f.png")
    assert not any(operation == "update" for operation, _identity in session.commands)


@pytest.mark.asyncio
async def test_invalid_dsl_never_touches_phone(tmp_path):
    session = MemorySession(tmp_path)
    source = tmp_path / "invalid.jsonl"
    source.write_text("invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        await session.render(source, "2x2", tmp_path / "c.png", tmp_path / "f.png")
    assert session.commands == []


@pytest.mark.parametrize("stale", ["run", "revision", "digest", "form"])
@pytest.mark.asyncio
async def test_old_or_other_form_receipt_is_rejected(tmp_path, stale):
    session = MemorySession(tmp_path)
    envelope = desktop_envelope(DSL, "run", "Q001", 3, "2x2")
    event = {**envelope, "formId": "small", "state": "APPLIED"}
    changes = {
        "run": ("runId", "old"),
        "revision": ("revision", 2),
        "digest": ("digest", "old"),
        "form": ("formId", "large"),
    }
    change = changes.get(stale)
    assert change is not None
    key, value = change
    event[key] = value

    async def events(_identity):
        return [event]

    session.events = events
    with pytest.raises(DesktopEnvironmentError, match="未确认"):
        await session.wait_applied(envelope)


@pytest.mark.parametrize("density", [True, 0, -1, float("nan"), None])
def test_invalid_density_is_rejected(density):
    with pytest.raises(DesktopEnvironmentError):
        physical_rect(screen_reply(density=density))


def test_crop_uses_reported_density_and_bounds():
    assert physical_rect(screen_reply()) == Rect(0, 0, 400, 400)
    with pytest.raises(DeviceError):
        physical_rect(screen_reply(rectVp={"left": 500, "top": 0, "width": 100, "height": 100}))


@pytest.mark.asyncio
async def test_no_compilation_record_fails_without_build_install_or_desktop_operations(tmp_path):
    session = MemorySession(tmp_path)
    actions = []

    async def target(_identity):
        return session.target

    async def acquire():
        actions.append("lock")

    async def cleanup():
        actions.append("cleanup")

    session.devices = SimpleNamespace(target=target)
    session._process_lock = SimpleNamespace(
        acquire=acquire, release=lambda: actions.append("unlock")
    )
    session._cleanup_remote = cleanup
    session._lock = None
    with pytest.raises(DesktopEnvironmentError, match="编译安装"):
        await DesktopRenderSession.__aenter__(session)
    assert session.commands == []
    assert actions == ["lock", "cleanup", "unlock"]
    assert session._lock is None


@pytest.mark.parametrize("fingerprint", ["fresh", "old"])
@pytest.mark.asyncio
async def test_prepared_session_only_queries_existing_forms(tmp_path, monkeypatch, fingerprint):
    session = MemorySession(tmp_path)
    session.instances = {}
    session._prepared = False
    prepared = tmp_path / "prepared/device.json"
    prepared.parent.mkdir()
    prepared.write_text(json.dumps({"fingerprint": fingerprint}), encoding="utf-8")
    (tmp_path / "genui_form.har").write_bytes(b"renderer")
    actions = []

    async def target(_identity):
        return session.target

    async def acquire():
        actions.append("lock")

    async def cleanup():
        actions.append("cleanup")

    async def sandbox(_serial):
        return True

    def build():
        pytest.fail("桌面后处理禁止构建安装")

    session.devices = SimpleNamespace(target=target)
    session.project = SimpleNamespace(_fingerprint=lambda: "fresh", build=build)
    session._process_lock = SimpleNamespace(
        acquire=acquire, release=lambda: actions.append("unlock")
    )
    session._cleanup_remote = cleanup
    session._prepare_sandbox = sandbox
    session._lock = None
    monkeypatch.setattr("debug_tools.device_debug.desktop.DesktopDriver", MemoryDriver)
    if fingerprint == "old":
        with pytest.raises(DesktopEnvironmentError, match="重新编译"):
            await DesktopRenderSession.__aenter__(session)
        assert session.commands == []
    else:
        await DesktopRenderSession.__aenter__(session)
        try:
            assert session._prepared
            assert len(session.instances) == 2
            assert [operation for operation, _identity in session.commands] == [
                "environment",
                "status",
                "rect",
                "rect",
            ]
        finally:
            await session.__aexit__(None, None, None)
    assert actions == ["lock", "cleanup", "unlock"]


@pytest.mark.parametrize("moving", [False, True])
@pytest.mark.asyncio
async def test_capture_requires_stable_pixels_and_checks_current_rect(
    tmp_path, monkeypatch, moving
):
    session = MemorySession(tmp_path)
    session.current_envelope = desktop_envelope(DSL, "run", "Q001", 1, "2x2")
    session.marker = "current"
    snapshots = []

    async def snapshot(path):
        assert session.commands == [], "连续采样期间不允许拉起应用查询"
        snapshots.append(path)
        color = "white" if moving and len(snapshots) % 2 else "black"
        with Image.new("RGB", (1000, 1000), color) as image:
            image.save(path)

    async def no_wait(_delay):
        return None

    session.snapshot = snapshot
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    card, full = tmp_path / "card.png", tmp_path / "full.png"
    if moving:
        with pytest.raises(DesktopEnvironmentError, match="未稳定"):
            await DesktopRenderSession.capture_stable(session, card, full, 0.0)
        assert not card.exists()
        assert not full.exists()
    else:
        assert await DesktopRenderSession.capture_stable(session, card, full, 0.0) == Rect(
            0, 0, 400, 400
        )
        assert len(snapshots) == 4
        assert session.commands == [("rect", "small")]
        assert card.is_file()


@pytest.mark.asyncio
async def test_process_lock_cancellation_releases_handle(tmp_path):
    first, second = DeviceProcessLock(tmp_path, "one"), DeviceProcessLock(tmp_path, "one")
    await first.acquire()
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(second.acquire(), 0.05)
        assert second.stream is None
    finally:
        first.release()
    await second.acquire()
    second.release()


@pytest.mark.asyncio
async def test_zero_form_query_error_never_opens_picker():
    async def command(_operation, _envelope):
        raise DesktopCommandError(16500100, "empty")

    session = SimpleNamespace(_command=command)
    with pytest.raises(DesktopEnvironmentError, match="各添加一张"):
        await DesktopRenderSession.bridge(session, "status")


def test_historical_preview_and_desktop_metadata_are_separate():
    assert compatible_capture({}, DSL)
    assert not compatible_capture({"captureMode": "desktop"}, DSL)
    assert not compatible_capture({"sampleDigest": "old"}, DSL)
    assert parse_desktop_events('prefix A2UI_DESKTOP {"state":"OK"}') == [{"state": "OK"}]


def same_page_tree(missing=None):
    nodes = []
    values = [
        ("icon", {"id": "AppIconCommonView_debug.app.EntryAbility"}, "[100,1400][250,1550]"),
        ("small", {"description": "A2UI_FORM:small"}, "[423,801][897,1275]"),
        ("large", {"description": "A2UI_FORM:large"}, "[129,201][1191,675]"),
    ]
    for name, attributes, bounds in values:
        if name == missing:
            continue
        nodes.append({"attributes": {**attributes, "bounds": bounds}})
    return parse_layout(
        {
            "attributes": {"id": "SCBDesktop_Flex_Desktop", "bounds": "[0,0][1320,2120]"},
            "children": [
                {
                    "attributes": {"type": "Grid", "bounds": "[72,176][1248,1676]"},
                    "children": nodes,
                }
            ],
        }
    )


def same_page_driver():
    session = SimpleNamespace(
        instance=SMALL,
        instances={"2x2": SMALL, "2x4": LARGE},
        project=SimpleNamespace(info=SimpleNamespace(bundle="debug.app", ability="EntryAbility")),
        config=SimpleNamespace(render_timeout=1.0),
    )
    return DesktopDriver(session, Rect(0, 0, 1320, 2120))


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, "icon", "small", "large"])
async def test_same_page_required_without_any_swipe(missing):
    driver = same_page_driver()
    commands = []

    async def layout():
        return same_page_tree(missing)

    async def hdc(arguments):
        commands.append(arguments)
        return ""

    driver.layout = layout
    driver.hdc = hdc
    if missing is None:
        await driver.navigate()
    else:
        with pytest.raises(DesktopEnvironmentError, match="同一个桌面页面"):
            await driver.navigate()
    assert commands == []


@pytest.mark.parametrize("invalid", ["hidden", "outside", "dock", "duplicate"])
def test_same_page_rejects_hidden_off_page_dock_or_duplicate_items(invalid):
    driver = same_page_driver()
    root = same_page_tree()
    workspace = root.children[0]
    target = workspace.children[0]
    if invalid == "hidden":
        target.attributes["visible"] = "false"
    elif invalid == "outside":
        target.attributes["bounds"] = "[1250,1400][1300,1550]"
    elif invalid == "dock":
        workspace = type(workspace)(workspace.attributes, workspace.children[1:])
        root = type(root)(root.attributes, (workspace, target))
    else:
        workspace = type(workspace)(workspace.attributes, (*workspace.children, target))
        root = type(root)(root.attributes, (workspace,))
    with pytest.raises(DesktopEnvironmentError, match="同一个桌面页面"):
        driver.same_page_workspace(root)


@pytest.mark.asyncio
async def test_inspection_rechecks_other_form_and_icon_on_every_capture():
    driver = same_page_driver()
    driver.card = Rect(423, 801, 474, 474)
    pages = iter([same_page_tree(), same_page_tree("large")])

    async def layout():
        return next(pages)

    driver.layout = layout
    assert await driver.inspect() == {"formBounds": driver.card.__dict__}
    with pytest.raises(DesktopEnvironmentError, match="同一个桌面页面"):
        await driver.inspect()


@pytest.mark.asyncio
@pytest.mark.parametrize("bundle,key", [("debug.app", "Back"), ("other.app", "Home")])
async def test_navigation_returns_from_command_without_resetting_page(bundle, key):
    app = parse_layout({"attributes": {"bundleName": bundle}})
    layouts = iter([app, same_page_tree()])
    commands = []
    driver = same_page_driver()

    async def layout():
        return next(layouts)

    async def hdc(arguments):
        commands.append(arguments)
        return ""

    driver.layout = layout
    driver.hdc = hdc
    await driver.navigate()
    assert commands == [["shell", "uitest", "uiInput", "keyEvent", key]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload", ['{"formId":"42","state":"APPLIED"}', "missing", "[]", "bad", "[Fail]"]
)
async def test_receipt_reads_sandbox_without_launching_ability(tmp_path, payload):
    session = MemorySession(tmp_path)
    session.instance = {"formId": "42"}
    session._sandbox_transport = True
    session.project = SimpleNamespace(info=SimpleNamespace(bundle="debug.app"))
    session.log = tmp_path / "device.log"
    commands = []

    async def hdc(_serial, arguments, **_options):
        commands.append(arguments)
        if payload == "missing":
            return f"cat: {arguments[-1]}: No such file or directory"
        return payload

    session.devices = SimpleNamespace(hdc=hdc)
    if payload in ("[]", "bad", "[Fail]"):
        with pytest.raises(DeviceError):
            await DesktopRenderSession.events(session, "run")
    else:
        result = await DesktopRenderSession.events(session, "run")
        expected = [] if payload == "missing" else [{"formId": "42", "state": "APPLIED"}]
        assert result == expected
    assert commands == [
        ["shell", "-b", "debug.app", "cat", "data/storage/el2/base/files/desktop/receipt-42.json"]
    ]
    assert session.commands == []


@pytest.mark.asyncio
async def test_receipt_keeps_non_sandbox_transport_fallback(tmp_path):
    session = MemorySession(tmp_path)
    session._sandbox_transport = False

    async def bridge(operation):
        session.commands.append(operation)
        return {"receipt": {"state": "APPLIED"}}

    session.bridge = bridge
    assert await DesktopRenderSession.events(session, "run") == [{"state": "APPLIED"}]
    assert session.commands == ["receipt"]


@pytest.mark.asyncio
async def test_final_pixel_change_restarts_stability_before_phone_verification(
    tmp_path, monkeypatch
):
    session = MemorySession(tmp_path)
    session.current_envelope = desktop_envelope(DSL, "run", "Q001", 1, "2x2")
    snapshots = []

    async def snapshot(path):
        assert session.commands == []
        snapshots.append(path)
        color = "black" if len(snapshots) <= 3 else "white"
        with Image.new("RGB", (1000, 1000), color) as image:
            image.save(path)

    async def no_wait(_delay):
        return None

    session.snapshot = snapshot
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    await DesktopRenderSession.capture_stable(
        session, tmp_path / "card.png", tmp_path / "full.png", 1.0
    )
    assert len(snapshots) == 7
    assert session.commands == [("rect", "small")]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "fatal", "moved"])
async def test_final_verification_failure_discards_captured_files(tmp_path, monkeypatch, failure):
    session = MemorySession(tmp_path)
    session.current_envelope = desktop_envelope(DSL, "run", "Q001", 1, "2x2")

    async def snapshot(path):
        with Image.new("RGB", (1000, 1000), "black") as image:
            image.save(path)

    async def events(_identity):
        if failure == "missing":
            return []
        return [{**session.current_envelope, "formId": "small", "state": "FAILED"}]

    async def bridge(_operation):
        return screen_reply(rectVp={"left": 1, "top": 0, "width": 200, "height": 200})

    async def no_wait(_delay):
        return None

    session.snapshot = snapshot
    session.events = events
    if failure == "moved":
        session.bridge = bridge
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    card, full = tmp_path / "card.png", tmp_path / "full.png"
    with pytest.raises(DeviceError):
        await DesktopRenderSession.capture_stable(session, card, full, 0.0)
    assert not card.exists()
    assert not full.exists()


@pytest.mark.parametrize("change", ["screen", "form"])
@pytest.mark.asyncio
async def test_frame_inspection_rejects_screen_change_or_shrunk_form(change):
    driver = same_page_driver()
    driver.card = Rect(423, 801, 474, 474)
    root = same_page_tree()
    if change == "screen":
        root.attributes["bounds"] = "[0,0][2120,1320]"
    else:
        root.children[0].children[1].attributes["bounds"] = "[423,801][896,1274]"

    async def layout():
        return root

    driver.layout = layout
    with pytest.raises(DesktopEnvironmentError):
        await driver.inspect()


@pytest.mark.asyncio
async def test_sample_groups_all_update_commands_before_returning_to_desktop(tmp_path):
    session = MemorySession(tmp_path)
    timeline = []
    original_bridge = session.bridge

    async def bridge(operation, envelope=None):
        timeline.append(operation)
        return await original_bridge(operation, envelope)

    async def navigate():
        timeline.append("desktop")

    session.bridge = bridge
    session.driver.navigate = navigate
    source = tmp_path / "source.jsonl"
    source.write_text(DSL, encoding="utf-8")
    await session.render(source, "2x2", tmp_path / "card.png", tmp_path / "full.png")
    assert timeline == [
        "desktop",
        "replace",
        "desktop",
    ]


@pytest.mark.parametrize("key", ["runId", "revision", "digest"])
@pytest.mark.asyncio
async def test_combined_update_rejects_stale_identity_before_capture(tmp_path, key):
    session = MemorySession(tmp_path)
    original = session.bridge

    async def stale(operation, envelope=None):
        reply = await original(operation, envelope)
        reply[key] = "stale"
        return reply

    session.bridge = stale
    source = tmp_path / "source.jsonl"
    source.write_text(DSL, encoding="utf-8")
    with pytest.raises(DesktopEnvironmentError, match="本轮样本"):
        await session.render(source, "2x2", tmp_path / "card.png", tmp_path / "full.png")
    assert not (tmp_path / "card.png").exists()
    assert session.marker is None


@pytest.mark.parametrize("key", ["beforeRectVp", "stagedRectVp", "updatedRectVp", "rectVp"])
@pytest.mark.asyncio
async def test_combined_update_checks_each_boundary_before_capture(tmp_path, key):
    session = MemorySession(tmp_path)
    original = session.bridge

    async def moved(operation, envelope=None):
        reply = await original(operation, envelope)
        reply[key] = {"left": 10, "top": 0, "width": 200, "height": 200}
        return reply

    session.bridge = moved
    source = tmp_path / "source.jsonl"
    source.write_text(DSL, encoding="utf-8")
    with pytest.raises(DesktopEnvironmentError, match="位置或尺寸"):
        await session.render(source, "2x2", tmp_path / "card.png", tmp_path / "full.png")
    assert session.marker is None


@pytest.mark.asyncio
async def test_combined_command_sends_ordered_instances_and_real_layout_guards(tmp_path):
    session = MemorySession(tmp_path)
    session.instances = {"2x4": dict(LARGE), "2x2": dict(SMALL)}
    session.screen_signature = (1000, 1000, 2.0, 0)
    session.log = tmp_path / "device.log"
    session.project = SimpleNamespace(info=SimpleNamespace(bundle="debug.app"))
    session._remote_files = set()
    sent = []

    async def hdc(_serial, arguments, **_kwargs):
        sent.append(json.loads(Path(arguments[-2]).read_text(encoding="utf-8")))
        return ""

    async def start(_parameters):
        return None

    async def events(identity):
        return [screen_reply(commandId=identity, state="OK", forms=session.forms)]

    session.devices = SimpleNamespace(hdc=hdc)
    session._start_app = start
    session.events = events
    envelope = desktop_envelope(DSL, "run", "sample", 1, "2x2")
    await DesktopRenderSession._command(session, "replace", envelope)
    assert len(sent) == 1
    command = sent[0]
    assert command.get("expectedForms") == [SMALL, LARGE]
    assert command.get("expectedRectPx") == Rect(0, 0, 400, 400).__dict__
    assert command.get("expectedDisplay") == [1000, 1000, 2.0, 0]


@pytest.mark.asyncio
async def test_inline_layout_uses_one_hdc_call_and_logs_no_tree_content(tmp_path):
    driver = same_page_driver()
    calls = []
    driver.session.log = tmp_path / "device.log"
    driver.session.target = SimpleNamespace(serial="one")
    driver.session._require_hdc_success = lambda *_args: None

    async def hdc(_serial, arguments):
        calls.append(arguments)
        return "DumpLayout saved\n" + json.dumps(asdict(same_page_tree()))

    driver.session.devices = SimpleNamespace(hdc=hdc)
    root = await driver.layout()
    driver.same_page_workspace(root)
    assert len(calls) == 1
    command = calls[0][-1]
    assert "dumpLayout" in command and "cat /data/local/tmp/" in command
    assert "rm -f /data/local/tmp/" in command
    logged = driver.session.log.read_text(encoding="utf-8")
    assert '"mode": "inline"' in logged
    assert "A2UI_FORM" not in logged


@pytest.mark.asyncio
async def test_inline_layout_falls_back_once_without_skipping_guards(tmp_path):
    driver = same_page_driver()
    driver.card = Rect(423, 801, 474, 474)
    driver.session.log = tmp_path / "device.log"
    driver.session.target = SimpleNamespace(serial="one")
    driver.session._require_hdc_success = lambda *_args: None
    calls = []

    async def hdc(*_args):
        calls.append("inline")
        return "output was truncated"

    async def legacy():
        calls.append("file")
        return same_page_tree("large")

    driver.session.devices = SimpleNamespace(hdc=hdc)
    driver.file_layout = legacy
    for _attempt in range(2):
        with pytest.raises(DesktopEnvironmentError, match="同一个桌面页面"):
            await driver.navigate_and_inspect()
    assert calls == ["inline", "file", "file"]


@pytest.mark.asyncio
async def test_combined_navigation_inspection_uses_same_fresh_tree_once():
    driver = same_page_driver()
    driver.card = Rect(423, 801, 474, 474)
    calls = []

    async def layout():
        calls.append("fresh")
        return same_page_tree()

    driver.layout = layout
    assert await driver.navigate_and_inspect() == {"formBounds": driver.card.__dict__}
    assert calls == ["fresh"]
    with pytest.raises(DesktopEnvironmentError):
        await driver.navigate_and_inspect(marker="wrong-version")
    assert calls == ["fresh", "fresh"]


@pytest.mark.asyncio
async def test_remote_cleanup_is_batched_without_dropping_any_paths(tmp_path):
    session = MemorySession(tmp_path)
    expected = {f"data/storage/el2/base/files/a2ui/{index}.json" for index in range(65)}
    session._remote_files = set(expected)
    session.project = SimpleNamespace(info=SimpleNamespace(bundle="debug.app"))
    batches = []

    async def hdc(_serial, arguments):
        assert arguments[:5] == ["shell", "-b", "debug.app", "rm", "-f"]
        batches.append(arguments[5:])
        return ""

    session.devices = SimpleNamespace(hdc=hdc)
    await session._cleanup_remote()
    assert [len(batch) for batch in batches] == [32, 32, 1]
    removed = set()
    for batch in batches:
        removed.update(batch)
    assert removed == expected
    assert session._remote_files == set()
