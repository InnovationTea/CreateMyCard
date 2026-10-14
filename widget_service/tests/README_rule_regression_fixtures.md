# R02–R97 校验规则回归测试

## 目的

本测试集为卡片校验器的 R02–R97 共 96 条规则提供逐条回归覆盖。每个规则编号对应一个独立 pytest 参数用例，读取其负例夹具，并断言目标诊断码出现，避免只运行少量历史专项用例而遗漏规则。

测试入口：`test_rule_regression_fixtures.py`

## 目录与依赖

- `widget_service/tests/test_artifact/<ValidatorName>/R##_规则码_0.json`：规则未注入错误的对照夹具。
- `widget_service/tests/test_artifact/<ValidatorName>/R##_规则码_1.json`：注入单个目标错误的负例夹具，由参数化用例读取。
- `widget_service/cloud/services/card_validation/`：被测校验实现，包括 `validate_card`、各 Validator、上下文、诊断报告及规则注册器。
- `widget_service/cloud/data/validator_rules/`：项目实际规则配置目录，包含协议、组件、表达式、样式、素材和诊断配置等文件。

测试文件中的 `RULE_CODES` 将 R02–R97 映射到期望诊断码。`test_all_96_rule_directories_exist` 检查负例夹具覆盖编号完整；`test_every_rule_fixture_hits_declared_diagnostic` 对 96 个编号分别加载 `_1.json` 并断言目标码。

R56、R92、R93、R97 是特殊单点测试：由于公开入口的解析或前置校验可能先拦截输入，测试在测试代码中构造最小 `ValidationContext`，直接执行对应 Validator 分支。R56 还对表达式引用收集做了局部 monkeypatch，以覆盖空引用边界。此做法只用于测试，不修改校验器实现。

## 运行方式

在仓库根目录执行：

```powershell
python -m pytest widget_service/tests/test_rule_regression_fixtures.py -q
```

单独运行某一规则（例如 R56）：

```powershell
python -m pytest 'widget_service/tests/test_rule_regression_fixtures.py::test_every_rule_fixture_hits_declared_diagnostic[R56]' -q
```

## 最近一次测试结果

最近一次执行上述完整测试文件的结果：

```text
107 passed, 15 warnings in 1.24s
```

其中 96 个参数化用例覆盖 R02–R97，另有 10 个既有专项用例和 1 个夹具完整性检查。15 条 warning 来自 Pydantic 对若干 `model_` 前缀字段与 protected namespace 的提示；测试均通过。

静态与差异检查结果：

```text
ruff check widget_service/tests/test_rule_regression_fixtures.py  -> All checks passed
git diff --check                                                -> 通过
```
