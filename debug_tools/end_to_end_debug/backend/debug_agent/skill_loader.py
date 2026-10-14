from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SkillLoadError(ValueError):
    """Raised when a Skill resource cannot be safely loaded."""


@dataclass(frozen=True)
class SkillCatalog:
    name: str
    description: str
    tools: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class SkillResource:
    skill_name: str
    resource_id: str
    digest: str
    content: str
    already_loaded: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "skillName": self.skill_name,
            "resourceId": self.resource_id,
            "digest": f"sha256:{self.digest}",
            "alreadyLoaded": self.already_loaded,
            "content": self.content,
        }


class SkillLoader:
    """Load allowlisted Skill resources with a per-session cache."""

    _RESOURCE_FILES = {
        "instructions": Path("SKILL.md"),
        "runtime-guide": Path("references/runtime-guide.md"),
        "examples": Path("references/examples.md"),
        "user-replies": Path("references/user-replies.md"),
    }

    def __init__(
        self,
        skills_root: Path,
        skill_name: str,
        max_bytes: int = 256 * 1024,
        skill_directory: Path | None = None,
    ) -> None:
        self.skills_root = skills_root.resolve()
        self.skill_name = skill_name
        self.skill_root = (skill_directory or self.skills_root / skill_name).resolve()
        self.max_bytes = max_bytes
        self._loaded: dict[str, SkillResource] = {}
        self.catalog = self._read_catalog()

    def _read_catalog(self) -> SkillCatalog:
        path = self._safe_path(Path("SKILL.md"))
        content = self._read_text(path)
        frontmatter = self._frontmatter(content)
        name_match = re.search(r"^name:\s*([^\n]+)$", frontmatter, re.MULTILINE)
        description_match = re.search(
            r"^description:\s*(?:[\"'](?P<quoted>.*?)[\"']|(?P<plain>[^\n]+))$",
            frontmatter,
            re.MULTILINE,
        )
        name = name_match.group(1).strip().strip("\"'") if name_match else ""
        if name != self.skill_name:
            raise SkillLoadError("Skill frontmatter name does not match configuration")
        description = ""
        if description_match:
            description = (
                description_match.group("quoted") or description_match.group("plain") or ""
            ).strip()
        tools = tuple(
            {"bundleName": bundle, "toolName": tool}
            for bundle, tool in re.findall(
                r"-\s+bundleName:\s*[\"']([^\"']+)[\"']\s*\n\s*toolName:\s*[\"']([^\"']+)[\"']",
                frontmatter,
            )
        )
        return SkillCatalog(name=name, description=description, tools=tools)

    @staticmethod
    def _frontmatter(content: str) -> str:
        if not content.startswith("---"):
            raise SkillLoadError("SKILL.md is missing frontmatter")
        end = content.find("\n---", 3)
        if end < 0:
            raise SkillLoadError("SKILL.md frontmatter is not closed")
        return content[3:end]

    def _safe_path(self, relative: Path) -> Path:
        candidate = (self.skill_root / relative).resolve()
        try:
            candidate.relative_to(self.skill_root)
        except ValueError as exc:
            raise SkillLoadError("Skill resource path escapes skill root") from exc
        if not candidate.is_file():
            raise SkillLoadError("Skill resource does not exist")
        return candidate

    def _read_text(self, path: Path) -> str:
        if path.stat().st_size > self.max_bytes:
            raise SkillLoadError("Skill resource exceeds size limit")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise SkillLoadError("Skill resource is not valid UTF-8") from exc

    def reset(self) -> None:
        self._loaded.clear()
        self.catalog = self._read_catalog()

    def load(self, resource_id: str) -> SkillResource:
        if not isinstance(resource_id, str):
            raise SkillLoadError("resourceId must be a string")
        if not resource_id.strip():
            raise SkillLoadError("resourceId must not be empty")
        logical_id = self._logical_resource_id(resource_id)
        if logical_id is None:
            raise SkillLoadError("unknown Skill logical resource")
        if logical_id.startswith("tool:"):
            relative = Path("references/tools") / self._tool_snapshot_name(
                logical_id.removeprefix("tool:")
            )
            path = self._safe_path(relative)
        else:
            path = self._find_resource_path(logical_id, resource_id)
        cached = self._loaded.get(logical_id)
        if cached is not None:
            return SkillResource(
                skill_name=cached.skill_name,
                resource_id=logical_id,
                digest=cached.digest,
                content=cached.content,
                already_loaded=True,
            )
        content = self._read_text(path)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        resource = SkillResource(
            skill_name=self.skill_name,
            resource_id=logical_id,
            digest=digest,
            content=content,
            already_loaded=False,
        )
        self._loaded[logical_id] = resource
        return resource

    @classmethod
    def _logical_resource_id(cls, resource_id: str) -> str | None:
        stripped = resource_id.strip().strip("`\"'").strip()
        if not stripped:
            return None
        normalized = stripped.replace("\\", "/")
        if normalized.lower().startswith("skill://"):
            normalized = normalized[8:]
        normalized = normalized.lstrip("/")
        if any(part == ".." for part in normalized.split("/")):
            return None
        while normalized.startswith("./"):
            normalized = normalized[2:]
        aliases = {
            "skill.md": "instructions",
            "skill": "instructions",
            "instructions": "instructions",
            "runtime-guide": "runtime-guide",
            "runtime-guide.md": "runtime-guide",
            "runtime_guide": "runtime-guide",
            "runtime_guide.md": "runtime-guide",
            "references/runtime-guide": "runtime-guide",
            "references/runtime-guide.md": "runtime-guide",
            "references/runtime_guide": "runtime-guide",
            "references/runtime_guide.md": "runtime-guide",
            "examples": "examples",
            "examples.md": "examples",
            "references/examples": "examples",
            "references/examples.md": "examples",
            "user-replies": "user-replies",
            "user-replies.md": "user-replies",
            "references/user-replies": "user-replies",
            "references/user-replies.md": "user-replies",
        }
        direct = aliases.get(normalized.lower())
        if direct is not None:
            return direct
        lowered = normalized.lower()
        for suffix, logical_id in (
            ("/references/runtime-guide.md", "runtime-guide"),
            ("/references/runtime-guide", "runtime-guide"),
            ("/references/runtime_guide.md", "runtime-guide"),
            ("/references/runtime_guide", "runtime-guide"),
            ("/references/examples.md", "examples"),
            ("/references/examples", "examples"),
            ("/references/user-replies.md", "user-replies"),
            ("/references/user-replies", "user-replies"),
            ("/skill.md", "instructions"),
        ):
            if lowered.endswith(suffix):
                return logical_id
        if normalized.startswith("tool:"):
            tool_name = normalized.removeprefix("tool:").strip()
            return f"tool:{tool_name}" if tool_name else None
        return None

    def _find_resource_path(self, logical_id: str, requested_id: str) -> Path:
        relative = self._RESOURCE_FILES.get(logical_id)
        if relative is None:
            raise SkillLoadError("unknown Skill logical resource")
        for root in self._resource_roots():
            candidate = (root / relative).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise SkillLoadError("Skill resource path escapes skill root") from exc
            if candidate.is_file():
                return candidate
        raise SkillLoadError(f"Skill resource does not exist: {requested_id}")

    def _resource_roots(self) -> tuple[Path, ...]:
        roots = [self.skill_root]
        if not self.skills_root.is_dir():
            return tuple(roots)
        for directory in sorted(self.skills_root.iterdir(), key=lambda item: item.name.lower()):
            resolved = directory.resolve()
            if resolved == self.skill_root or not directory.is_dir():
                continue
            try:
                resolved.relative_to(self.skills_root)
            except ValueError:
                continue
            skill_file = directory / "SKILL.md"
            if not skill_file.is_file():
                continue
            try:
                content = skill_file.read_text(encoding="utf-8")
                frontmatter = self._frontmatter(content)
            except (OSError, UnicodeDecodeError, SkillLoadError):
                continue
            name_match = re.search(r"^name:\s*([^\n]+)$", frontmatter, re.MULTILINE)
            name = name_match.group(1).strip().strip("\"'") if name_match else ""
            if name == self.skill_name:
                roots.append(resolved)
        return tuple(roots)

    def load_for_model(self, resource_id: str) -> dict[str, Any]:
        resource = self.load(resource_id)
        return resource.as_dict()

    def _tool_snapshot_name(self, tool_name: str) -> str:
        for item in self.catalog.tools:
            if item["toolName"] == tool_name:
                bundle = item["bundleName"]
                return f"{bundle}__{tool_name}.json"
        raise SkillLoadError("unknown Skill tool snapshot")

    @property
    def loaded_resource_ids(self) -> frozenset[str]:
        return frozenset(self._loaded)

