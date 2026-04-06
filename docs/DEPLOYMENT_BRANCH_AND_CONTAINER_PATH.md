# Deployment Branch And Container Path

This guide defines how to think about `deploy/app`.

It is not a Dockerfile or infrastructure spec.
It is the operating guide for keeping the deployment branch clean and ready for container work.

## What `deploy/app` Is For

`deploy/app` is the deployment-focused branch for the hosted RenderScript app.

Its job is to contain:

- the FastAPI app
- the core RenderScript package
- templates
- runtime assets
- Python packaging/build files needed to install and run the app

It should not contain:

- tests
- examples
- internal branch-management docs
- benchmark material
- generated `out/` artifacts
- cache files

## Branch Role

Use this rule:

- develop on `main`
- promote to `deploy/app`
- deploy containers from `deploy/app`

Do not build new product work directly on `deploy/app`.

## What The Branch Should Contain

At a high level, `deploy/app` should keep:

- `app/`
- `renderscript/`
- `pyproject.toml`
- `build_backend.py`
- `renderscript.schema.v0.1.json`

It may also keep small runtime-facing docs if they are useful during deployment, but the branch should stay operational, not encyclopedic.

## Promotion Flow

When `main` has app/runtime changes you want to deploy:

```bash
git checkout deploy/app
git merge main
```

Then review the branch and remove anything that does not belong in the runtime image.

Typical things to remove if they appear:

- `tests/`
- `examples/`
- `docs/`
- `bench/`
- `out/`
- tracked cache files

Then push:

```bash
git push origin deploy/app
```

## Container Mental Model

The container should be built from the deployment branch, not from `main`.

That keeps the image focused on:

- runtime code
- runtime assets
- install metadata

It avoids shipping:

- contributor-only material
- public-repo-only material
- local artifacts

## Minimum Runtime Expectations

A container build should be able to:

1. install the package
2. import `app.main`
3. import `renderscript.renderpackage`
4. run the app server

That means the deployment branch must keep:

- Python package metadata correct
- app templates present
- branding/runtime assets present
- prompt/package generation code intact

## Practical Pre-Deploy Check

Before building or deploying from `deploy/app`, run:

```bash
git checkout deploy/app
git status
python3 -c "import app.main; import renderscript.renderpackage; print('imports ok')"
```

If imports work and the branch is clean, the branch is in a decent state for containerization work.

## Future Improvement

When you are ready, the next step is to add deployment-specific files such as:

- Dockerfile
- process command
- environment variable documentation
- platform-specific deploy config

Those should live on `deploy/app` once you are ready to formalize the container path.
