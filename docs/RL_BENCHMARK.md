# RL Benchmark (Optional — Future)

Reinforcement learning is **deferred** until deterministic baselines (P0–P7) and OR-Tools LP are stable.

## Proposed environment outline

```text
State:  zone-level demand, idle drivers, current tau_e(t) summaries, policy vector
Action: rider adjustments a_z,t and driver bonuses b_z,t (discretized or bounded continuous)
Reward: completed trips - wait penalty - subsidy cost
Episode: one simulation day (07:00–22:00)
```

## Minimal gym-style interface (planned)

```python
class MarketplaceEnv:
    def reset(self, seed: int) -> np.ndarray: ...
    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, dict]: ...
```

## Benchmark order

1. Rule policies P0–P3 (done)
2. OR-Tools LP P4 (done)
3. Repositioning P5–P7 (done)
4. RL agent vs P4/P7 on fixed seeds

## Dependencies (future)

- `gymnasium` or custom env wrapper around `SimulationEngine`
- Stable experiment logging under `artifacts/task_rl/`
