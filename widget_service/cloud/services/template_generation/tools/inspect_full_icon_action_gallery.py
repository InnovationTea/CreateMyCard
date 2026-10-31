"""核对真机截图、检查动作边界并输出逐图待复核记录。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def _rectangle(node: dict[str, Any]) -> tuple[float, float, float, float]:
    geometry = node.get("geometry")
    if not isinstance(geometry, dict):
        raise ValueError("Missing device geometry")
    offset = geometry.get("windowOffset")
    size = geometry.get("size")
    if not isinstance(offset, dict) or not isinstance(size, dict):
        raise ValueError("Incomplete device geometry")
    values = (offset.get("x"), offset.get("y"), size.get("width"), size.get("height"))
    if not all(isinstance(value, (float, int)) for value in values):
        raise ValueError("Invalid device rectangle")
    x, y, width, height = values
    return x, y, x + width, y + height


def _intersects(first: tuple, second: tuple) -> bool:
    return min(first[2], second[2]) > max(first[0], second[0]) + 1 and (
        min(first[3], second[3]) > max(first[1], second[1]) + 1
    )


def inspect_case(case: dict, record: dict, gallery: Path, screenshots: Path) -> dict:
    result = {"caseId": case.get("caseId"), "templateId": case.get("targetTemplateId"),
              "state": case.get("scenarioId"), "status": "pending", "overlaps": []}
    if case.get("status") == "not_applicable":
        result.update(status="not_applicable", reason=case.get("errorMessage"))
        return result
    if record.get("status") != "captured":
        result.update(status="unavailable", reason=record.get("error", "Missing capture"))
        return result
    filename = case.get("a2uiFile")
    image_file = record.get("imageFile")
    if not isinstance(filename, str) or not isinstance(image_file, str):
        raise ValueError("Missing artifact/image filename")
    digest = hashlib.sha256((gallery / filename).read_bytes()).hexdigest()
    if digest != record.get("artifactDigest") or digest != case.get("artifactDigest"):
        raise ValueError(f"Capture artifact mismatch: {case.get('caseId')}")
    image_path = screenshots / image_file
    with Image.open(image_path) as picture:
        if picture.size != (record.get("width"), record.get("height")):
            raise ValueError("Capture dimensions mismatch")
    geometry = json.loads(image_path.with_suffix(".geometry.json").read_text())
    if geometry.get("caseId") != case.get("caseId"):
        raise ValueError("Geometry case mismatch")
    nodes = geometry.get("nodes", [])
    action = next(node for node in nodes if node.get("id") == "audit_icon_action")
    action_rect = _rectangle(action)
    overlaps = []
    for node in nodes:
        if node.get("type") not in {"Text", "Image", "Progress", "Button", "Checkbox"}:
            continue
        identity = node.get("id", "")
        if identity.startswith("audit_icon_action"):
            continue
        if _intersects(_rectangle(node), action_rect):
            overlaps.append({"nodeId": identity, "type": node.get("type"),
                             "text": node.get("props", {}).get("content")})
    result.update(
        status="bounds_intersection" if overlaps else "review_required", overlaps=overlaps,
        screenshot=image_file, screenshotDigest=hashlib.sha256(image_path.read_bytes()).hexdigest(),
        artifactDigest=digest, warning=record.get("warning", ""),
        viewportVp=[geometry.get("cardWidthVp"), geometry.get("cardHeightVp")],
    )
    return result


def inspect_gallery(gallery: Path, screenshots: Path, output: Path) -> dict:
    manifest = json.loads((gallery / "manifest.json").read_text())
    captures = json.loads((screenshots / "manifest.json").read_text())
    records = {}
    for record in captures.get("records", []):
        identity = record.get("caseId")
        if identity in records:
            raise ValueError("Duplicate capture")
        records[identity] = record
    results = []
    expected_ids = set()
    for provider in manifest.get("providers", []):
        for case in provider.get("cases", []):
            expected_ids.add(case.get("caseId"))
            results.append(inspect_case(case, records.get(case.get("caseId"), {}),
                                        gallery, screenshots))
    if captures.get("complete") and set(records) != expected_ids:
        raise ValueError("Complete capture must exactly cover the gallery")
    output.mkdir(parents=True, exist_ok=True)
    report = {"complete": captures.get("complete", False), "cases": results}
    (output / "geometry-review.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    # 每行一个模板的三种状态；截图缩略图只用于索引，原始 PNG 保留。
    for start in range(0, len(results), 30):
        batch = results[start:start + 30]
        sheet = Image.new("RGB", (840, 10 * 300), "#e8e8e8")
        draw = ImageDraw.Draw(sheet)
        for index, result in enumerate(batch):
            x, y = (index % 3) * 280, (index // 3) * 300
            filename = result.get("screenshot")
            if filename:
                with Image.open(screenshots / filename) as picture:
                    picture.thumbnail((270, 270))
                    sheet.paste(picture, (x + 5, y))
            label = f"{result.get('caseId')} {result.get('status')}"
            draw.text((x + 5, y + 272), label, fill="black")
        sheet.save(output / f"sheet-{start // 30:02d}.jpg")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gallery", type=Path)
    parser.add_argument("screenshots", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = inspect_gallery(args.gallery, args.screenshots, args.output)
    print(f"完整批次={report.get('complete')}，检查条数={len(report.get('cases', []))}")


if __name__ == "__main__":
    main()
