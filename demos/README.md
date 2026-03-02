# PyPixoo Demos

Demos require a Pixoo 64 on the network. Edit the IP in each script if needed (default: 192.168.0.37). **Demos use the real device by default** (no environment variable needed).

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
# Optional: --fps, --render-lead-ms, --dial-color, --hands-color
python demos/clock_realtime.py
python demos/clock_realtime.py --fps 3 --render-lead-ms 1500 --dial-color "#111" --hands-color cyan
python demos/clock_realtime.py --clockface ticks_all_thick_quarters --no-second-hand
python demos/clock_realtime.py --no-second-hand --marker-color "#ff00ff"

# Optional: native upload windows mode (may show loading indicator while uploading)
python demos/clock_realtime.py --delivery upload --fps 6 --window-seconds 3

# Font showcase: cycle Tiny5 text screens (alphabet, numbers, alert, warning, success, info) — 5s per screen
# Uses local 192x192 fixture + 3x downsample (no Storybook required)
python demos/font_showcase.py
python demos/font_showcase.py --duration 3
```
