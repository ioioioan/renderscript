# Release Checklist

This is the short version of the RenderScript release workflow.

Use it when you want to:

- ship changes to the public open-core repo
- refresh the app deployment branch
- avoid forgetting a branch or push step

## Rule First

Do all real development on `main`.

Do not build features directly on:

- `publish/open-core`
- `deploy/app`

## Standard Release Flow

### 1. Finish work on `main`

```bash
git checkout main
git status
python3 -m pytest -q
```

Before moving on:

- working tree should be clean
- tests should pass

### 2. Push `main` to the private repo

```bash
git push origin main
```

### 3. Refresh the open-core branch if needed

Use this when the change belongs in the public engine/CLI repo.

Examples:

- compiler changes
- package generation
- provider adapters
- CLI updates
- examples
- public docs
- engine tests

```bash
git checkout publish/open-core
git merge main
python3 -m pytest -q
git push origin publish/open-core
git push public publish/open-core:main
```

Before pushing public:

- make sure `app/` is not tracked there
- make sure generated output is not tracked there
- keep only public-facing docs

### 4. Refresh the deployment branch if needed

Use this when the change belongs in the hosted app/runtime.

Examples:

- UI changes
- FastAPI app changes
- templates
- runtime assets
- app-side packaging behavior

```bash
git checkout deploy/app
git merge main
git push origin deploy/app
```

Before pushing:

- keep runtime files only
- do not keep tests/examples/docs unless intentionally needed

### 5. Return to `main`

```bash
git checkout main
```

## Fast Decision Rule

Ask this:

### Does the change matter to public developers using the CLI?

If yes:

- promote to `publish/open-core`

### Does the change matter to the hosted app/runtime?

If yes:

- promote to `deploy/app`

### Does it matter to both?

If yes:

- merge into both release branches after it lands on `main`

## Tiny Safety Checklist

Before every push:

- `git branch --show-current`
- `git status`
- confirm the remote branch you are about to update

## Common Commands

Check remotes:

```bash
git remote -v
```

Check branches:

```bash
git branch --list
```

Check remote branch state:

```bash
git ls-remote --heads origin
git ls-remote --heads public
```

## The Habit To Keep

Use this mental model:

- `main` evolves the product
- `publish/open-core` publishes the engine
- `deploy/app` runs the hosted app

If you keep those roles clean, releases stay manageable.
