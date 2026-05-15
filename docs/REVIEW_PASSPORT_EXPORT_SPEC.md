# Feature Specification: Review Passport Export And PR Comment

## Description

Review Passport should become a shareable review artifact, not only an internal dashboard panel. A user can export the current passport as Markdown for local/demo workflows and, for GitHub-backed reviews, post or update the passport as a pull request comment through the existing GitHub App comment path.

This matters because the product promise is evidence, traceability, and merge readiness. The evidence should travel with the PR where review decisions happen.

## User Stories

- As a developer, I want to copy a Review Passport Markdown report, so that I can share the verdict without screenshots.
- As a PR owner, I want to post the passport to GitHub, so that reviewers see acceptance-criteria coverage and anti-slop risks directly in the PR.
- As a maintainer, I want repeated posting to update the previous passport comment, so that a PR does not accumulate duplicate bot comments.
- As a local-demo user, I want Markdown export to work without GitHub credentials, so that the first demo remains zero-cost and offline-friendly.

## Data Model

`review_passports`
- `github_comment_id`: bigint nullable, GitHub issue comment id for the passport comment.
- `github_comment_url`: text nullable, browser URL for the passport comment.
- `github_comment_posted_at`: timestamptz nullable, last successful post/update time.

Ownership remains unchanged:
- `review_passports.user_id` owns the passport.
- `review_passports.review_id` points to the owned review.
- RLS continues to scope rows to `app.current_user_id`.

## API

```text
GET /api/reviews/{review_id}/passport/markdown
Auth: Bearer user JWT
Success: 200 { "body": "markdown" }
Errors: 401 unauthenticated, 403 wrong owner, 404 review or passport missing
```

```text
POST /api/reviews/{review_id}/passport/post-comment
Auth: Bearer user JWT
Body: {}
Success: 200 { "comment_id": 123, "url": "https://github.com/...", "posted_at": "..." }
Errors:
- 400 review is not GitHub-backed, GitHub App missing, or installation id missing
- 401 unauthenticated
- 403 wrong owner
- 404 review, repository, or passport missing
- 502 GitHub API error
```

## Screens

Review detail / Review Passport panel:

- With a passport: show `Copy Markdown` and, when the review has GitHub PR metadata, `Post to PR`.
- Local/demo reviews: keep copy/export available and show GitHub posting errors as inline messages instead of hiding the feature.
- Success: after copying, show a short copied confirmation. After posting, show the returned comment URL.
- Error: show the API error message in the existing passport panel error area.

## Business Logic

- Markdown export is deterministic and does not call external providers.
- Markdown includes verdict, confidence, criteria coverage, anti-slop signals, missing evidence, QA steps, and generated timestamp.
- Markdown truncates long lists to keep GitHub comments readable.
- Posting requires an owned review, existing passport, repository row, GitHub installation id, and configured GitHub App client.
- If `ReviewPassport.github_comment_id` exists, update that comment. Otherwise create a new comment and persist the id/url/timestamp.
- Posting a passport does not alter the existing findings PR comment id on `reviews.pr_comment_id`.

## Edge Cases

- Passport missing: return 404 and ask the user to generate a passport first.
- Local playground review: Markdown export works; GitHub post returns 400 with a clear message.
- GitHub API unavailable: return 502 without deleting or mutating passport data.
- Repeated post: update existing comment and refresh `github_comment_posted_at`.
- Huge passport data: render only first 10 criteria, first 8 signals, first 8 missing evidence entries, and first 8 QA steps.

## Priority / Dependencies

Priority: next product differentiation slice after the Review Passport core.

Dependencies:
- Existing Review Passport persistence.
- Existing GitHub API client `post_pr_comment` / `update_pr_comment`.
- Existing review ownership/auth checks.

Verification:
- Unit tests for Markdown formatting.
- API tests for export, missing passport, local GitHub-post guard, and GitHub post/update with mocked client.
- Frontend tests for copy Markdown and post-to-PR actions.
