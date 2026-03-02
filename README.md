# PyPixoo

[![PyPI version](https://img.shields.io/pypi/v/pypixoo.svg)](https://pypi.org/project/pypixoo/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/endymion/PyPixoo/actions/workflows/ci.yml/badge.svg)](https://github.com/endymion/PyPixoo/actions/workflows/ci.yml)
[![codecov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/endymion/PyPixoo/main/coverage.json)](https://github.com/endymion/PyPixoo/actions)

> The Pixoo library you can trust — BDD-first, well-tested.

A Python library for the [Divoom Pixoo 64](https://www.divoom.com/products/pixoo-64) display. This is a **true behavior-driven design** project: **behaviors come first**.

## What is this?

PyPixoo is a reimplementation of Pixoo control logic, inspired by [pixoo](https://github.com/SomethingWithComputers/pixoo) but built with BDD from the ground up.

V2 is a breaking redesign that aligns with native Pixoo command behavior:
- Native sequence upload via `Draw/SendHttpGif` and `Draw/CommandList`
- Native GIF playback via `Device/PlayTFGif`
- Native text overlays via `Draw/SendHttpText` / `Draw/ClearHttpText`
- Native cycle orchestration across uploaded sequences and GIF sources

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

### CLI

A `pypixoo` command is installed with the package. Set `PIXOO_REAL_DEVICE=1` to send to a real device.

```bash
# Fill the display with a color (hex or name)
PIXOO_REAL_DEVICE=1 pypixoo fill FF00FF

# Load an image (resized to 64×64) and push
PIXOO_REAL_DEVICE=1 pypixoo load-image path/to/image.png

# Upload native sequence
PIXOO_REAL_DEVICE=1 pypixoo upload-sequence frame1.png frame2.png --speed-ms 120 --mode command_list --chunk-size 40

# Native GIF playback
PIXOO_REAL_DEVICE=1 pypixoo play-gif-url https://example.com/anim.gif
PIXOO_REAL_DEVICE=1 pypixoo play-gif-file divoom_gif/1.gif
PIXOO_REAL_DEVICE=1 pypixoo play-gif-dir divoom_gif/

# Cycle ordered items
PIXOO_REAL_DEVICE=1 pypixoo cycle --item 'sequence=120:frame1.png,frame2.png' --item 'url=https://example.com/anim.gif' --loop 2
```

If the `pypixoo` script is not on your PATH, run `python -m pypixoo.cli` instead.

## Usage

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

### Cycle orchestration

```python
from pypixoo import CycleItem, GifSource, Pixoo

pixoo = Pixoo("192.168.0.37")
pixoo.connect()

items = [
    CycleItem(source=GifSource.url("https://example.com/a.gif")),
    CycleItem(source=GifSource.tf_file("divoom_gif/1.gif")),
]
handle = pixoo.start_cycle(items, loop=2)
handle.wait()
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
