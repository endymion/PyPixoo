# Scene Acceptance Matrix (Real Device)

Use this matrix when validating v3 layered runtime behavior on hardware.
Do not close acceptance tasks without explicit visual confirmation.

| Capability | Command | Expected Visual | Confirmed |
|---|---|---|---|
| Raster single-frame push | `pixoo raster push --color dark.amber10` | Solid amber-ish frame appears immediately | ☐ |
| Raster paced stream | `pixoo raster stream --fps 2 --duration 8` | Alternating frames at steady cadence | ☐ |
| Scene run (clock) | `pixoo scene run --scene clock --duration 15` | Clock scene updates continuously | ☐ |
| Scene run (info) | `pixoo scene run --scene info --duration 15` | Info scene with moving band | ☐ |
| `cross_fade` | `pixoo scene enqueue --transition cross_fade` | A fades out while B fades in | ☐ |
| `push_left` | `pixoo scene enqueue --transition push_left` | A exits left while B enters from right | ☐ |
| `push_right` | `pixoo scene enqueue --transition push_right` | A exits right while B enters from left | ☐ |
| `push_up` | `pixoo scene enqueue --transition push_up` | A exits up while B enters from bottom | ☐ |
| `push_down` | `pixoo scene enqueue --transition push_down` | A exits down while B enters from top | ☐ |
| `slide_over_left` | `pixoo scene enqueue --transition slide_over_left` | B slides in from right over static A | ☐ |
| `slide_over_right` | `pixoo scene enqueue --transition slide_over_right` | B slides in from left over static A | ☐ |
| `slide_over_up` | `pixoo scene enqueue --transition slide_over_up` | B slides in from bottom over static A | ☐ |
| `slide_over_down` | `pixoo scene enqueue --transition slide_over_down` | B slides in from top over static A | ☐ |
| `wipe_left` | `pixoo scene enqueue --transition wipe_left` | B reveals from right edge toward left | ☐ |
| `wipe_right` | `pixoo scene enqueue --transition wipe_right` | B reveals from left edge toward right | ☐ |
| `wipe_up` | `pixoo scene enqueue --transition wipe_up` | B reveals from bottom toward top | ☐ |
| `wipe_down` | `pixoo scene enqueue --transition wipe_down` | B reveals from top toward bottom | ☐ |

