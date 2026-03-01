# PyPixoo

> The Pixoo library you can trust — BDD-first, well-tested.

A Python library for the [Divoom Pixoo 64](https://www.divoom.com/products/pixoo-64) display. PyPixoo is driven by Gherkin specs: write scenarios first, run them (expect failures), implement until they pass.

## What is this?

PyPixoo is a reimplementation of Pixoo control logic, inspired by [pixoo](https://github.com/SomethingWithComputers/pixoo) but built with BDD from the ground up. Specs run against a real device, so you get integration confidence that the library actually works on a Pixoo 64.

See [PR_FAQ.md](PR_FAQ.md) for the project rationale and FAQ. See [AGENTS.md](AGENTS.md) for guidance for AI agents working on the codebase.

## Requirements

- Python 3.10+
- A Divoom Pixoo 64 on your network
- Device IP (e.g. `192.168.0.37`)

## Installation

```bash
cd PyPixoo
pip install -e ".[dev]"
```

## Run specs

```bash
behave
```

Specs require a real Pixoo device. The first scenario uses a hardcoded IP (`192.168.0.37`). Edit `features/display.feature` if your device has a different IP.

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
  features/           # Gherkin specs
  src/pypixoo/        # Library
  PR_FAQ.md           # Project rationale
  AGENTS.md           # Agent guide
```
