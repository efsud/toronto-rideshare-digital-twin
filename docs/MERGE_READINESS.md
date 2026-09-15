# Merge Readiness — feature/traffic-layer → main

## Ready to merge when

1. `pytest` and `ruff check src tests examples scripts dashboard` pass locally and in CI
2. Demo artifacts exist at `artifacts/task_demo/demo_summary.png`
3. You have reviewed [`docs/PR_REVIEW.md`](PR_REVIEW.md)
4. Word big-picture doc is current: `docs/Toronto_Rideshare_Digital_Twin_Big_Picture.docx`

Local verification (2026-09-15, project `.venv`): 61 pytest tests, Ruff, AppTest,
time-dependent Toronto route demo, baseline experiment, and 3-seed repeated P0–P7
comparison all passed. CI on the PR remains the merge gate.

## Merge command (when you approve)

```bash
git checkout main
git pull origin main
git merge feature/traffic-layer
git push origin main
```

Or merge Draft PR #1 on GitHub.

## Optional post-merge

```bash
git tag v0.4.0
git push origin v0.4.0
```

## Not blocking merge

- SUMO integration
- RL benchmark
- Full recruiter portfolio GIF
- Real Toronto traffic download (synthetic fallback works)
