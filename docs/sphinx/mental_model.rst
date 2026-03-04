Mental Model
============

PyPixoo v3 is intentionally layered so both low-level and high-level usage
are first-class.

L0: Device transport (`Pixoo`)
------------------------------

`Pixoo` is the raw command and frame transport layer:

- direct commands (`command`, `set_*`, `get_*`)
- frame upload (`Draw/SendHttpGif`, `Draw/CommandList`)
- single-frame push (`push_buffer`)
- device-side features like weather/tools/clock IDs

If you want total control and no framework opinions, stay at L0.

L1: Raster streaming (`pypixoo.raster`)
---------------------------------------

`RasterClient` / `AsyncRasterClient` sit on top of a `FrameSink` and provide
simple, paced frame streaming with reconnect-aware sinks (`PixooFrameSink`).

This layer still has no scene concepts. It is for users who want to push
buffers directly with minimal ceremony.

L2: Scene runtime (`pypixoo.scene`)
-----------------------------------

`ScenePlayer` adds queueing, transitions, and compositing on top of L1.
Scenes expose `LayerNode` lists. The runtime renders host-side and pushes the
composited frame through the raster layer.

`pypixoo.transitions` and `pypixoo.compositor` define transition planning and
pixel blending behavior.

`ScenePlayer` intentionally does not include clock/info assumptions. High-level
composition choices (for example `ClockScene` and `InfoScene`) are caller-owned
and live in optional scene modules.

`InfoScene` now takes `InfoLayout` from `pypixoo.info_dsl`. The DSL (rows,
styles, table alignment) is composition-layer behavior, not runtime behavior in
`ScenePlayer`.

Device-vs-host behavior
-----------------------

- `Device/PlayTFGif` with URL source: **device fetches and decodes**.
- `Draw/SendHttpGif` / `push_buffer`: **host uploads pixels**.
- Scene transitions (`cross_fade`, `push_*`, `slide_over_*`, `wipe_*`):
  **host-side compositing** in PyPixoo.
- Text overlays (`Draw/SendHttpText`): **device-side overlay rendering** on top
  of uploaded animation context.

Fonts: built-in vs web
----------------------

- Built-in animation fonts (0-7): used by `Draw/SendHttpText`.
- Display list fonts: used by `Draw/SendHttpItemList`.
- Web fonts (Google Fonts): only when browser-rendering frames then uploading.
