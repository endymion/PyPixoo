# PyPixoo — PR FAQ (RFC-style)

> The Pixoo library you can trust — BDD-first, well-tested.

## Problem

The existing [pixoo](https://github.com/SomethingWithComputers/pixoo) project works but has no BDD or executable specs. Demos are brittle, behavior is unclear from reading the code alone, and it is hard to trust changes or evolve the API. Integration with a real device is implicit and untested.

## Goals

- **BDD-first:** Gherkin specs drive implementation. Write scenarios first, see them fail, implement until they pass.
- **Real-device integration tests:** Specs run against an actual Divoom Pixoo 64 on the network.
- **Minimal v1:** Connect to device, draw one primitive (fill), push to screen.
- **Approachable:** Works for hobbyists and developers — simple API, clear docs.

## Non-goals

- Feature parity with pixoo in v1
- Simulator or mock in the first slice (real device required)
- Text drawing, images, or advanced primitives in v1

## Proposed approach

1. Reimplement from scratch, using pixoo as a reference for the HTTP API.
2. Use Gherkin (Behave) specs as the single source of truth.
3. Require a real Pixoo 64 on the network for integration tests.
4. Start with connect → fill → push. Add more primitives incrementally.

---

## FAQ

### Why reimplement instead of wrapping or extending pixoo?

To own the design and test surface from the start. A wrapper would inherit pixoo’s untested behavior. A reimplementation lets us define behavior in Gherkin first and implement only what the specs require.

### Why require a real device for v1 specs (vs mock)?

We want integration confidence: “it works on a real Pixoo.” A mock would prove logic, not connectivity or device API. Device-based specs are the differentiator for v1.

### What happens if no device is available when running specs?

Specs will fail with a connection error. Document that `PIXOO_IP` must point to a reachable Pixoo. Future work could add `@skip_if_no_device` or env-gated skip logic.

### What is the minimal "one thing" to draw in v1?

**Fill.** A single solid color across the display. Simplest primitive, no fonts or images. Text and other primitives come in later slices.
