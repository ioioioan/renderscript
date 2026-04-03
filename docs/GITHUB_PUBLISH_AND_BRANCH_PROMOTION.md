# GitHub Publish And Branch Promotion

This guide turns the current RenderScript branch setup into a repeatable GitHub workflow.

Use it when you want to:

- back up the full product safely
- publish the open-core code to a public GitHub repo
- prepare the app deployment branch
- keep future development simple

## Recommended Repo Layout

Use two GitHub repositories.

### 1. Private repository

This is the real source-of-truth backup for the full product.

Suggested name:

- `renderscript-private`

Push these branches there:

- `main`
- `deploy/app`
- `publish/open-core` (optional, but useful to keep)

### 2. Public repository

This is the open-core GitHub repo for developers.

Suggested name:

- `renderscript`

Push this branch there:

- local `publish/open-core` -> remote `main`

This keeps:

- the full product private
- the open-core engine public
- the app deployment branch private

## Why This Layout Works

GitHub visibility is repository-level, not branch-level.

That means you cannot safely keep:

- `main` private
- `publish/open-core` public

inside the same GitHub repository.

The clean solution is:

- one private repo for the full project
- one public repo for open-core

## Remote Naming

Use these local remote names:

- `origin` -> private full-product repo
- `public` -> public open-core repo

This keeps the commands easy to remember.

## Initial Setup Commands

Run these from your local RenderScript repository.

### Add the private repo remote

```bash
git checkout main
git remote add origin <PRIVATE_REPO_URL>
git push -u origin main
git push origin deploy/app
git push origin publish/open-core
```

### Add the public repo remote

```bash
git remote add public <PUBLIC_REPO_URL>
git push -u public publish/open-core:main
```

That last command means:

- local branch: `publish/open-core`
- public GitHub branch: `main`

## Safe Remote Check Commands

Use these before pushing if you want to sanity-check the setup:

```bash
git remote -v
git branch --show-current
git branch --list
```

Use these after pushing:

```bash
git ls-remote --heads origin
git ls-remote --heads public
```

## Day-To-Day Development Strategy

All real development should happen from `main`.

Use short-lived feature or fix branches from `main`, then merge back into `main`.

Examples:

- `feature/new-provider-pack`
- `feature/package-map-update`
- `fix/pdf-copy`
- `fix/ui-upload-validation`

Do not build new features directly on:

- `publish/open-core`
- `deploy/app`

Those are release branches, not working branches.

## Promotion Strategy

When a feature is finished on `main`, decide where it needs to go.

### If it should go to open-core

The change belongs in the public engine/CLI offering.

Typical examples:

- compiler changes
- package generation
- prompt-pack logic
- provider adapters
- CLI changes
- engine tests
- examples
- engine docs

Promotion flow:

```bash
git checkout publish/open-core
git merge main
```

Then trim or review anything that should not stay in the public branch before pushing.

Finally:

```bash
git push origin publish/open-core
git push public publish/open-core:main
```

### If it should go to the app deployment branch

The change belongs in the hosted product runtime.

Typical examples:

- UI updates
- app templates
- FastAPI route changes
- runtime assets
- deployment-only config

Promotion flow:

```bash
git checkout deploy/app
git merge main
```

Then trim or review anything that should not stay in the deployment branch before pushing.

Finally:

```bash
git push origin deploy/app
```

## Release Checklist

Use this checklist whenever you want to publish or deploy.

### Before promoting from `main`

```bash
git checkout main
git status
python3 -m pytest -q
```

### Before pushing open-core

Check that the branch does not contain:

- `app/`
- local output artifacts
- caches
- scratch files

Then push:

```bash
git checkout publish/open-core
git status
git push origin publish/open-core
git push public publish/open-core:main
```

### Before pushing app deployment

Check that the branch contains the app runtime and core engine, but not dev-only extras.

Then push:

```bash
git checkout deploy/app
git status
git push origin deploy/app
```

## Mental Model

Use this rule:

- `main` is where the product evolves
- `publish/open-core` is what developers get publicly
- `deploy/app` is what the hosted product runs

If you keep that boundary clean, the repo stays understandable even as RenderScript grows.
