# 02-safety-rules.md: Safety & Permission Rules

## Non-Negotiable Hard Rules
1. **DO NOT MODIFY ArkTs/ DIRECTORY FILES**
   - All builds use temporary copies created in .work/{SN}/ directory
   - Any changes to the template must be explicitly approved by the project owner

2. **NO HARDCODED SECRETS**
   - Never commit API keys, passwords, or sensitive credentials to the repository
   - All sensitive parameters must be passed via command line or environment variables

3. **NO UNAPPROVED DESTRUCTIVE ACTIONS**
   - Never delete files outside .work/, output/, dsl/ directories without explicit approval
   - Never run git reset --hard, git clean -f or other destructive git commands without approval

4. **ISOLATION BOUNDARIES**
   - All device-specific resources are isolated by SN: no cross-device file sharing or overwriting
   - Temporary files are always placed in .work/ directory, which is auto-cleaned between runs

---

## Permission Levels
| Action | Allowed | Approval Required |
|---|---|---|
| Run any pipeline commands (one/one-from-file/batch/parallel/aesthetics) | ✅ Yes | No |
| Read any files in project directory | ✅ Yes | No |
| Modify files in Automation/ or isual_aesthetics/ directories | ⚠️ Conditional | Yes, for all changes |
| Add new features or modules | ⚠️ Conditional | Yes |
| Install Python dependencies | ⚠️ Conditional | Yes |
| Modify ArkTs/ template files | ❌ No | Always required |
| Push changes to git repository | ⚠️ Conditional | Yes |
| Delete files outside .work/, output/, dsl/ | ❌ No | Always required |
