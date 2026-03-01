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

# Storybook Clock animation (t 0..1)
# Requires: Storybook running (cd storybook-app && npm run storybook)
python demos/storybook_clock.py

# Real-time clock: current time, updates every second; pre-renders before each tick (--preload-ms, default 800)
# Optional: --dial-color, --hands-color (defaults black/white), --interval 1
python demos/clock_realtime.py
python demos/clock_realtime.py --dial-color "#111" --hands-color cyan
```
