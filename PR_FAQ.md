# PyPixoo — PR FAQ (RFC-style)

> The Pixoo library you can trust — BDD-first, well-tested.

## Problem

The existing [pixoo](https://github.com/SomethingWithComputers/pixoo) project works but has no BDD or executable specs. Demos are brittle, behavior is unclear from reading the code alone, and it is hard to trust changes or evolve the API.

## Goals

- **BDD-first:** Gherkin specs drive implementation. Write scenarios first, see them fail, implement until they pass.
- **Test the library, not the device:** Specs mock the device and assert library behavior.
- **Native command alignment:** Represent Pixoo behavior directly (`Draw/SendHttpGif`, `Draw/CommandList`, `Device/PlayTFGif`, text overlay commands).
- **Breaking redesign for clarity:** Prefer a clean V2 API over preserving legacy abstractions.
- **Approachable:** Works for hobbyists and developers — simple API, clear docs.

## Non-goals

- Preserving the legacy `AnimationPlayer`/`AnimationSequence` API
- Requiring a real device for CI (we mock for automated tests)
- TF card file management tooling in this wave

## Proposed approach

1. Reimplement from scratch, using pixoo as a reference for the HTTP API.
2. Use Gherkin (Behave) specs as the single source of truth.
3. Mock device HTTP in specs so CI runs without a Pixoo; assert library behavior only.
4. Build around native commands first, then orchestrate higher-level cycle behavior.

## V2 roadmap (epics in Kanbus)

- **V2 native HttpGif upload protocol:** `Draw/SendHttpGif`, `Draw/CommandList`, and PicID lifecycle.
- **V2 native GIF playback + text overlay rules:** `Device/PlayTFGif` and overlay compatibility rules.
- **V2 sequence cycling orchestration:** Async cycle of mixed native item types.
- **V2 API/CLI migration and release:** Breaking API rollout, docs, and major release path.

---

## FAQ

### Why breaking changes?

The legacy animation abstraction did not align with how Pixoo actually behaves. A breaking redesign keeps the public API close to native device semantics and reduces hidden behavior.

### Why mock the device in specs?

We test the library, not the device. Specs mock `requests.post` and assert payloads, sequencing, and control flow. CI runs without a Pixoo on the network.

### How do I run against a real device?

Run the CLI or `@real_device` scenarios against a real device.
