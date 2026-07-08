---
name: gitpush
description: Commit local Git changes and push them to the user's fork remote in a fork-based repository with origin and upstream configured. Use when the user asks to run gitpush, /gitpush, commit and push current changes, or optionally run gitpush --squash to squash the current feature branch into one commit before pushing with --force-with-lease.
---

# GitPush

Run one fork-based commit-and-push workflow. Treat squash as an optional preparation step, not a separate workflow.

## Invocation

- Use the default path for `gitpush`, `/gitpush`, or requests to commit and push current changes.
- Enable squash mode only when the user explicitly passes `--squash`, says `/gitpush --squash`, or clearly asks to squash the branch before pushing.
- In squash mode, accept an optional target branch argument. For unqualified names like `develop`, resolve to `upstream/develop` because the squash base should normally be the source repository's integration branch. Use `origin/<target>` only when the user explicitly supplies a remote-qualified ref like `origin/release`. Keep remote-qualified refs like `origin/release` or `upstream/release` unchanged.

## Workflow

1. Record the start time.
2. Verify the current directory is inside a Git worktree:

```bash
git rev-parse --is-inside-work-tree
```

3. Verify `HEAD` is attached to a branch:

```bash
git branch --show-current
```

4. Inspect the worktree:

```bash
git status --porcelain
```

5. Verify required remotes are configured before creating a commit:

```bash
git remote
git remote get-url origin
git remote get-url upstream
```

If `origin` is missing, stop and tell the user: `origin` must point to the user's fork of the source repository. If `upstream` is missing, stop and tell the user: `upstream` must point to the source repository.

6. If squash mode is enabled, run the squash preparation steps below before generating the final commit message.
7. Stage all current changes:

```bash
git add -A
```

8. Inspect staged changes:

```bash
git diff --cached --stat
git diff --cached --name-status
```

9. If there is no staged content, stop and report that there is nothing to commit.
10. Generate a concise Chinese Conventional Commit message from the staged diff:

```text
feat: 描述
fix: 描述
docs: 描述
style: 描述
refactor: 描述
test: 描述
chore: 描述
```

Use `chore: 更新代码` only when the type cannot be inferred.

11. Commit:

```bash
git commit -m "提交信息"
```

12. Push to the user's writable fork remote, `origin`:

```bash
git push origin CURRENT_BRANCH
```

If the branch has no upstream, also set it:

```bash
git push -u origin CURRENT_BRANCH
```

If squash mode was enabled, push with lease protection instead:

```bash
git push --force-with-lease origin CURRENT_BRANCH
```

If squash mode was enabled and the branch has no upstream, use:

```bash
git push -u origin CURRENT_BRANCH --force-with-lease
```

Never use `git push --force`.

## Squash Preparation

Run these steps only when squash mode is enabled.

1. Stop immediately if the current branch is protected:

```text
main
master
develop
dev
release
staging
production
prod
```

2. Verify and fetch remote refs. `origin` must point to the user's fork of the source repository, and `upstream` must point to the source repository. Stop with that guidance if either remote is missing:

```bash
git remote
git remote get-url origin
git remote get-url upstream
git fetch origin
git fetch upstream
```

3. Resolve the target branch:

- If the user supplied a remote-qualified target like `upstream/main` or `origin/develop`, use it as given.
- If the user supplied an unqualified target like `main` or `develop`, resolve it to `upstream/<target>`. Do not fall back to `origin/<target>` unless the user explicitly supplied the remote-qualified `origin/<target>` ref.
- If the user did not supply a target, choose the first existing ref from `upstream/main`, `upstream/master`, then `upstream/develop`. If none exists, stop and ask the user for an explicit target branch.

Verify the selected target exists:

```bash
git rev-parse --verify TARGET_BRANCH
```

4. Verify the target branch is an ancestor of `HEAD`:

```bash
git merge-base --is-ancestor TARGET_BRANCH HEAD
```

If this fails, stop. Tell the user to rebase or merge the target branch first. This prevents a squash commit from accidentally reverting changes that exist on the target branch.

5. Count commits to squash:

```bash
git rev-list --count TARGET_BRANCH..HEAD
```

If the count is `0` and the worktree is clean, stop and report that there is nothing to commit.

6. Stage uncommitted work so it is included in the squashed commit:

```bash
git add -A
```

7. Capture summary information before rewriting:

```bash
git rev-list --count TARGET_BRANCH..HEAD
git diff --cached --name-status
git diff --name-status TARGET_BRANCH...HEAD
```

8. Soft-reset to the target branch:

```bash
git reset --soft TARGET_BRANCH
```

After this, return to the main workflow at staged-change inspection. The final commit message should describe the whole squashed diff.

## Failure Rules

- Stop on any failed precheck, failed fetch, missing required remote (`origin` or `upstream`), missing target branch, detached `HEAD`, protected branch squash, failed commit, or rejected push.
- Preserve the relevant Git output in the final error.
- If `--force-with-lease` rejects the push, do not retry with `--force`.

## Output

On success, summarize:

- Whether squash mode was used
- Current branch
- Target branch and squashed commit count, when applicable
- Commit message
- Changed file counts
- Push result
- Elapsed time

On failure, use:

```text
提交失败
原因: <specific reason>
```
