# Web font renders at 3px height instead of 5px on device

## Summary

When capturing the letter "A" (or any Tiny5 typography) from the browser and sending it to the Pixoo 64, the glyph appears **only 3 pixels tall** on the device instead of the intended **5 pixels tall**. The pipeline (Playwright screenshot → downsampling → threshold → push) is working; the problem is that the **browser-rendered glyph** has only ~3px effective height in the capture, so downsampling cannot add rows that were never drawn.

## Observed behavior

- **letter_a.html** (64×64 viewport, 5px Tiny5 font): Captured frame has lit rows at y = 1, 2, 3 only → **3 rows**.
- **letter_a_192.html** (192×192 viewport, 18px font): Sometimes 5 rows after 3×3 downscale, sometimes still 3 rows depending on **font load timing** (Google Fonts).
- **font_showcase.py** (Storybook TinyText stories): Same 3px-tall rendering when capturing from localhost Storybook.
- **Device**: The Pixoo correctly displays whatever buffer we send; the issue is the content of that buffer, not the device or channel.

## Root cause (current understanding)

1. **64×64 viewport, 5px font**: Chromium/Playwright renders Tiny5 at 5px CSS, but the **visible glyph height** (cap height / bounding box) is only ~3px—either due to font metrics or because the font has not finished loading and a fallback is used. So the screenshot never contains 5 rows of the letter.

2. **Font load timing**: When using Google Fonts (e.g. `family=Tiny5&display=block`), the font may load after `networkidle` or even after `document.fonts.ready`. We added `wait_for_function("document.fonts.check('18px Tiny5')")` and extra timeouts, but results are still inconsistent.

3. **Downsampling cannot invent rows**: 2×2 or 3×3 max-pool (or average) only combines existing pixels. If the source has 3 lit rows, the output has at most 3 (or fewer after averaging). So fixing capture is required; post-processing alone is not enough.

## What was tried

| Approach | Result |
|----------|--------|
| `device_scale_factor=1` (64×64 screenshot, no downscale) | Still 3 lit rows. |
| `device_scale_factor=2` (128×128 → 2×2 max-pool to 64×64) | Still 3 rows. |
| `device_scale_factor=3` (192×192 → 3×3 max-pool) with 64×64 viewport, 5px font | Still 3 rows (glyph only ~9 device px tall). |
| **192×192 viewport**, 15px/18px font, 3×3 downscale | **5 rows** when font loads in time; 3 rows when it doesn’t. |
| Binary threshold (luminance ≥ 64 → white) | Helps anti-aliasing; does not add missing rows. |
| CSS `transform: scaleY(5/3)` on the character | No visible change in captured rows. |
| Larger font (10px) in 64×64 | Still 3 rows. |
| `document.fonts.ready` + `wait_for_function("document.fonts.check('18px Tiny5')")` | Reduces but does not eliminate flakiness. |
| Save full-resolution screenshot before downsampling | Implemented: `letter_a_fullres.png` (192×192) for debugging. Path: `demos/fixtures/letter_a_fullres.png` when running `python demos/screen_test.py --save-frame`. |

## Current workaround

- **Letter A**: Use **letter_a_192.html** (192×192 viewport, 18px Tiny5) and `viewport_size=192` in `WebFrameSource`. This yields 5 rows when the font loads before the screenshot. Full-res screenshot is saved so the user can verify the web font before downsampling.
- **Typography demo (font_showcase)**: Still uses browser capture; same 3px issue unless/until the 192-viewport + font-wait strategy is applied there and font load is reliable.

## Desired state

- **Web font** (Tiny5 from Google Fonts or equivalent) used in HTML/Storybook should render at a **full 5px height** in the captured frame so that after downsampling the device shows a 5-pixel-tall glyph.
- Either:
  - Font load is guaranteed (or detected) before screenshot, and 64×64 + 5px or 192×192 + 15–18px consistently produces 5 rows, or
  - Font is bundled/embedded (e.g. base64 or local TTF) so network timing is not a factor.

## Relevant paths

- **Browser capture**: `src/pypixoo/browser.py` — `WebFrameSource`, `_render_web_frame`, `_screenshot_to_buffer`, `viewport_size`, `save_raw_screenshot_path`, font wait.
- **Letter A fixtures**: `demos/fixtures/letter_a.html` (64×64, 5px), `demos/fixtures/letter_a_192.html` (192×192, 18px).
- **Screen test**: `demos/screen_test.py` — uses `letter_a_192.html`, `viewport_size=192`, `--save-frame` writes `letter_a_fullres.png` and 64×64 pre/post threshold.
- **Typography demo**: `demos/font_showcase.py` — Storybook TinyText; still 3px without 192 viewport + reliable font load.

## How to reproduce

1. Run: `python demos/screen_test.py --save-frame`
2. Open `demos/fixtures/letter_a_fullres.png` (192×192) and check whether the "A" has full height.
3. Open `demos/fixtures/letter_a_rendered.png` (64×64) and count lit rows (y with any white); expect 5 for correct behavior, often 3 currently.
4. Push to device and observe height of the letter on the Pixoo.
