# PyPixoo — Agent Guide


## Project management with Kanbus

Use Kanbus for task management.
Why: Kanbus task management is MANDATORY here; every task must live in Kanbus.
When: Create/update the Kanbus task before coding; close it only after the change lands.
How: See CONTRIBUTING_AGENT.md for the Kanbus workflow, hierarchy, status rules, priorities, command examples, and the sins to avoid. Never inspect project/ or issue JSON directly (including with cat or jq); use Kanbus commands only.
Performance: Prefer kbs (Rust) when available; kanbus (Python) is equivalent but slower.
Warning: Editing project/ directly is a sin against The Way. Do not read or write anything in project/; work only through Kanbus.

This document helps AI agents (and humans) work effectively on PyPixoo.

## Project Overview

PyPixoo is a **true behavior-driven design (BDD)** project: **behaviors come first**. It is a Python library for the Divoom Pixoo 64 display, a reimplementation inspired by [pixoo](https://github.com/SomethingWithComputers/pixoo), with Gherkin specs driving implementation. We work **outside-in** and **backward** from observable behavior — never from implementation details.

## Key Principles

1. **Behaviors come first:** This is BDD. Describe the desired behavior in Gherkin *before* writing production code. Run `behave`, see failures, implement until green.
2. **Outside-in, working backward:** Start from observable outcomes (what the user sees, what the API returns). Work backward into the implementation. Do not design internals first.
3. **Specs mock the device:** We test the library, not the device. Specs mock HTTP and assert library behavior.
4. **Minimal API:** Connect, draw primitives (fill, text, shapes), push to screen.
5. **100% test coverage:** CI fails if coverage is below 100%. Add scenarios (and mocks as needed) so every line in `src/pypixoo/` is covered.

## Project Structure

```
PyPixoo/
  demos/                 # Demo scripts (require real device)
    black_band_transparent.py
    black_band_opaque.py
  features/              # Gherkin specs
    display.feature
    animation.feature
    steps/
      display_steps.py
      animation_steps.py
    environment.py       # Behave hooks
  src/pypixoo/           # Library
    __init__.py
    pixoo.py             # Pixoo client (connect, fill, push)
    animation.py         # AnimationSequence, AnimationPlayer
    buffer.py            # Buffer model
  pyproject.toml
  PR_FAQ.md
  README.md
```

## Workflow

Outside-in, behavior-first:

1. Add or edit scenarios in `features/*.feature` — define the behavior *first*
2. Run `behave` — expect undefined or failing steps
3. Implement steps in `features/steps/` and library code in `src/pypixoo/` — only what the specs require
4. Reference the original pixoo project for HTTP API semantics (e.g. `Draw/SendHttpGif`, `Channel/GetAllConf`)

## Commands

- **Run specs:** `behave --tags '~real_device'` (CI excludes @real_device)
- **Run specs with coverage (must be 100%):** `coverage run -m behave --tags '~real_device' && coverage report --fail-under=100`
- **Run against real device:** `PIXOO_REAL_DEVICE=1 behave --tags real_device` (device plugged in, edit IP in feature file if needed)
- **Install:** `pip install -e ".[dev]"`
- **Device IP:** Specs use hardcoded IP in feature file (e.g. `192.168.0.37`). The device is mocked; no real Pixoo required for CI.

## API Reference (Current)

```python
from pypixoo import Pixoo, AnimationPlayer, AnimationSequence, Frame
from pypixoo.buffer import Buffer

pixoo = Pixoo("192.168.0.37")
pixoo.connect()          # Returns bool, loads GIF counter
pixoo.fill(r, g, b)      # Fill buffer with RGB
pixoo.load_image(path)   # Load image file into buffer (resizes to 64×64 if needed)
pixoo.push()             # Send buffer to device

# Animation
seq = AnimationSequence(frames=[Frame(image=buf, duration_ms=100)], background=buf)
player = AnimationPlayer(
    seq,
    loop=1,
    blend_mode="transparent",
    on_finished=lambda: print("done"),
    on_loop=lambda n: print(f"loop {n}"),
)
player.play_async(pixoo)  # Returns immediately
player.wait()             # Block until done
```
