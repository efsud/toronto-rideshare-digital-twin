# Merge Readiness — feature/traffic-layer → main

## Ready to merge when

1. `pytest` passes locally and in CI
2. Demo artifacts exist at `artifacts/task_demo/demo_summary.png`
3. You have reviewed [`docs/PR_REVIEW.md`](PR_REVIEW.md)
4. Word big-picture doc is current: `docs/Toronto_Rideshare_Digital_Twin_Big_Picture.docx`

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
git tag v0.3
git push origin v0.3
```

## Not blocking merge

- SUMO integration
- RL benchmark
- Full recruiter portfolio GIF
- Real Toronto traffic download (synthetic fallback works)
