# Pixoo 64 React components (Storybook)

React components designed for the **64×64** Pixoo display. Stories run in Storybook; PyPixoo’s headless browser can capture frames by loading Storybook URLs with a `t` (time) argument for animation.

## Run Storybook

From this directory:

```bash
npm install
npm run storybook
```

Storybook runs at **http://localhost:6006**. The preview is forced to 64×64 so it matches the device.

## Use with PyPixoo

1. Start Storybook (`npm run storybook` in `storybook-app/`).
2. In Python, use `WebFrameSource` with the iframe URL for your story and pass timestamps for `t`:

```python
from pypixoo import Pixoo, FrameRenderer, WebFrameSource, AnimationPlayer

# Story URL (no t yet – we add it per frame)
BASE = "http://localhost:6006/iframe.html?id=pixoo-clock--default"

sources = [
    WebFrameSource(
        url=BASE,
        timestamps=[0, 0.25, 0.5, 0.75],  # t = 0, 0.25, 0.5, 0.75
        duration_per_frame_ms=200,
        browser_mode="persistent",
        timestamp_param="t",
    )
]
renderer = FrameRenderer(sources)
seq = renderer.precompute()
# Play on device...
```

The library appends `&t=<timestamp>` to the URL for each frame, so the Clock (or any component that uses the `t` arg) updates per frame.

## Stories

- **Pixoo/Clock** – Simple clock with a hand; `t` (0–1) sets the hand angle (one full rotation per cycle).

## Adding components

1. Add a component under `src/components/` that accepts a `t` prop (and any other args).
2. Add a `.stories.tsx` file and export stories with args (e.g. `t`).
3. Use the story’s iframe URL in `WebFrameSource` as above; vary `timestamps` for animation.
