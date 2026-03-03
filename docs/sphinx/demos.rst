Demos
=====

Real-device demos live in `demos/` and are intended for manual testing.
All demos require the device IP.

- `demo_upload_sequence.py`: Upload frames via `Draw/SendHttpGif`.
- `demo_sequence_switching.py`: Compare stitched single-upload switching vs
  live upload switching for smoothness.
- `demo_three_hand_clock.py`: Three-hand analog clock rendered in Python;
  default `push` delivery avoids loading overlays, optional stitched mode for diagnostics.
  Hand/dial colors accept hex/rgb/name and Radix tokens (`gray11`, `dark.gray11`, `grayDark11`).
- `demo_play_url_gif.py`: Device fetches a URL GIF via `PlayTFGif`.
- `demo_text_overlay.py`: Overlays text on top of an uploaded sequence.
- `demo_display_list.py`: Sends `Draw/SendHttpItemList`.
- `demo_tools.py`: Countdown, stopwatch, scoreboard, noise, buzzer.
- `demo_device_settings.py`: Brightness/screen/rotation/mirror/24h.
- `demo_weather.py`: Set location and read device weather.
- `demo_web_fonts.py`: WebFrameSource + Google Fonts path.
- `clock_realtime.py` / `storybook_clock.py`: shared clock core with
  `native_clock` (default) and `web_clock_experimental` modes.
