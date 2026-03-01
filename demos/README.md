# PyPixoo Demos

Demos require a Pixoo 64 on the network. Edit the IP in each script if needed (default: 192.168.0.37).

Run from the project root:

```bash
# Transparent blend: black band over gradient background
PIXOO_REAL_DEVICE=1 python demos/black_band_transparent.py

# Opaque: pre-composited gradient + black band frames
PIXOO_REAL_DEVICE=1 python demos/black_band_opaque.py

# Chained: sequence 1 (band L→R) then sequence 2 (band R→L), loop forever (Ctrl+C to stop)
PIXOO_REAL_DEVICE=1 python demos/black_band_chained.py
```
