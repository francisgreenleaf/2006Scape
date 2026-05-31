# Walk Distance Estimate

Small read-only estimator for a selected profile's recorded walking distance.

Run from the repo root:

```sh
python3 agent-navigation/analysis/walk-distance-estimate/estimate_walked_miles.py \
  --profile PROFILE \
  --write-json agent-navigation/analysis/walk-distance-estimate/latest-result.json
```

Assumptions:

- One tile-step is one meter.
- Diagonal movement counts as one tile-step, matching the "squares moved through" estimate.
- Running ticks can move two tile-steps, so the script uses `max(abs(dx), abs(dy))`.
- Teleports, map-region jumps, and plane changes are skipped.
- Server passive movement traces are preferred. Agent batch traces before passive tracing started are added, while overlapping agent traces are reported separately but not added to the combined total.
- Legacy route-recorder samples are read from the selected profile's trace file and treated as a lower-bound add-on only before detailed tick traces begin.
