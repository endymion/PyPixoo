# PyPixoo

[![PyPI version](https://img.shields.io/pypi/v/pypixoo.svg)](https://pypi.org/project/pypixoo/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/endymion/PyPixoo/actions/workflows/ci.yml/badge.svg)](https://github.com/endymion/PyPixoo/actions/workflows/ci.yml)
[![codecov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/endymion/PyPixoo/main/coverage.json)](https://github.com/endymion/PyPixoo/actions)

> The Pixoo library you can trust — BDD-first, well-tested.

A Python library for the [Divoom Pixoo 64](https://www.divoom.com/products/pixoo-64) display. This is a **true behavior-driven design** project: **behaviors come first**.

## What is this?

PyPixoo is a reimplementation of Pixoo control logic, inspired by [pixoo](https://github.com/SomethingWithComputers/pixoo) but built with BDD from the ground up.

V3 is a breaking redesign with a layered model:
- **L0 transport**: `Pixoo` direct command + frame APIs
- **L1 raster**: `RasterClient` / `AsyncRasterClient` for paced frame pushing
- **L2 scene**: `ScenePlayer` with layer graphs and transitions

## Requirements

- Python 3.9+
- A Divoom Pixoo 64 on your network (for real-device use; specs use a mock)

## Installation

```bash
cd PyPixoo
pip install -e ".[dev]"
```

## Run specs

```bash
behave
```

Specs mock the device HTTP layer, so no Pixoo is required.

## Documentation

Sphinx docs live in `docs/sphinx/`. Build them with:

```bash
pip install -e ".[dev]"
sphinx-build -b html docs/sphinx docs/_build/html
```

Real-device demos live in `demos/` and are documented in `demos/README.md`.
The unified smooth clock demo is `demos/pixooclock.py` (with `--demo` comparison mode).

### CLI

A `pixoo` command is installed with the package. Use a real device on your network to run commands.
By default the CLI reads `PIXOO_DEVICE_IP` (or legacy `PIXOO_IP`) from the environment or a local `.env` file.
Use `--ip` to override for a single command.

```bash
# Fill the display with a color (hex or name)
pixoo fill FF00FF

# Load an image (resized to 64×64) and push
pixoo load-image path/to/image.png

# Upload native sequence
pixoo upload-sequence frame1.png frame2.png --speed-ms 120 --mode command_list --chunk-size 40

# Native GIF playback
pixoo play-gif-url https://example.com/anim.gif
pixoo play-gif-file divoom_gif/1.gif
pixoo play-gif-dir divoom_gif/

# First-class low-level raster operations
pixoo raster push --color dark.amber10
pixoo raster stream --fps 2 --duration 5 --primary-color black --secondary-color dark.gray8

# High-level scene runtime
pixoo scene run --scene clock --duration 15
pixoo scene run --scene info --info-title STATUS --info-font tiny5 --info-header-height 12
pixoo scene run --scene info --info-layout-json '{"rows":[{"kind":"text","content":"STATUS"},{"kind":"table","column_align":["left","right"],"cells":[{"value":"CPU"},{"value":"42%"}]}]}'
pixoo scene enqueue --from-scene clock --to-scene info --transition push-left --duration-ms 600
pixoo scene demo --all-transitions --run-seconds 30

# List built-in display list fonts (no device required)
pixoo list-fonts

# Send a native text overlay (requires a prior animation upload)
pixoo text-overlay "hello" --x 0 --y 40 --font font_4 --width 56 --speed 10

# Clear overlays
pixoo clear-text

# Raw command passthrough
pixoo raw-command Device/SetHighLightMode Mode=1
```

If the `pixoo` script is not on your PATH, run `python -m pypixoo.cli` instead.

## Usage

### L1 Raster streaming

```python
from pypixoo import AsyncRasterClient, Pixoo, PixooFrameSink
from pypixoo.buffer import Buffer

pixoo = Pixoo("192.168.0.37")
pixoo.connect()

sink = PixooFrameSink(pixoo, reconnect=True)
raster = AsyncRasterClient(sink)

frame = Buffer.from_flat_list([40] * (64 * 64 * 3))
```

### L2 Scene runtime

```python
import asyncio
from pypixoo import AsyncRasterClient, LayerNode, Pixoo, PixooFrameSink, QueueItem, RenderContext, ScenePlayer, TransitionSpec
from pypixoo.buffer import Buffer

class SolidLayer:
    name = "solid"
    def __init__(self, color):
        self.color = color
    def render(self, ctx: RenderContext) -> Buffer:
        return Buffer.from_flat_list([c for _ in range(64 * 64) for c in self.color])

class SolidScene:
    def __init__(self, name, color):
        self.name = name
        self.layer = SolidLayer(color)
    def layers(self, ctx):
        return [LayerNode(id=f"{self.name}-layer", layer=self.layer)]
    def on_enter(self): pass
    def on_exit(self): pass

async def main():
    pixoo = Pixoo("192.168.0.37")
    pixoo.connect()
    player = ScenePlayer(AsyncRasterClient(PixooFrameSink(pixoo)), fps=3)
    await player.set_scene(SolidScene("a", (0, 0, 0)))
    await player.enqueue(
        QueueItem(
            scene=SolidScene("b", (120, 120, 120)),
            transition=TransitionSpec(kind="push_left", duration_ms=600),
        )
    )
    task = asyncio.create_task(player.run())
    await asyncio.sleep(5)
    await player.stop()
    await task

asyncio.run(main())
```

### Basic display

```python
from pypixoo import Pixoo

pixoo = Pixoo("192.168.0.37")
pixoo.connect()
pixoo.fill(255, 0, 68)
pixoo.push()
```

### Native HttpGif upload

```python
from pypixoo import GifFrame, GifSequence, Pixoo, UploadMode
from pypixoo.buffer import Buffer

pixoo = Pixoo("192.168.0.37")
pixoo.connect()

buf = Buffer.from_flat_list([c for _ in range(64 * 64) for c in (255, 0, 0)])
seq = GifSequence(frames=[GifFrame(image=buf, duration_ms=120)], speed_ms=120)

pic_id = pixoo.upload_sequence(seq, mode=UploadMode.COMMAND_LIST, chunk_size=40)
print(pic_id)
```

### Native GIF playback and overlays

```python
from pypixoo import GifSource, Pixoo, TextOverlay

pixoo = Pixoo("192.168.0.37")
pixoo.connect()

pixoo.play_gif(GifSource.url("https://example.com/anim.gif"))

# Overlay text is intended for uploaded HttpGif playback contexts
pixoo.send_text_overlay(TextOverlay(text="hello", x=0, y=40, text_id=1))
pixoo.clear_text_overlay()
```

### Mix static and generated frames, then upload natively

```python
from pypixoo import FrameRenderer, Pixoo, StaticFrameSource, UploadMode, WebFrameSource
from pypixoo.buffer import Buffer

buf = Buffer.from_flat_list([80] * (64 * 64 * 3))
renderer = FrameRenderer(
    sources=[
        StaticFrameSource(buffer=buf, duration_ms=100),
        WebFrameSource(url="http://localhost:6006/?t=0.1", timestamps=[0.0, 0.5, 1.0], duration_per_frame_ms=150),
    ]
)
seq = renderer.precompute()

pixoo = Pixoo("192.168.0.37")
pixoo.connect()
pixoo.upload_sequence(seq, mode=UploadMode.COMMAND_LIST)
```

### Native fonts + web backgrounds

```python
from pypixoo import BuiltinFont, FrameRenderer, Pixoo, TextOverlay, WebFrameSource

renderer = FrameRenderer(
    sources=[
        WebFrameSource(
            url="http://localhost:6006/iframe.html?id=pixoo-clock--default",
            timestamps=[0.0, 0.5, 1.0],
            duration_per_frame_ms=200,
            browser_mode="persistent",
        )
    ]
)
seq = renderer.precompute()

pixoo = Pixoo("192.168.0.37")
pixoo.connect()
pixoo.upload_sequence_with_overlays(
    seq,
    overlays=[
        TextOverlay(text="ALERT", x=2, y=2, font=BuiltinFont.FONT_4, text_width=60, speed=8),
    ],
    clear_before=True,
)
```

## Project structure

```
PyPixoo/
  storybook-app/      # React components for 64×64 (Storybook)
  features/           # Gherkin specs (behave)
  src/pypixoo/        # Library
  tests/              # Unit tests (pytest)
  PR_FAQ.md           # Project rationale and roadmap
  AGENTS.md           # Agent guide
```
