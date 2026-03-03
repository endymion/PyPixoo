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

# Storybook Clock animation (t 0..1), pre-rendered then pushed in timed loop (no loading overlay)
# Requires: Storybook running (cd storybook-app && npm run storybook)
python demos/storybook_clock.py
python demos/storybook_clock.py --fps 10 --loop-seconds 2
python demos/storybook_clock.py --delivery upload --upload-mode command_list

# Smooth real-time clock (default push mode avoids repeated "Loading..." indicator)
# Default demo mode cycles clockface marker style every minute.
# Automatically reconnects after device/network interruptions (default retry every 3s).
# Defaults: magenta markers, lighter top marker, mauve hour/minute hands.
# Optional: --fps, --render-lead-ms, --dial-color, --hour-hand-color, --minute-hand-color, --fade
python demos/clock_realtime.py
python demos/clock_realtime.py --fps 3 --render-lead-ms 1500 --dial-color "#111"
python demos/clock_realtime.py --clockface ticks_all_thick_quarters --no-second-hand
python demos/clock_realtime.py --no-second-hand --marker-color "#ff00ff"
python demos/clock_realtime.py --fade 20

# Optional: native upload windows mode (may show loading indicator while uploading)
python demos/clock_realtime.py --delivery upload --fps 6 --window-seconds 3

# Font showcase: cycle Tiny5 text screens (alphabet, numbers, alert, warning, success, info) — 5s per screen
# Uses local 192x192 fixture + 3x downsample (no Storybook required)
python demos/font_showcase.py
python demos/font_showcase.py --duration 3

# Upload a short sequence (client pushes frames)
python demos/demo_upload_sequence.py

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
