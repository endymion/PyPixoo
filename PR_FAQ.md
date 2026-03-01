# PyPixoo — PR FAQ (RFC-style)

> The Pixoo library you can trust — BDD-first, well-tested.

## Problem

The existing [pixoo](https://github.com/SomethingWithComputers/pixoo) project works but has no BDD or executable specs. Demos are brittle, behavior is unclear from reading the code alone, and it is hard to trust changes or evolve the API. Integration with a real device is implicit and untested.

## Goals

- **BDD-first:** Gherkin specs drive implementation. Write scenarios first, see them fail, implement until they pass.
- **Test the library, not the device:** Specs mock the device and assert library behavior. The device is known to work.
- **Minimal v1:** Connect to device, draw one primitive (fill), push to screen.
- **Approachable:** Works for hobbyists and developers — simple API, clear docs.
- **Buffer-centric evolution:** A clean Pydantic buffer model with introspection for effective assertions; features focus on constructing images and running animation sequences with timing.

## Non-goals

- Feature parity with pixoo in v1
- Requiring a real device for CI (we mock for automated tests)

## Proposed approach

1. Reimplement from scratch, using pixoo as a reference for the HTTP API.
2. Use Gherkin (Behave) specs as the single source of truth.
3. Mock device HTTP in specs so CI runs without a Pixoo; assert library behavior only.
4. Start with connect → fill → push. Add buffer introspection, image construction, and animation incrementally.

## Roadmap (epics in Kanbus)

- **Buffer model and assertions:** Pydantic class representing the 64×64 display buffer with enough introspection (e.g. region checks, pixel equality) to write effective Gherkin assertions.
- **Image construction:** Primitives and helpers for constructing images to send.
- **Animation sequences:** Frame sequences with timing between frame updates.
- **Async fire-and-forget animation:** Asynchronous constructs that push frames at the right times without blocking.
- **Headless browser rendering:** Load a headless browser and render the buffer for preview/debugging.
- **React + Storybook on Pixoo:** Use Storybook to construct and preview React components on the computer; run the same components on the Pixoo. Components support a `time` parameter for frame rendering (timestamp), enabling animation libraries (gsap, Framer Motion) with easing. Variable frame rate is acceptable: the device may not sustain a high frame rate, but animation timing remains correct when driven by `time` rather than frame count.

---

## FAQ

### Why reimplement instead of wrapping or extending pixoo?

To own the design and test surface from the start. A wrapper would inherit pixoo's untested behavior. A reimplementation lets us define behavior in Gherkin first and implement only what the specs require.

### Why mock the device in specs?

We test the library, not the device. The device is known to work. Specs mock `requests.post` and assert that our buffer handling, API payloads, and control flow behave correctly. CI runs without a Pixoo on the network.

### What happens if I want to run against a real device?

Use the same specs with a live Pixoo: remove or disable the mock in the environment. The specs exercise the real API when a device is reachable.

### What is the minimal "one thing" to draw in v1?

**Fill.** A single solid color across the display. Simplest primitive, no fonts or images. Text and other primitives come in later slices.
