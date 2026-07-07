# 01-commands.md: Full Command Reference

## Common Parameters (available for all commands)
| Parameter | Default | Description |
|---|---|---|
| --project-root | Current directory | Project root directory path |
| --sn | None | Target device SN (required for single device execution when multiple devices are connected) |
| --deveco-sdk-home | None | DevEco SDK path, default: D:\DevEco Studio\sdk |
| --java-home | None | DevEco JDK path, default: D:\DevEco Studio\jbr |
| --enable-aesthetics | False | Enable UI aesthetic scoring functionality after screenshot |
| --aesthetics-base-url | None | Doubao API endpoint: https://ark.cn-beijing.volces.com/api/plan/v3 |
| --aesthetics-api-key | None | Volcano Ark API key |
| --aesthetics-model | doubao-seed-2-0-lite | Scoring model name |
| --aesthetics-disable-cache | True | Disable API result caching (default off) |
| --build-timeout | 300s | HAP build timeout |
| --extract-delay | 30s | Wait time after query send before extracting DSL |

---

## Command Details
### 1. one - Run single manual query
`
python Automation/main.py one --query <QUERY_TEXT> [--qid <QUERY_ID>] [OPTIONS]
`
**Use when**: Testing single query, ad-hoc runs

### 2. one-from-file - Run single query from queries.jsonl
`
python Automation/main.py one-from-file --qid <QUERY_ID> [--queries <QUERY_FILE_PATH>] [OPTIONS]
`
**Use when**: Reproducing existing query test cases

### 3. atch - Run all queries in query file
`
python Automation/main.py batch [--queries <QUERY_FILE_PATH>] [OPTIONS]
`
**Use when**: Full regression testing, batch processing of multiple queries

### 4. parallel - Run batch on multiple devices in parallel
`
python Automation/main.py parallel --devices <auto|SN1,SN2,SN3> [--max-workers <MAX_PARALLEL>] [OPTIONS]
`
**Use when**: Multi-device compatibility testing, large scale batch processing

### 5. esthetics - Standalone scoring command
`
python Automation/main.py aesthetics --input <IMAGE_PATH|DIR_PATH> --output <OUTPUT_PATH> [OPTIONS]
`
**Use when**: Manual scoring of existing screenshots, batch scoring of image directories
