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

# Clock demos (shared core)
# Default mode is native_clock (device-side clock features only; discovery-first safe default)
# Native default preserves the current device clock face unless you pass --clock-id.
python demos/clock_realtime.py
python demos/storybook_clock.py

# Native clock mode options (device commands only)
python demos/clock_realtime.py --mode native_clock --clock-id 846 --sync-utc
python demos/clock_realtime.py --mode native_clock --twenty-four-hour --poll-seconds 5

# Experimental web clock mode (browser-rendered + upload; non-native)
# Requires: Storybook running (cd storybook-app && npm run storybook)
python demos/clock_realtime.py --mode web_clock_experimental --fps 3 --render-lead-ms 1500
python demos/clock_realtime.py --mode web_clock_experimental --clockface ticks_all_thick_quarters --no-second-hand
python demos/clock_realtime.py --mode web_clock_experimental --no-second-hand --marker-color "#ff00ff"
python demos/clock_realtime.py --mode web_clock_experimental --fade 20
python demos/clock_realtime.py --mode web_clock_experimental --delivery upload --fps 6 --window-seconds 3

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

# Three-hand analog clock via stitched native uploads (phase-locked segments)
# Default delivery is push to avoid device "Loading..." overlays between segments
python demos/demo_three_hand_clock.py
python demos/demo_three_hand_clock.py --once --fps 4 --segment-seconds 10
python demos/demo_three_hand_clock.py --fps 6 --segment-seconds 12
python demos/demo_three_hand_clock.py --delivery stitched --fps 4 --segment-seconds 10
python demos/demo_three_hand_clock.py --hour-hand-color gray11 --minute-hand-color dark.gray11 --second-hand-color grayDark11

# Troubleshooting:
# - If you only see a static/default channel, run with --once and lower fps first.
# - If you see periodic "Loading..." flashes, use/keep --delivery push (default).
# - If hands appear truncated or updates stall, lower --fps or --segment-seconds.
# - Color args support hex/rgb/name and Radix tokens (gray11, dark.gray11, grayDark11).

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
