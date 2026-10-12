"""操作标识与内容名称的中文语义，集中维护调试展示词汇。"""

OPERATION_TITLES = {
    "request": "请求全链路",
    "interface.attempt": "生成尝试",
    "prepare": "请求准备",
    "plan": "生成计划",
    "dsl": "生成 DSL",
    "validation": "转换与校验",
    "repair": "质量修复",
    "artifact": "保存产物",
    "response": "返回结果",
    "protocol.selection.completed": "选择卡片协议",
    "source_artifact.completed": "读取编辑源产物",
    "registry.completed": "读取能力清单",
    "generation_preflight.completed": "能力裁决与生成预检",
    "dsl_prompt.built": "构建基础提示词",
    "plan.prompt.built": "构建计划提示词",
    "plan.attempt": "计划尝试",
    "plan.validation.completed": "解析与校验计划",
    "model.physical_call": "模型调用",
    "model.queue": "等待模型执行配额",
    "model.provider_execution": "执行模型请求",
    "model.retry_backoff": "模型重试等待",
    "model.output.processed": "提取模型输出",
    "repair.attempt": "修复尝试",
    "repair.prompt.built": "构建修复提示词",
    "validation.evaluate": "质量评估",
    "dsl.processing": "DSL 处理",
    "dsl.binding_repair.completed": "修正数据绑定",
    "dsl.plan_coverage_validation.completed": "校验计划覆盖",
    "dsl.compact_validation.completed": "校验 Compact DSL",
    "dsl.conversion.completed": "转换为标准 A2UI",
    "dsl.unit_repair.completed": "修正展示单位",
    "dsl.asset_mapping.completed": "映射资源地址",
    "artifact.candidate.built": "构建待校验产物",
    "artifact_validation.completed": "校验卡片产物",
    "artifact.final.built": "构建最终产物",
    "artifact.store": "保存与上传",
    "artifact.payload_built": "序列化产物",
    "artifact.digest_calculated": "计算产物摘要",
    "artifact.local_write": "保存本地产物",
    "artifact.upload": "上传产物",
    "response_plan.completed": "决定返回状态",
}

CONTENT_LABELS = {
    "raw_request": "原始请求",
    "normalized_generation_request": "归一化请求",
    "card_spec": "卡片规格",
    "task_spec": "生成任务规格",
    "preflight_issues": "预检问题",
    "preflight_warnings": "预检告警",
    "protocol_selection": "协议选择结果",
    "source_artifact": "编辑源产物",
    "accepted_plan": "通过的生成计划",
    "plan_validation_input": "待校验计划",
    "plan_validation_errors": "计划校验错误",
    "plan_warnings": "计划校验告警",
    "plan_prompt": "计划提示词",
    "plan_repair_prompt": "计划修复提示词",
    "dsl_prompt_base": "基础 DSL 提示词",
    "dsl_prompt_final": "最终 DSL 提示词",
    "generation_response": "最终业务响应",
    "dsl_processing_input": "待处理 DSL",
    "dsl_processing_output": "处理后 DSL",
    "dsl_processing_issues": "处理问题",
    "repair_quality_errors": "修复依据",
    "repair_prompt": "修复提示词",
    "repair_invalid_source_dsl": "待修复 DSL",
    "final_artifact": "最终卡片产物",
    "artifact_save_result": "产物保存结果",
    "artifact_validation_input": "待校验卡片产物",
    "artifact_validation_result": "产物校验结果",
    "compact_validation_input": "待校验 Compact DSL",
    "compact_validation_result": "DSL 校验结果",
    "compact_validation_errors": "DSL 校验错误",
    "coverage_validation_input": "计划覆盖校验输入",
    "plan_coverage_result": "计划覆盖校验结果",
    "plan_coverage_errors": "计划覆盖错误",
    "binding_repair_input": "绑定修正前 DSL",
    "compact_dsl_binding_repaired": "绑定修正后 DSL",
    "conversion_input": "转换前 DSL",
    "standard_a2ui_before_unit_repair": "转换后 A2UI",
    "unit_repair_input": "单位修正前 A2UI",
    "standard_a2ui_after_unit_repair": "单位修正后 A2UI",
    "final_genui": "交付 GenUI",
}


def operation_title(operation: str, attempts: dict) -> str:
    title = OPERATION_TITLES.get(operation, f"未命名步骤 · {operation}")
    dimension = {
        "interface.attempt": "interface",
        "plan.attempt": "plan",
        "repair.attempt": "qualityRepair",
        "model.physical_call": "modelPhysical",
        "validation.evaluate": "validation",
    }.get(operation)
    attempt = attempts.get(dimension) if dimension else None
    if isinstance(attempt, int):
        title = f"{title} · 第 {attempt} 次"
    return title


def content_label(name: str) -> str:
    label = CONTENT_LABELS.get(name)
    if label is None:
        for suffix, value in (
            ("_model_messages", "模型完整 Messages"),
            ("_assistant_raw", "模型原文"),
            ("_assistant_partial_recovered", "恢复的模型原文"),
            ("_extracted_output", "提取后的输出"),
            ("_extraction_input", "提取前模型原文"),
        ):
            if name.endswith(suffix):
                label = value
                break
    return label or name
