Mental Model
============

There are three distinct rendering paths. Understanding them prevents
confusion about what runs on the device vs what runs on your machine.

1) Device fetches a GIF (remote URL)
-----------------------------------

`Device/PlayTFGif` with `FileType=2` tells the Pixoo to download and play
a GIF directly. The device does the network fetch and decoding. PyPixoo only
sends a small JSON command with the URL.

2) Client uploads frames
------------------------

`Draw/SendHttpGif` uploads raw frame data (RGB) from your Python process
to the device. The device does not fetch anything from the internet. You
are pushing frames over HTTP.

3) Device overlays text on top of the last upload
-------------------------------------------------

`Draw/SendHttpText` renders a text overlay on top of the last uploaded
sequence. This is device-side rendering. It is not a browser or React
feature. Overlays only make sense after you have uploaded a sequence.

Fonts: built-in vs web
----------------------

- Built-in animation fonts (0-7) are used by `Draw/SendHttpText`.
- Dial/display list fonts come from Divoom services and are used by
  `Draw/SendHttpItemList`.
- Web fonts (Google Fonts) are only used when you render via
  `WebFrameSource` in a headless browser and then upload frames.

Weather and device tools
------------------------

The Pixoo has built-in modes like weather, countdown, stopwatch, and
scoreboard. PyPixoo exposes these as command wrappers that call device
endpoints. For weather you set location with `Sys/LogAndLat` and read
current device weather via `Device/GetWeatherInfo`.
