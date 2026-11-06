"""动态 Plan 的列表成员复核，使用已有的 Plan 预算和可见数据路径。"""

import re
from collections.abc import Awaitable, Callable

from app.logger import logger
from custom.a2ui_model_client import A2UIModelGenerationError
from services.compact_plan import (
    CompactPlanValidationError,
    CompactPlanValidationResult,
    compact_plan_data_paths,
    parse_compact_plan_call,
)
from services.generation_trace_recorder import (
    trace_attempt,
    trace_increment_attempt,
    trace_increment_retry,
    trace_record,
)

_LIST_QUERY = re.compile(
    r"列表|清单|明细|记录|逐条|每条|各条|多条|最近|近期|近几|前[两二三四五六七八九\d]"
)
_SINGLE_QUERY = re.compile(
    r"(?:(?:最近|最新|最后)(?:的)?(?:一|1|那|这)|上一|下一|第一|首)(?:条|次|项|笔|场|件|个|通)"
    r"|前(?:一|1)(?:条|项|个|通)"
    r"|(?:只|仅)(?:需|要|看|显示|展示|保留|取|返回)*(?:最近的|最新|首个|一个|一条|单条|1条)"
)
_MEMBER_PATH = re.compile(r"(?P<collection>/[^\s]*?)/(?P<index>\d+)/(?P<field>.+)")


def second_member_targets(plan: dict, task: dict) -> tuple[str, ...]:
    query = task.get("userQuery", "")
    if not _LIST_QUERY.search(query) or _SINGLE_QUERY.search(query):
        return ()
    available = set(compact_plan_data_paths(task))
    collections: set[str] = set()
    targets: list[str] = []
    for fact in plan.get("info_required", []):
        path = fact.get("dataId")
        if not isinstance(path, str):
            continue
        match = _MEMBER_PATH.fullmatch(path)
        if match is None:
            continue
        if match.group("index") != "0":
            return ()
        collection = match.group("collection")
        collections.add(collection)
        sibling = f"{collection}/1/{match.group('field')}"
        if sibling in available and fact.get("priority") == "must":
            targets.append(sibling)
    return tuple(dict.fromkeys(targets)) if len(collections) == 1 else ()


def _protected_fact_keys(plan: dict) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for fact in plan.get("info_required", []):
        if fact.get("priority") != "must" and not fact.get("actionId"):
            continue
        for kind in ("dataId", "actionId", "text"):
            value = fact.get(kind)
            if isinstance(value, str):
                keys.add((kind, value))
    return keys


def list_review_complete(original: dict, revised: dict, targets: tuple[str, ...]) -> bool:
    required = _protected_fact_keys(original)
    required.update(("dataId", path) for path in targets)
    return required <= _protected_fact_keys(revised)


def list_review_instruction(targets: tuple[str, ...]) -> str:
    return (
        "这是同一请求的最后一次 Plan 复核。上一版选了列表首个成员；第二个成员有以下已声明的"
        "对应核心 dataId，请将它们逐项以 must 写入 info_required，与首个成员相同字段成组：\n"
        + "\n".join(targets)
        + "\n保留原 must、动作、公共信息及真实绑定，容量紧张先收敛未要求的可选细节。"
        "两个成员可用两条完整摘要或共享表头；公共日期、时间按完整格式选较宽位置。"
        "按同一数组的成员下标归组，身份与属性使用对应排版，公共信息单独安排。"
        "并列短值先核对扣除间距与内边距后的文字宽度，完整值超宽时改选较宽的合法正文位置。"
        "使用原 submit_card_plan 工具格式返回一个完整 Plan。"
    )


async def review_list_plan(
    original: CompactPlanValidationResult,
    conversation: list[dict[str, str]],
    task: dict,
    targets: tuple[str, ...],
    *,
    require_composition: bool,
    generate: Callable[[list[dict[str, str]]], Awaitable[str]],
) -> CompactPlanValidationResult:
    messages = [*conversation, {"role": "user", "content": list_review_instruction(targets)}]
    logger.info("[Generation Service] list_plan_review_started target_count={}", len(targets))
    with trace_attempt(plan=2):
        trace_increment_retry("planSemanticReviews")
        trace_increment_attempt("planContractAttempts")
        trace_record(
            "plan.list_review.scheduled",
            stage="plan",
            status="started",
            json_artifacts={"list_review_targets": list(targets), "review_prompt": messages},
        )
        try:
            raw = await generate(messages)
            trace_record(
                "plan.list_review.output",
                stage="plan",
                status="success",
                text_artifacts={"list_review_submission": raw},
            )
            revised = parse_compact_plan_call(raw, task, require_composition=require_composition)
            if not list_review_complete(original.plan, revised.plan, targets):
                raise CompactPlanValidationError(["复核计划缺少第二成员核心字段或原有保护事实"])
        except (CompactPlanValidationError, A2UIModelGenerationError) as exc:
            logger.warning(
                "[Generation Service] list_plan_review_kept_original reason={}", str(exc)
            )
            trace_record(
                "plan.list_review.fallback",
                stage="plan",
                status="failed",
                details={"reason": str(exc)},
            )
            return original
        # 后续 DSL 只继承最终有效提交，避免再次执行复核指令。
        conversation[-1] = {"role": "assistant", "content": raw}
        logger.info("[Generation Service] list_plan_review_accepted target_count={}", len(targets))
        trace_record(
            "plan.list_review.accepted",
            stage="plan",
            status="success",
            json_artifacts={"reviewed_plan": revised.plan},
        )
        return revised
