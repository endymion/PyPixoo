Demos
=====

Real-device demos live in `demos/` and are intended for manual testing.
All demos require the device IP.

- `demo_upload_sequence.py`: Upload frames via `Draw/SendHttpGif`.
- `scene_transitions.py`: Scene runtime transition showcase (`cross_fade`,
  `push_*`, `slide_over_*`, `wipe_*`) with real-device rendering.
  It now uses `InfoScene(layout=InfoLayout(...))` with text/table rows.
- `demo_sequence_switching.py`: Compare stitched single-upload switching vs
  live upload switching for smoothness.
- `pixooclock.py` / `demo_three_hand_clock.py`: Scene-first smooth analog
  clock rendering over the raster layer.
- `demo_play_url_gif.py`: Device fetches a URL GIF via `PlayTFGif`.
- `demo_text_overlay.py`: Overlays text on top of an uploaded sequence.
- `demo_display_list.py`: Sends `Draw/SendHttpItemList`.
- `demo_tools.py`: Countdown, stopwatch, scoreboard, noise, buzzer.
- `demo_device_settings.py`: Brightness/screen/rotation/mirror/24h.
- `demo_weather.py`: Set location and read device weather.
- `demo_web_fonts.py`: WebFrameSource + Google Fonts path.

Header-only InfoScene example::

    pixoo scene run --scene info \
      --info-title "STATUS" \
      --info-font tiny5 \
      --info-header-height 12 \
      --info-header-border \
      --info-header-border-thickness 1 \
      --info-header-border-color dark.gray8

Table alignment + multi-row layout via JSON::

    pixoo scene run --scene info --duration 30 \
      --info-layout-json '{"rows":[{"kind":"text","height":12,"align":"center","content":"STATUS"},{"kind":"table","height":10,"column_align":["left","right"],"block_align":"center","cells":[{"value":"CPU"},{"value":"42%"}]},{"kind":"table","height":10,"column_align":["left","right"],"block_align":"center","cells":[{"value":"RAM"},{"value":"61%"}]}]}'
