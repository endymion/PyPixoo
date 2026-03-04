# PyPixoo Demos

Demos require a Pixoo 64 on the network. By default they read `PIXOO_DEVICE_IP` (or legacy `PIXOO_IP`)
from the environment or a local `.env` file, falling back to `192.168.0.37`. You can also pass `--ip`
when the script supports it.

**Device lock:** Only one process can use a given device IP at a time. The library acquires an exclusive lock (under `~/.pypixoo/` or `$PYPIXOO_LOCK_DIR`) so running a second demo against the same IP fails with `DeviceInUseError` until the first exits or calls `pixoo.close()`.

Run from the project root:

```bash
# Transparent blend: black band over gradient background
python demos/black_band_transparent.py

# Opaque: pre-composited gradient + black band frames
python demos/black_band_opaque.py

# Chained: sequence 1 (band L→R) then sequence 2 (band R→L), loop forever (Ctrl+C to stop)
python demos/black_band_chained.py

# Browser mixed: static frames + web-rendered frames (local HTML), on_first_frame / on_all_frames callbacks
# Requires: pip install -e ".[browser]"
python demos/browser_mixed.py

# Scene transition showcase (v3 high-level runtime)
python demos/scene_transitions.py
python demos/scene_transitions.py --all-transitions --run-seconds 45
python demos/scene_transitions.py --info-layout-json '{"rows":[{"kind":"text","height":12,"align":"center","content":"STATUS"},{"kind":"table","height":10,"column_align":["left","right"],"block_align":"center","cells":[{"value":"TEMP"},{"value":"72F"}]}]}'

# Alerting clock REPL (clock by default; alert/warn/info commands enqueue transitions)
python demos/alerting_clock.py
# Optional tuning:
#   --fps 5 --transition-ms 1200
# Then type commands in the REPL:
#   alert "SOMETHING\nIS\nWRONG"
#   alert --seconds 5 "lorem ipsum"
#   alert -s5 "lorem ipsum"
#   alert --color red-10 --background-color red-5 "lorem ipsum"
#   warn "disk nearing full"
#   info "backup completed"
# REPL history is persisted at ~/.pypixoo/alerting_clock_history (up/down arrows)

# Kanbus Clock REPL + recursive project/events watcher
# - Recursively discovers all */project/events folders under --root (default: .)
# - Prints startup folder summary with latest occurred_at
# - Watches for new *.json files and auto-queues INFO notices
# - Keeps REPL active for manual alert/warn/info commands
python demos/kanbus_clock.py
python demos/kanbus_clock.py --root . --poll-seconds 1 --rescan-seconds 10 --auto-info-seconds 5
# REPL history is persisted at ~/.pypixoo/kanbus_clock_history (up/down arrows)

# Font showcase: cycle Tiny5 text screens (alphabet, numbers, alert, warning, success, info) — 5s per screen
# Uses local 192x192 fixture + 3x downsample (no Storybook required)
python demos/font_showcase.py
python demos/font_showcase.py --duration 3

# Upload a short sequence (client pushes frames)
python demos/demo_upload_sequence.py

# Sequence switching experiment:
# stitched = smoothest switch (single upload), live = repeated uploads (experimental)
# defaults are tuned for device compatibility (frame_by_frame + bounded frame count)
python demos/demo_sequence_switching.py --mode stitched
python demos/demo_sequence_switching.py --mode live

# Unified smooth clock demo (scene-first runtime + raster transport)
# `pixooclock` is the canonical clock script; demo_three_hand_clock.py is a compatibility wrapper.
# Default preset is adaptive: face=dot12, band=auto, day=sand, night=bronze, hand AA on, dot AA on, second hand off.
python demos/pixooclock.py
python demos/pixooclock.py --face default --second-hand --no-anti-aliasing
python demos/pixooclock.py --band tomato
python demos/pixooclock.py --face ticks_all_thick_quarters --anti-aliasing
python demos/pixooclock.py --face dot12 --band sand --dot-anti-aliasing
python demos/pixooclock.py --band auto --day-band sand --night-band bronze
python demos/pixooclock.py --latitude 40.7484 --longitude -73.9857
python demos/pixooclock.py --once --fps 4 --segment-seconds 10
python demos/pixooclock.py --delivery stitched --fps 4 --segment-seconds 10

# Visual comparison mode: cycle every 5s through all combinations:
# color band x face x second-hand(on/off) x anti-aliasing(on/off)
python demos/pixooclock.py --demo --demo-interval-seconds 5

# Optional: reduce demo sweep to a subset of color bands
python demos/pixooclock.py --demo --demo-bands tomato,purple,blue

# Troubleshooting:
# - If you only see a static/default channel, run with --once and lower fps first.
# - If you see periodic "Loading..." flashes, use/keep --delivery push (default).
# - If hands appear truncated or updates stall, lower --fps or --segment-seconds.
# - Color args support hex/rgb/name and Radix tokens (gray11, dark.gray11, grayDark11).
# - In `--band auto`, location priority is CLI lat/lon -> PIXOO_LATITUDE/LONGITUDE -> cached/live ipapi -> timezone seasonal fallback.
# - `--band tomato` remaps the default intensity slots: top=10, markers=7, hour=9, minute=10, second/center=5.
# - `--dot-anti-aliasing` smooths marker/center dots independently from hand anti-aliasing.

# Device fetches and plays a GIF from a URL
python demos/demo_play_url_gif.py --url https://example.com/anim.gif

# Upload then overlay text (device renders text on top)
python demos/demo_text_overlay.py --text HELLO

# Send a display list item
python demos/demo_display_list.py

# Exercise built-in tools (timer, stopwatch, scoreboard, noise, buzzer)
python demos/demo_tools.py

# Exercise device settings (brightness, rotation, mirror, 24h)
python demos/demo_device_settings.py

# Set weather location and read device weather info
python demos/demo_weather.py --longitude -73.9857 --latitude 40.7484

# Render web fonts in Playwright then upload to device
# Requires: pip install -e ".[browser]"
python demos/demo_web_fonts.py
```
