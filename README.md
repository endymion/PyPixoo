# PyPixoo

[![PyPI version](https://img.shields.io/pypi/v/pypixoo.svg)](https://pypi.org/project/pypixoo/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/endymion/PyPixoo/actions/workflows/ci.yml/badge.svg)](https://github.com/endymion/PyPixoo/actions/workflows/ci.yml)
[![codecov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/endymion/PyPixoo/main/coverage.json)](https://github.com/endymion/PyPixoo/actions)

> The Pixoo library you can trust — BDD-first, well-tested.

A Python library for the [Divoom Pixoo 64](https://www.divoom.com/products/pixoo-64) display. This is a **true behavior-driven design** project: **behaviors come first**. We work **outside-in** and **backward** from observable behavior — write Gherkin scenarios first, run them (expect failures), implement until they pass. Specs mock the device and assert library behavior; we test the library, not the device.

## What is this?

PyPixoo is a reimplementation of Pixoo control logic, inspired by [pixoo](https://github.com/SomethingWithComputers/pixoo) but built with BDD from the ground up. Outside-in: we specify observable behavior in Gherkin before writing production code, then implement just enough to make the specs pass. CI runs without a real Pixoo; specs mock HTTP and verify our buffer handling, API payloads, and control flow.

Features include: a Pydantic buffer model with introspection; animation sequences with per-frame timing and loop control; async fire-and-forget playback with `on_finished` and `on_loop` callbacks; headless browser rendering (Playwright) for web-sourced frames; mixing static buffers and web-rendered frames in the same sequence; and `on_first_frame` / `on_all_frames` callbacks to react to precompute readiness. See [PR_FAQ.md](PR_FAQ.md) for rationale. See [AGENTS.md](AGENTS.md) for agent guidance.

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

Specs mock the device HTTP layer, so no Pixoo is required. The first scenario uses a hardcoded IP (`192.168.0.37`) in the step text; the mock fakes all API calls. Edit `features/display.feature` if you change the IP in your assertions.

### CLI

A `pypixoo` command is installed with the package. Set `PIXOO_REAL_DEVICE=1` to send to a real device.

```bash
# Fill the display with a color (hex or name)
PIXOO_REAL_DEVICE=1 pypixoo fill FF00FF
PIXOO_REAL_DEVICE=1 pypixoo fill f0f
PIXOO_REAL_DEVICE=1 pypixoo fill fuchsia

# Load an image (resized to 64×64) and push
PIXOO_REAL_DEVICE=1 pypixoo load-image path/to/image.png

# Optional: device IP (default 192.168.0.37)
PIXOO_REAL_DEVICE=1 pypixoo --ip 192.168.0.38 fill black
```

If the `pypixoo` script is not on your PATH, run `python -m pypixoo.cli` instead.

## Usage

### Basic display

```python
from pypixoo import Pixoo

pixoo = Pixoo("192.168.0.37")
pixoo.connect()
pixoo.fill(255, 0, 68)  # RGB red
pixoo.push()
```

### Asynchronous animations

Play sequences without blocking. Use callbacks to time events to the animation lifecycle:

```python
from pypixoo import Pixoo, AnimationPlayer, AnimationSequence, Frame
from pypixoo.buffer import Buffer

pixoo = Pixoo("192.168.0.37")
pixoo.connect()

# Build a sequence from buffers
buf = Buffer.from_flat_list([c for _ in range(64 * 64) for c in (255, 0, 0)])
seq = AnimationSequence(frames=[Frame(image=buf, duration_ms=100)])

player = AnimationPlayer(
    seq,
    loop=2,
    on_finished=lambda: print("animation done"),
    on_loop=lambda n: print(f"loop {n}"),
)
player.play_async(pixoo)  # Returns immediately
player.wait()             # Block until done
```

### Mix static and generated frames

Combine pre-built buffers with frames rendered from web URLs in a single sequence. The frame order is preserved: `[static, web, static, web, ...]` stays in that order. Use `on_first_frame` to react when the first web-rendered frame is ready (e.g. to start playback early), and `on_all_frames` when the full sequence is ready:

```python
from pypixoo import Pixoo, FrameRenderer, StaticFrameSource, WebFrameSource, AnimationPlayer
from pypixoo.buffer import Buffer

buf = Buffer.from_flat_list([80] * (64 * 64 * 3))
sources = [
    StaticFrameSource(buffer=buf, duration_ms=100),
    WebFrameSource(
        url="http://localhost:6006/?t=0.1",
        timestamps=[0.0, 0.5, 1.0],
        duration_per_frame_ms=150,
        browser_mode="persistent",  # or "per_frame"
    ),
    StaticFrameSource(buffer=buf, duration_ms=100),
]

renderer = FrameRenderer(sources)
seq = renderer.precompute(
    on_first_frame=lambda: print("first web frame ready"),
    on_all_frames=lambda: print("all frames ready"),
)

player = AnimationPlayer(seq)
player.play_async(pixoo)
player.wait()
```

Requires Playwright: `pip install -e ".[browser]"` (or `.[dev]`).

### Blend modes and end behavior

- **Blend mode**: `opaque` (frame as-is) or `transparent` (composite over background with transparent color).
- **End on**: `last_frame` (hold final frame) or `blank` (clear to `blank_background`).

## Project structure

```
PyPixoo/
  features/           # Gherkin specs (behave)
  src/pypixoo/        # Library
  PR_FAQ.md           # Project rationale and roadmap
  AGENTS.md           # Agent guide
```
