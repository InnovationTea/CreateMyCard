"""Batch generation pipeline orchestration."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .config import DEFAULT_DELAY, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, DEFAULT_TIMEOUT
from .dsl_parser import extract_jsonl_from_text
from .io_utils import read_queries, write_item_dat, write_item_json, write_results
from .llm_client import build_request_body, call_api, extract_text_from_response
from .prompt_builder import assemble_system_prompt, build_user_prompt, extract_keywords as extract_keyword_list, load_few_shot
from .validator_adapter import parse_validation_output, run_validator


def generate_for_query(
    query_id: str,
    query_text: str,
    system_prompt: str,
    api_config: dict[str, str],
    temperature: float | None = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    request_timeout: int = DEFAULT_TIMEOUT,
    validate_enabled: bool = False,
    extract_keywords: bool = True,
    few_shot: str = "",
    max_retry: int = 1,
) -> dict[str, Any]:
    start_time = time.time()
    base_url = api_config["base_url"]
    auth_token = api_config["auth_token"]
    model = api_config["model"]

    dsl_text = ""
    keywords: list[str] = []
    validation: dict[str, Any] = {
        "ok": False,
        "errors": [],
        "warnings": [],
        "message_count": 0,
        "component_count": 0,
        "score": 0,
    }
    error: str | None = None
    retry_count = 0

    for attempt in range(max_retry + 1):
        is_retry = attempt > 0
        print(f"  [GEN] attempt {attempt + 1}/{max_retry + 1} calling model...", flush=True)
        prompt = build_user_prompt(
            query_text,
            extract_keywords,
            few_shot=few_shot,
            last_errors=validation["errors"] if is_retry else None,
            last_dsl=dsl_text if is_retry and dsl_text else None,
        )

        try:
            body = build_request_body(system_prompt, prompt, model, temperature, max_tokens)
            response = call_api(base_url, auth_token, body, request_timeout)
            raw_text = extract_text_from_response(response)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            error = f"API 调用失败 (attempt {attempt + 1}): {exc}"
            break

        if extract_keywords and not keywords:
            keywords = extract_keyword_list(raw_text, query_text)

        dsl_text, dsl_stats = extract_jsonl_from_text(raw_text)
        if not dsl_text.strip():
            error = (
                f"无有效 DSL，尝试次数 {attempt + 1}: "
                f"总行数 {dsl_stats['total_lines']}，有效行数 {dsl_stats['valid_lines']}"
            )
            continue

        if validate_enabled:
            try:
                validation = parse_validation_output(run_validator(dsl_text))
            except Exception as exc:
                validation = {
                    "ok": False,
                    "errors": [f"校验器异常: {exc}"],
                    "warnings": [],
                    "message_count": 0,
                    "component_count": 0,
                    "score": 0,
                    "dimension_scores": {},
                }
            retry_count = attempt + 1
            if validation["ok"]:
                print(f"  [PASS] 校验通过 (attempt {attempt + 1})，分数: {validation.get('score', 0)}")
                for warning in validation["warnings"]:
                    print(f"    [WARN] 警告: {warning}")
                break
            print(f"  [FAIL] 校验失败 (attempt {attempt + 1})，分数: {validation.get('score', 0)}")
            for err in validation["errors"]:
                print(f"    错误: {err}")
            if attempt < max_retry:
                print("  -> 将用错误信息重试...")
        else:
            validation["ok"] = True
            validation["score"] = -1
            retry_count = attempt + 1
            break

    return {
        "id": query_id,
        "query": query_text,
        "dsl": dsl_text,
        "validation": validation,
        "model": model,
        "elapsed_ms": int((time.time() - start_time) * 1000),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": error,
        "keywords": keywords,
        "retry_count": retry_count,
    }


def process_batch(
    input_path: Path,
    output_path: Path,
    item_output_dir: Path,
    skill_dir: Path,
    api_config: dict[str, str],
    temperature: float | None = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    request_timeout: int = DEFAULT_TIMEOUT,
    delay_between_queries: float = DEFAULT_DELAY,
    validate_enabled: bool = False,
    write_items: bool = False,
    extract_keywords: bool = True,
    max_retry: int = 1,
) -> None:
    queries = read_queries(input_path)
    total = len(queries)
    print(f"已加载 {total} 条 query")
    print(f"静态校验: {'[ON] 开启' if validate_enabled else '[OFF] 关闭'}")
    if validate_enabled:
        print(f"最多重试: {max_retry} 次（总共尝试 {max_retry + 1} 次）")
    print()

    print("正在组装 system prompt...")
    system_prompt = assemble_system_prompt(skill_dir)
    few_shot = load_few_shot(skill_dir)
    print(f"System prompt 长度: {len(system_prompt)} 字符")
    if few_shot:
        print(f"Few-shot 长度: {len(few_shot)} 字符")
    print()

    passed = 0
    failed = 0
    errored = 0
    all_results: list[dict[str, Any]] = []

    for idx, q in enumerate(queries, 1):
        qid = q["id"]
        qtext = q["query"]
        print(f"[{idx}/{total}] Processing {qid}: {qtext}")

        result = generate_for_query(
            query_id=qid,
            query_text=qtext,
            system_prompt=system_prompt,
            api_config=api_config,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
            validate_enabled=validate_enabled,
            extract_keywords=extract_keywords,
            few_shot=few_shot,
            max_retry=max_retry,
        )
        result["input_metadata"] = {
            key: value for key, value in q.items() if key not in {"id", "query"}
        }

        all_results.append(result)
        write_results(output_path, all_results)

        if write_items:
            item_path = write_item_json(item_output_dir, result)
            dat_path = write_item_dat(item_output_dir, result)
            if item_path:
                print(f"  -> Saved item: {item_path}")
            if dat_path:
                print(f"  -> Saved DSL:  {dat_path}")
        print(f"  -> Updated summary: {output_path}")

        if result["error"]:
            errored += 1
            print(f"  -> ERROR: {result['error']}")
        elif validate_enabled:
            if result["validation"]["ok"]:
                passed += 1
                warnings = result["validation"].get("warnings", [])
                suffix = f", {len(warnings)} warnings" if warnings else ""
                print(
                    f"  -> PASS (score: {result['validation'].get('score', 0)}, "
                    f"{result['elapsed_ms']}ms{suffix})"
                )
            else:
                failed += 1
                errors = result["validation"].get("errors", [])
                print(
                    f"  -> FAIL (score: {result['validation'].get('score', 0)}, "
                    f"{result['elapsed_ms']}ms, {len(errors)} errors)"
                )
                for err in errors:
                    print(f"     - {err}")
        else:
            passed += 1
            print(f"  -> OK ({result['elapsed_ms']}ms)")

        if idx < total and delay_between_queries > 0:
            time.sleep(delay_between_queries)

    print("\n" + "=" * 50)
    print("=== Summary ===")
    print(f"Total:   {total} queries")
    if validate_enabled:
        print(f"Passed:  {passed} (validation ok)")
        print(f"Failed:  {failed} (validation errors)")
    else:
        print(f"Success: {passed} (generated ok)")
    print(f"Errored: {errored} (unrecoverable)")
    print(f"Output:  {output_path}")
    if write_items:
        print(f"Items:   {item_output_dir}")
        print("DSL dat: " + str(item_output_dir))
