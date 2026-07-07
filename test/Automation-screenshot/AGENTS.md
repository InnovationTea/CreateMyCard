# AGENTS.md: Automation-screenshot Project Agent Runbook

## 📋 Project Overview
**Project Purpose**: Full end-to-end automation pipeline for Xiaoyi (小艺) AI assistant DSL extraction, HarmonyOS ArkTS render, screenshot capture, and AI-powered UI aesthetic scoring.
**Core Flow**: User Query → Xiaoyi chat UI detection → Query send → DSL extraction → ArkTS build/install → Render screenshot → UI aesthetic scoring → Structured report
**Tech Stack**: Python 3.12+, DevEco Studio (HarmonyOS SDK), Doubao multimodal API (Volcano Ark), HDC (HarmonyOS Device Connector)
**Project Root**: C:\Users\afan\Desktop\Automation-screenshot

---

## 🔧 Environment Setup & Dependencies
### Required Environment
1. **Python 3.12+** installed and in PATH
2. **DevEco Studio** installed at default path D:\DevEco Studio (customizable via command parameters)
   - HarmonyOS SDK included
   - DevEco自带JDK included (required for HAP signing)
3. **HDC (HarmonyOS Device Connector)** in system PATH
4. **Test device(s)** connected via USB debugging, or emulator running
5. **Doubao API access** (Volcano Ark endpoint + API key)

### First-Time Setup
1. Install Python dependencies:
`powershell
pip install -r requirements.txt
`
2. Verify HDC device connection:
`powershell
hdc list targets
`
3. Verify DevEco installation paths exist:
   - SDK path: D:\DevEco Studio\sdk
   - JDK path: D:\DevEco Studio\jbr

---

## 🚀 Available Commands
**Unified Entry Point**: python Automation/main.py <COMMAND> [OPTIONS]

### 1. Single Query Execution
Run full pipeline for one manual query:
`powershell
python Automation/main.py one --query "帮我做一个日程卡片" --qid "test1"
`
Run full pipeline for a query from queries.jsonl:
`powershell
python Automation/main.py one-from-file --qid "q1"
`

### 2. Batch Query Execution
Run full pipeline for all queries in queries.jsonl:
`powershell
python Automation/main.py batch
`
Run pipeline with aesthetic scoring enabled:
`powershell
python Automation/main.py batch --enable-aesthetics --aesthetics-base-url "https://ark.cn-beijing.volces.com/api/plan/v3" --aesthetics-api-key "your-api-key"
`

### 3. Multi-Device Parallel Execution
Run full batch pipeline on all connected devices automatically:
`powershell
python Automation/main.py parallel --devices auto
`
Run on specified devices only:
`powershell
python Automation/main.py parallel --devices "SN1,SN2,SN3"
`

### 4. Standalone Aesthetic Scoring
Score a single image:
`powershell
python Automation/main.py aesthetics --input "./output/test.png" --output "./output/result.html" --aesthetics-base-url "https://ark.cn-beijing.volces.com/api/plan/v3" --aesthetics-api-key "your-api-key"
`
Score all images in a directory and generate report:
`powershell
python Automation/main.py aesthetics --input "./output" --output "./output" --aesthetics-base-url "https://ark.cn-beijing.volces.com/api/plan/v3" --aesthetics-api-key "your-api-key"
`

---

## 📊 Aesthetic Scoring Dimensions
| Dimension | Weight | Description |
|---|---|---|
| **基础可用性** | 25% | UI functional completeness, no broken elements, text readability, no overlap/cutoff |
| **视觉一致性** | 20% | Color harmony, font consistency, spacing uniformity, design style consistency |
| **信息层级** | 20% | Clear visual hierarchy, prominent core content, logical information organization |
| **交互合理性** | 15% | Reasonable touch target size, intuitive operation flow, clear feedback signals |
| **原创性&设计感** | 20% | Design originality, visual appeal, compliance with modern UI design principles |

**Scoring Range**: 0-100 points, scores <60 are considered unqualified.

---

## 📁 Project Structure & Output Paths
### Core Directories
`
Automation/              # Core automation pipeline code
visual_aesthetics/       # AI aesthetic scoring module
ArkTs/                   # Original ArkTS project template (READ ONLY, never modify directly)
queries.jsonl            # Query case library
dsl/                     # Extracted DSL files, isolated by device SN: dsl/{SN}/{qid}.jsonl
output/                  # Output directory, isolated by device SN: output/{SN}/
  - {qid}.png            # Screenshot file
  - scores.jsonl         # Scoring result data
  - report.html          # Visual scoring report
.work/                   # Temporary working directory (auto-cleaned, never commit)
`

### Important File Paths
| Item | Path |
|---|---|
| Main entry | Automation/main.py |
| Configuration | Automation/automation/config.py |
| HDC client | Automation/automation/hdc.py |
| Pipeline logic | Automation/automation/pipeline.py |
| Scoring config | isual_aesthetics/config.py |
| Scoring rubric | isual_aesthetics/core/rubric.py |

---

## 🛡️ Safety Rules & Boundaries
### Non-Negotiable Rules
1. **Never modify files in ArkTs/ directory directly**: All builds use isolated temporary copies created in .work/{SN}/ directory per device.
2. **Never hardcode secrets/API keys in code**: All sensitive parameters must be passed via command line arguments or environment variables only.
3. **Never commit temporary/cache files**: .gitignore already excludes .work/, __pycache__, *.pyc, output/, dsl/ and other temporary files.
4. **Cache is disabled by default**: Explicitly enable only when needed via --aesthetics-disable-cache false parameter.
5. **All resources are isolated by device SN**: No cross-device conflicts for build artifacts, outputs, temporary files.

### Permissions & Escalation Rules
| Action | Permission Level |
|---|---|
| Run pipeline commands, generate outputs | ✅ Autonomous |
| Install Python dependencies | ⚠️ Ask first |
| Modify core pipeline code | ⚠️ Ask first |
| Modify ArkTs/ template files | ❌ Never |
| Delete files outside .work/, output/, dsl/ | ⚠️ Ask first |
| Push changes to git repository | ⚠️ Ask first |

---

## 🐛 Common Issues & Debugging
### 1. DevEco/SDK/JDK path errors
**Symptom**: DEVECO_SDK_HOME is not configured or JDK version mismatch
**Fix**: Add parameters --deveco-sdk-home "D:\DevEco Studio\sdk" --java-home "D:\DevEco Studio\jbr"

### 2. HDC device connection errors
**Symptom**: No HDC devices found
**Fix**: 
- Verify USB debugging is enabled on device
- Run hdc kill && hdc start to restart HDC service
- Reconnect device

### 3. Build/Install errors
**Symptom**: HAP build failed or installation failed
**Fix**:
- Check DevEco SDK version matches device HarmonyOS version
- Verify device has enough storage space
- Uninstall existing test app from device first: hdc shell bm uninstall -n yyx.test.test

### 4. Scoring API errors
**Symptom**: API call failed, timeout, or authentication error
**Fix**:
- Verify API endpoint and key are correct
- Check network connectivity to Volcano Ark service
- Increase timeout parameter: --aesthetics-timeout 600

---

## 📝 Code Conventions
- All code uses UTF-8 encoding
- Use Python type hints for all function signatures
- Comments written in Chinese for core logic
- Follow existing code structure when adding new features
- Add appropriate error handling and logging for new functionality
- Test all changes locally before committing

---

## 🧪 Validation & Testing
All changes must pass these validation steps before merging:
1. Run single query pipeline successfully: python Automation/main.py one --query "测试" --qid "test"
2. Verify DSL is extracted correctly in dsl/ directory
3. Verify screenshot is generated correctly in output/ directory
4. (Optional) Test aesthetic scoring functionality works
5. (Optional) Test parallel execution works with at least 2 devices
