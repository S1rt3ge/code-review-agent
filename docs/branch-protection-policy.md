# Branch Protection Policy

This document defines the minimum branch protection baseline for `main`.

## Required settings for `main`

- **Require a pull request before merging**
  - Require at least **1 approval**.
  - Dismiss stale approvals when new commits are pushed.
  - Require review from Code Owners.
- **Require status checks to pass before merging**
  - Require branches to be up to date before merging.
  - Required checks:
    - `CI / Security Gates`
    - `CI / SBOM`
    - `CI / Backend Tests (Python 3.12)`
    - `CI / Frontend Build`
- **Require conversation resolution before merging**.
- **Restrict who can push to matching branches**
  - No direct pushes to `main`.
- **Do not allow force pushes**.
- **Do not allow deletions**.

## Recommended repository-level settings

- Enable **Dependabot security updates**.
- Enable **secret scanning** and **push protection** (GitHub Advanced Security, if available).
- Keep squash merges enabled for clean history.

## Applying via GitHub UI

1. Repository `Settings` -> `Branches`.
2. Edit (or create) protection rule for `main`.
3. Configure settings from this policy.
4. Save and verify required checks list matches current workflow names.

## Ongoing maintenance

- If CI job names change, update this document and branch protection required checks.
- Review policy quarterly or after major pipeline changes.
