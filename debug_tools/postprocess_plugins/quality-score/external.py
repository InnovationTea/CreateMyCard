"""DSL＋图片＋Query 检测适配：复用离线结构、内容和 OCR 规则。"""

import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path


def _load(name):
    path = Path(__file__).with_name("offline_checks") / (name + ".py")
    spec = importlib.util.spec_from_file_location("offline_quality_" + name, path)
    if spec is None or spec.loader is None:
        raise ImportError("离线检查器缺失")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load("core")
content = _load("content_checks")
BOUNDARY = (
    "外部 DSL＋截图＋Query：结构引用、占位内容、初始绑定、有限需求线索及 OCR 文本匹配。"
    "截图由用户提供，哈希用于核对上传文件。OCR 疑似缺字计入分数下界。"
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(context):
    sample = context.get("sample") or {}
    run_dir = Path(context.get("runDir", "")).resolve()
    directory = (Path(context.get("sampleDir", "")) / "input").resolve()
    if not directory.is_relative_to(run_dir):
        raise ValueError("导入目录越界")
    metadata_path = (directory / "input.json").resolve()
    source_path = (directory / "genui.jsonl").resolve()
    if not metadata_path.is_relative_to(run_dir) or not source_path.is_relative_to(run_dir):
        raise ValueError("导入文件越界")
    metadata_bytes = metadata_path.read_bytes()
    if _sha(metadata_bytes) != sample.get("inputSha256"):
        raise ValueError("导入元数据已变化；请重新导入，不使用旧关联")
    metadata = json.loads(metadata_bytes)
    source = source_path.read_bytes()
    image_file = metadata.get("imageFile")
    if image_file not in {"image.png", "image.jpg"}:
        raise ValueError("导入截图路径无效")
    image_path = (directory / image_file).resolve()
    if not image_path.is_relative_to(run_dir):
        raise ValueError("导入截图路径越界")
    image_bytes = image_path.read_bytes()
    if (_sha(source), _sha(image_bytes)) != (
        metadata.get("sourceSha256"),
        metadata.get("imageSha256"),
    ):
        raise ValueError("DSL 或截图已变化；请重新导入")
    if (metadata.get("query"), metadata.get("size")) != (sample.get("query"), sample.get("size")):
        raise ValueError("Query 或尺寸已变化；请重新导入")
    findings, gaps = [], []
    complete = True
    actions = None
    try:
        actions = core.parse_actions(source.decode("utf-8-sig"))
    except (ValueError, RecursionError):
        findings.append({"code": "structure.invalid", "message": "DSL 解析失败或嵌套过深"})
    supported = False
    if actions is not None:
        # ponytail: 旧检查器按单卡消息集工作；不猜测增量归并或新协议语义。
        stack = [(actions, 0)]
        count = 0
        while stack:
            item, depth = stack.pop()
            count += 1
            if depth > 60 or count > 100000:
                raise ValueError("DSL 结构超过离线检测资源限制")
            if isinstance(item, dict):
                stack.extend((value, depth + 1) for value in item.values())
            elif isinstance(item, list):
                stack.extend((value, depth + 1) for value in item)
        known_protocol = all(
            isinstance(action, dict) and action.get("version") == "v0.9" for action in actions
        )
        if known_protocol:
            ok, hard, comps, soft = core.check_structure(actions)
        else:
            ok, hard, comps = True, [], []
            soft = ["离线结构检查仅覆盖 v0.9 消息；其他格式待评，不按旧协议淘汰"]
        data_model = core.get_data_model(actions) if known_protocol else None
        if isinstance(data_model, dict) and not isinstance(data_model.get("value", {}), dict):
            soft.append("待复核非对象数据模型；离线内容检查未支持")
        for comp in comps:
            if comp.get("styles") is not None and not isinstance(comp.get("styles"), dict):
                soft.append("待复核非对象样式；离线内容检查未支持")
        for message in hard:
            findings.append({"code": "structure.invalid", "message": message})
        for message in soft:
            findings.append({"code": "structure.review", "message": message})
        supported = ok and not soft
        if supported:
            card_spec = metadata.get("cardSpec") or {}
            if not card_spec:
                try:
                    bundle = core.strict_json(source.decode("utf-8-sig"))
                except ValueError:
                    bundle = None  # JSONL 无外层 CardSpec，仍按消息集检测。
                if isinstance(bundle, dict) and "genui" in bundle:
                    card_spec = bundle.get("cardSpec") or {}
            findings.extend(content.content_findings(actions, card_spec, metadata.get("query", "")))
            required = metadata.get("expectedIntents")
            if required is not None:
                missing = set(required) - core.intent_names(comps)
                for intent in sorted(missing):
                    findings.append(
                        {
                            "code": "semantic.required_action_unproven",
                            "message": "显式需求中声明的动作未找到：" + intent,
                            "evidence": {"expected_intent": intent},
                        }
                    )
            else:
                gaps.append("未提供显式动作清单；Query 仅执行已覆盖短语线索")
        elif ok:
            complete = False
            gaps.append("旧检测器不支持该结构的完整状态归并")
    try:
        ocr_version = importlib.metadata.version("rapidocr-onnxruntime")
    except importlib.metadata.PackageNotFoundError:
        ocr_version = "unavailable"
    coverage = ["structure", "content-clues", "query-clues"]
    if supported:
        for message in core.check_ocr(str(image_path), actions):
            if message.startswith("[检测失败") or message.startswith("[未检查·无"):
                complete = False
                gaps.append(message)
            elif message.startswith("[未检查"):
                gaps.append(message)
            else:
                findings.append(
                    {
                        "rule_id": "GEOMETRY.CLIP_OCR_SUSPECT",
                        "severity": "P1",
                        "evidence_type": "待确认",
                        "message": message,
                        "evidence": {"method": "offline-ocr-character-match"},
                    }
                )
        if complete:
            coverage.append("ocr-text-match")
    checker_hash = hashlib.sha256()
    for path in [Path(__file__), *sorted(Path(__file__).with_name("offline_checks").glob("*.py"))]:
        checker_hash.update(path.read_bytes())
    evidence = {
        "schemaVersion": "external-quality-v1",
        "complete": complete,
        "sourceSha256": _sha(source),
        "imageSha256": _sha(image_bytes),
        "imageSource": metadata.get("imageSource"),
        "pairing": "user-supplied-unverified",
        "coverage": coverage,
        "gaps": gaps,
        "findings": findings,
        "renderContext": {"query": sample.get("query"), "size": sample.get("size")},
        "comparisonScope": {
            "detectorSha256": checker_hash.hexdigest(),
            "ocrVersion": ocr_version,
            "imageSource": metadata.get("imageSource"),
            "coverage": coverage,
            "expectedIntents": metadata.get("expectedIntents"),
        },
    }
    return findings, evidence, image_path, BOUNDARY
