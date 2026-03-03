# pixooclock Adaptive Palette Plan

## Goal

Make `demos/pixooclock.py` default to adaptive color-band behavior:

- Daytime: `sand`
- Nighttime: `bronze`

## Behavior Contract

1. `--band auto` is the default mode.
2. If `--band <name>` is explicitly provided, adaptive logic is disabled.
3. Adaptive location resolution priority:
   1. CLI `--latitude/--longitude`
   2. env `PIXOO_LATITUDE` / `PIXOO_LONGITUDE`
   3. Cached IP geolocation (`~/.pypixoo/geolocation.json`, TTL 24h)
   4. Live IP geolocation (`https://ipapi.co/json/`)
   5. Timezone seasonal fallback (no location available)
4. Real location path uses true sunrise/sunset from `astral`.
5. Timezone fallback uses a seasonal daylight model (not fixed hours).
6. Adaptive mode reevaluates on a cadence (default 60s) and can switch bands at runtime.
7. `--demo` mode keeps existing cycling behavior and bypasses adaptive updates.

## Timezone Seasonal Fallback

When location is unavailable:

1. Determine hemisphere:
   1. Use `PIXOO_HEMISPHERE` if set (`north`/`south`)
   2. Else infer from timezone key heuristics
   3. Default to `north` when unknown
2. Compute daylight estimate:
   - `daylight_hours = 12.0 + 2.5 * cos(2pi * (doy - solstice_day) / 365.25)`
   - `solstice_day = 172` (north), `355` (south)
3. Apply local DST shift (+1 hour if active).
4. Estimate sunrise/sunset around noon:
   - `sunrise_est = 12 - daylight_hours / 2 + dst_shift`
   - `sunset_est = 12 + daylight_hours / 2 + dst_shift`
5. Day iff `sunrise_est <= local_now < sunset_est`.

## Logging Contract

At startup:

- log adaptive mode source (`real_sun`, `tz_seasonal`, or `explicit`)
- log selected band and data source (`cli`, `env`, `cache`, `ipapi`, fallback)

At runtime:

- on band transition, log `Adaptive band change: <old> -> <new>`

## Tests

1. `tests/test_clock_palette.py`
   - location priority resolution
   - cache hit/miss/expiry
   - ipapi success/failure parsing
   - real sunrise/sunset day-night selection
   - seasonal fallback north/south inversion
   - DST shift effect
   - boundary checks at sunrise/sunset
2. `tests/test_demo_three_hand_clock.py`
   - parser defaults for `auto`, day/night bands
   - explicit `--band` bypass
   - runtime transition triggers style refresh
   - `--demo` bypasses adaptive logic

## Acceptance Criteria

1. Default `pixooclock` run uses adaptive logic.
2. Explicit `--band` remains deterministic and fixed.
3. No-location mode remains non-fatal and uses seasonal timezone fallback.
4. Adaptive switching occurs without restart when boundary is crossed.
