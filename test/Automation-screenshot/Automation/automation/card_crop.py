from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import cv2
import numpy as np
from PIL import Image


CardType = Literal["2x2", "2x4"]
CardTypeOption = Literal["auto", "2x2", "2x4"]


@dataclass(frozen=True)
class CardCropConfig:
    y_start_ratio: float = 0.040
    y_end_ratio: float = 0.240
    x_start_2x2: float = 0.284
    x_end_2x2: float = 0.719
    x_start_2x4: float = 0.074
    x_end_2x4: float = 0.931
    wide_card_threshold: float = 0.80
    bg_gray_threshold: int = 235
    min_block_width: int = 50
    col_gap_threshold: int = 15
    col_content_threshold: int = 3
    row_content_threshold: int = 2
    y_refine_top_margin: int = 2
    y_refine_bottom_margin: int = 3
    card_type: CardTypeOption = "auto"

    @classmethod
    def from_json(cls, path: Path) -> "CardCropConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Card crop config must be a JSON object: {path}")

        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(f"Unknown card crop config keys in {path}: {', '.join(unknown)}")
        return cls(**data)


@dataclass(frozen=True)
class CardCropResult:
    source_path: Path
    card_path: Path
    card_type: CardType
    box: tuple[int, int, int, int]
    content_width_ratio: float
    debug_path: Path | None = None


class CardCropper:
    def __init__(self, config: CardCropConfig | None = None):
        self.config = config or CardCropConfig()

    def crop(
        self,
        input_path: Path,
        output_dir: Path | None = None,
        *,
        output_path: Path | None = None,
        debug: bool = False,
        debug_dir: Path | None = None,
    ) -> CardCropResult:
        input_path = Path(input_path)
        if not input_path.exists() or not input_path.is_file():
            raise FileNotFoundError(input_path)
        if output_path is None:
            target_dir = Path(output_dir) if output_dir else input_path.parent
            output_path = target_dir / f"{input_path.stem}_card.png"
        else:
            output_path = Path(output_path)

        image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to read image: {input_path}")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape[:2]
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid image size: {input_path}")

        y_start = clamp_int(int(height * self.config.y_start_ratio), 0, height)
        y_end = clamp_int(int(height * self.config.y_end_ratio), y_start + 1, height)

        detected_type, content_width_ratio = self._detect_card_type(gray, y_start, y_end, width)
        card_type = detected_type if self.config.card_type == "auto" else self.config.card_type
        x_start, x_end = self._x_bounds(card_type, width)
        refined_y_start, refined_y_end = self._refine_y(gray, x_start, x_end, y_start, y_end)
        box = (x_start, refined_y_start, x_end, refined_y_end)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(input_path) as pil_image:
            pil_image.crop(box).save(output_path)

        debug_path = None
        if debug:
            target_debug_dir = Path(debug_dir) if debug_dir else output_path.parent / "_debug"
            debug_path = target_debug_dir / f"{input_path.stem}_card_annotated.png"
            self._save_debug(image, box, debug_path)

        return CardCropResult(
            source_path=input_path,
            card_path=output_path,
            card_type=card_type,
            box=box,
            content_width_ratio=content_width_ratio,
            debug_path=debug_path,
        )

    def crop_many(
        self,
        input_paths: Iterable[Path],
        output_dir: Path,
        *,
        debug: bool = False,
    ) -> list[CardCropResult]:
        results: list[CardCropResult] = []
        for input_path in input_paths:
            results.append(self.crop(input_path, output_dir, debug=debug))
        return results

    def _detect_card_type(self, gray: np.ndarray, y_start: int, y_end: int, img_w: int) -> tuple[CardType, float]:
        band_gray = gray[y_start:y_end, :]
        content_mask = band_gray < self.config.bg_gray_threshold
        col_proj = content_mask.sum(axis=0)
        content_cols = np.where(col_proj > self.config.col_content_threshold)[0]
        blocks = [
            (start, end)
            for start, end in contiguous_blocks(content_cols, self.config.col_gap_threshold)
            if end - start + 1 >= self.config.min_block_width
        ]

        if not blocks:
            return "2x2", 0.0

        x_min = min(start for start, _ in blocks)
        x_max = max(end for _, end in blocks)
        content_width_ratio = (x_max - x_min) / img_w
        card_type: CardType = "2x4" if content_width_ratio > self.config.wide_card_threshold else "2x2"
        return card_type, content_width_ratio

    def _x_bounds(self, card_type: CardType, img_w: int) -> tuple[int, int]:
        if card_type == "2x4":
            x_start = int(img_w * self.config.x_start_2x4)
            x_end = int(img_w * self.config.x_end_2x4)
        else:
            x_start = int(img_w * self.config.x_start_2x2)
            x_end = int(img_w * self.config.x_end_2x2)
        return clamp_bounds(x_start, x_end, img_w)

    def _refine_y(self, gray: np.ndarray, x_start: int, x_end: int, y_start: int, y_end: int) -> tuple[int, int]:
        band_gray = gray[y_start:y_end, x_start:x_end]
        if band_gray.size == 0:
            return y_start, y_end

        row_proj = (band_gray < self.config.bg_gray_threshold).sum(axis=1)
        content_rows = np.where(row_proj > self.config.row_content_threshold)[0]
        if content_rows.size == 0:
            return y_start, y_end

        band_height = y_end - y_start
        refined_start = y_start + max(0, int(content_rows[0]) - self.config.y_refine_top_margin)
        refined_end = y_start + min(band_height, int(content_rows[-1]) + self.config.y_refine_bottom_margin)
        return clamp_bounds(refined_start, refined_end, gray.shape[0])

    def _save_debug(self, image: np.ndarray, box: tuple[int, int, int, int], debug_path: Path) -> None:
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        annotated = image.copy()
        x_start, y_start, x_end, y_end = box
        cv2.rectangle(annotated, (x_start, y_start), (x_end - 1, y_end - 1), (0, 0, 255), 2)
        cv2.imwrite(str(debug_path), annotated)


def load_card_crop_config(path: Path | None) -> CardCropConfig:
    if path is None:
        return CardCropConfig()
    return CardCropConfig.from_json(path)


def find_image_files(input_path: Path) -> list[Path]:
    input_path = Path(input_path)
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(input_path)

    image_files: list[Path] = []
    for pattern in ("*.png", "*.jpg", "*.jpeg"):
        image_files.extend(input_path.glob(pattern))
    return sorted(path for path in image_files if not path.stem.endswith("_card"))


def contiguous_blocks(indices: np.ndarray, gap_threshold: int) -> list[tuple[int, int]]:
    if indices.size == 0:
        return []

    blocks: list[tuple[int, int]] = []
    start = int(indices[0])
    previous = int(indices[0])
    for raw_index in indices[1:]:
        index = int(raw_index)
        if index - previous > gap_threshold:
            blocks.append((start, previous))
            start = index
        previous = index
    blocks.append((start, previous))
    return blocks


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def clamp_bounds(start: int, end: int, maximum: int) -> tuple[int, int]:
    start = clamp_int(start, 0, maximum)
    end = clamp_int(end, start + 1, maximum)
    return start, end
