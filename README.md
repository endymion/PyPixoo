# PyPixoo

[![PyPI version](https://img.shields.io/pypi/v/pypixoo.svg)](https://pypi.org/project/pypixoo/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/endymion/PyPixoo/actions/workflows/ci.yml/badge.svg)](https://github.com/endymion/PyPixoo/actions/workflows/ci.yml)
[![codecov](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/endymion/PyPixoo/main/coverage.json)](https://github.com/endymion/PyPixoo/actions)

> The Pixoo library you can trust — BDD-first, well-tested.

A Python library for the [Divoom Pixoo 64](https://www.divoom.com/products/pixoo-64) display. This is a **true behavior-driven design** project: **behaviors come first**. We work **outside-in** and **backward** from observable behavior — write Gherkin scenarios first, run them (expect failures), implement until they pass. Specs mock the device and assert library behavior; we test the library, not the device.

## What is this?

PyPixoo is a reimplementation of Pixoo control logic, inspired by [pixoo](https://github.com/SomethingWithComputers/pixoo) but built with BDD from the ground up. Outside-in: we specify observable behavior in Gherkin before writing production code, then implement just enough to make the specs pass. CI runs without a real Pixoo; specs mock HTTP and verify our buffer handling, API payloads, and control flow.

Planned evolution: a Pydantic buffer model with introspection for assertions; features for constructing images and running animation sequences with timing; async fire-and-forget constructs that push frames at the right times; headless browser rendering; and React + Storybook components that run on the Pixoo with a `time` parameter for frame rendering (variable frame rate, animation timing intact). See [PR_FAQ.md](PR_FAQ.md) for rationale and roadmap. See [AGENTS.md](AGENTS.md) for agent guidance.

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

## Usage

```python
from pypixoo import Pixoo

pixoo = Pixoo("192.168.0.37")
pixoo.connect()
pixoo.fill(255, 0, 68)  # RGB red
pixoo.push()
```

## Project structure

```
PyPixoo/
  features/           # Gherkin specs (behave)
  src/pypixoo/        # Library
  PR_FAQ.md           # Project rationale and roadmap
  AGENTS.md           # Agent guide
```
