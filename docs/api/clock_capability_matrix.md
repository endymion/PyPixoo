# Clock Capability Matrix

Source of truth for clock-related behavior in PyPixoo during discovery-first redesign.

Legend:
- `stable`: repeated real-device runs match expected behavior
- `partial`: behavior works but has caveats or pending confirmation
- `unstable`: behavior is inconsistent or currently unsuitable for non-experimental use

| Capability | Command/API | Expected Behavior | Observed on Real Device | Stability | Notes |
|---|---|---|---|---|---|
| Select device clock face | `Channel/SetClockSelectId` via `Pixoo.set_clock_select_id()` | Device switches to selected built-in clock face | Command path implemented; visual verification pending in current pass | partial | Native mode only |
| Read device clock info | `Channel/GetClockInfo` via `Pixoo.get_clock_info()` | Returns active clock configuration/details | Command path implemented and used in native mode startup logs | partial | Structure varies by firmware |
| Set device UTC | `Device/SetUTC` via `Pixoo.set_utc_time()` | Device time syncs to host epoch | Command path implemented; long-run drift validation pending | partial | Optional periodic sync in native mode |
| Set 24-hour mode | `Device/SetTime24Flag` via `Pixoo.set_time_24_flag()` | Device toggles 12h/24h display mode | Command path implemented; visual confirmation pending in acceptance pass | partial | Native mode option `--twenty-four-hour` |
| Native clock refresh behavior | Device-side clock rendering | Clock updates continuously without browser upload stalls | Native path selected as default mode for reliability | partial | Requires dedicated acceptance confirmation |
| Three-hand uploaded clock (push delivery) | `Draw/SendHttpGif` via `push_buffer` in `demo_three_hand_clock.py` | Smooth analog hour/minute/second hands without periodic loading overlays | Implemented; pending full 30s visual confirmation | partial | Default delivery is `push`; adaptive FPS based on upload latency |
| Three-hand uploaded clock (stitched delivery) | Segment `Draw/SendHttpGif` uploads in `demo_three_hand_clock.py --delivery stitched` | Phase-locked segment playback | Works but triggers visible loading overlay at segment boundaries | partial | Keep for diagnostics, not default |
| Web clock second-hand smoothness | Storybook render + `push_buffer`/`upload_sequence` | Continuous smooth motion with accurate real time | Historically showed burst/stall patterns under render pressure | unstable | Explicitly marked `web_clock_experimental` |
| 12 o'clock marker brightness | Storybook args `topMarkerColor` vs `markerColor` | Top marker appears brighter than other markers | Defaults updated to brighter top marker and user-confirmed | stable | Bug `kanbus-04c906` closed |

## Mode Truth Rules

- `native_clock`: uses only device commands and claims only native capabilities.
- `web_clock_experimental`: uses browser rendering + uploads, explicitly non-native and experimental.
- No silent fallback between modes is allowed.
