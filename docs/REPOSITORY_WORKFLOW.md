# Repository Workflow

This document defines how the RenderScript repository should be organized as the project grows.

The goal is simple:

- keep one real development source of truth
- keep public open-core publishing clean
- keep deployment packaging separate

## Core Rule

`main` is the source of truth.

All new features, fixes, refactors, and tests should start from `main`.

Do not build new product work directly on the trimmed distribution branches.

## Branch Roles

### `main`

This is the full working repository.

It should contain:

- core engine
- hosted app UI
- tests
- examples
- docs
- build files

All product development happens here first.

### `publish/open-core`

This is the public GitHub branch for the open-core engine.

It is derived from `main`, then trimmed for public release.

It should contain:

- core engine
- CLI
- tests for the engine
- examples
- docs
- packaging/build files

It should not contain:

- hosted UI
- local output artifacts
- scratch files

### `deploy/app`

This is the deployment-focused branch for the hosted app.

It is derived from `main`, then trimmed for deployment.

It should contain:

- app runtime
- core engine
- templates
- runtime assets
- build/config files needed for the container

It should not contain:

- tests
- examples
- docs
- benchmark files
- local output artifacts

## Day-To-Day Development

Use short-lived branches from `main`.

Examples:

- `feature/grok-adapter`
- `feature/package-map-refresh`
- `fix/pdf-layout`
- `fix/ui-upload-validation`

Merge those back into `main`.

## What Not To Do

Do not:

- build features directly on `publish/open-core`
- build features directly on `deploy/app`
- treat trimmed branches as the main development branch

Those branches are distribution branches, not product-development branches.

## Release Flow

### Open-Core Release Flow

1. Start from `main`
2. Update or recreate `publish/open-core`
3. Trim the repo to the public open-core set
4. Run tests
5. Push `publish/open-core` to GitHub

### App Deployment Flow

1. Start from `main`
2. Update or recreate `deploy/app`
3. Trim the repo to the deployment/runtime set
4. Build the container from that branch
5. Deploy

## Why This Structure Exists

RenderScript now has three different needs:

- full product development
- public open-core publishing
- deployment packaging

If those are all developed separately, the project will drift and become harder to reason about.

Using `main` as the source of truth avoids that.

## Practical Summary

Use this rule:

- build on `main`
- publish from `publish/open-core`
- deploy from `deploy/app`

## Future Improvement

If this becomes repetitive, automate branch preparation with scripts.

Examples:

- `scripts/prepare_open_core.sh`
- `scripts/prepare_deploy_branch.sh`

That would reduce manual pruning and make releases more repeatable.
