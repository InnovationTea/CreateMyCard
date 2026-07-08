---
name: gitsync
description: Sync a fork's mainline branch with the source repository. Use when the user asks to run gitsync, /gitsync, sync fork, update origin from upstream, or pull upstream changes and push them to origin without merge commits.
---

# GitSync

Sync the user's fork mainline from the source repository:

```text
upstream -> local main/master -> origin
```

`origin` must point to the user's fork of the source repository. `upstream` must point to the source repository.

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

Stop if the branch name is empty.

4. Inspect the worktree:

```bash
git status --porcelain
```

If there are any uncommitted, staged, untracked, or conflicted changes, stop and tell the user to commit, stash, or discard them before syncing.

5. Verify required remotes are configured:

```bash
git remote
git remote get-url origin
git remote get-url upstream
```

If `origin` is missing, stop and tell the user: `origin` must point to the user's fork of the source repository. If `upstream` is missing, stop and tell the user: `upstream` must point to the source repository.

6. Resolve the target branch:

- If the current branch is `main` or `master`, use it.
- If the current branch is not `main` or `master`, switch to local `main` when it exists; otherwise switch to local `master` when it exists.
- If neither local `main` nor local `master` exists, stop and report that no local mainline branch exists.

Use:

```bash
git show-ref --verify refs/heads/main
git show-ref --verify refs/heads/master
git switch TARGET_BRANCH
```

Do not switch back to the original branch after syncing. The sync only updates the local mainline branch; it does not rebase feature branches.

7. Fetch upstream and verify the upstream target branch exists:

```bash
git fetch upstream
git rev-parse --verify upstream/TARGET_BRANCH
```

If `upstream/TARGET_BRANCH` is missing, stop and report the missing upstream branch.

8. Update the local target branch without merge commits:

```bash
git pull --rebase upstream TARGET_BRANCH
```

Never use plain `git pull`, `git merge`, or any command that can create a merge commit. If the rebase has conflicts or stops, stop immediately and preserve the Git output. Tell the user to resolve the rebase, then run `git rebase --continue` or `git rebase --abort`.

9. Push the updated target branch to the fork remote:

```bash
git push origin TARGET_BRANCH
```

Never use `--force` or `--force-with-lease` for gitsync. If the push is rejected, stop and preserve the Git output.

## Failure Rules

- Stop on any failed precheck, dirty worktree, detached `HEAD`, missing required remote (`origin` or `upstream`), missing local mainline branch, missing upstream target branch, failed fetch, rebase conflict, failed pull, or rejected push.
- Do not create merge commits.
- Do not auto-stash user changes.
- Do not create local `main` or `master` branches automatically.
- Do not sync or rebase feature branches.
- Preserve relevant Git output in the final error.

## Output

On success, summarize:

- Original branch
- Target branch
- Whether the workflow switched branches
- `origin` URL and `upstream` URL
- Pull/rebase result
- Push result
- Elapsed time

On failure, use:

```text
同步失败
原因: <specific reason>
```
