# CHANGELOG

<!-- version list -->

## v2.2.2 (2026-03-02)

### Bug Fixes

- Replace mixed marker mode with two-dot-size clockface
  ([`27115e0`](https://github.com/endymion/PyPixoo/commit/27115e00809dbc49050cefc3ec20d3df7fa54733))


## v2.2.1 (2026-03-02)

### Bug Fixes

- Make realtime clock demo auto-reconnect on disconnect
  ([`5695d75`](https://github.com/endymion/PyPixoo/commit/5695d75d7c6e5ebe13cef57c385825e0ee1234c7))


## v2.2.0 (2026-03-02)

### Features

- Add clock marker color option for realtime demo
  ([`a4b444a`](https://github.com/endymion/PyPixoo/commit/a4b444acdbf0ebb4278b16ad55eb5e7a12c0630b))


## v2.1.0 (2026-03-02)

### Features

- Add clockface marker modes and minute-cycle demo
  ([`07158e6`](https://github.com/endymion/PyPixoo/commit/07158e670526371bfc5e92901f433792cfd3e9ef))


## v2.0.2 (2026-03-02)

### Bug Fixes

- Default clock demos to no-loading push delivery
  ([`d0bb72d`](https://github.com/endymion/PyPixoo/commit/d0bb72d6567c8bff88f81c8e56e0b2e65dc3515a))


## v2.0.1 (2026-03-02)

### Bug Fixes

- Modernize clock demos for V2 native smooth playback
  ([`8dd8ee4`](https://github.com/endymion/PyPixoo/commit/8dd8ee44cc402ba8cd0cae36a1b81a84f8100bdd))


## v2.0.0 (2026-03-02)

### Bug Fixes

- Update font showcase demo for V2 native playback
  ([`98e7792`](https://github.com/endymion/PyPixoo/commit/98e7792235c9447286573a71e14e8f1484bba5d5))

### Chores

- Checkpoint workspace before v2 redesign
  ([`1e3ec88`](https://github.com/endymion/PyPixoo/commit/1e3ec882204fe07b2cbabf432a588d5788731fd3))

- Close Async fire-and-forget animation epic
  ([`43dae71`](https://github.com/endymion/PyPixoo/commit/43dae7191bfa570dde0b5f35c5b45c1898ccf9d7))

- Update coverage badge [skip ci]
  ([`826ca59`](https://github.com/endymion/PyPixoo/commit/826ca59ac1f01ba4bff74693f552156c9f4c96f5))

- Update coverage badge [skip ci]
  ([`93dd297`](https://github.com/endymion/PyPixoo/commit/93dd2975e96e8bbcab74c28894f7f59b2a37e2bc))

### Features

- Migrate PyPixoo to native V2 GIF sequencing API
  ([`a45847f`](https://github.com/endymion/PyPixoo/commit/a45847fb73eb24da2c10ca53e982086d058ea6b0))

- Storybook clock, realtime device clock, demos use device by default
  ([`02a45be`](https://github.com/endymion/PyPixoo/commit/02a45be865ef95c8f18bf188979d69b443db458e))


## v1.3.0 (2026-03-01)

### Chores

- Close Animation sequences with timing epic
  ([`7e4f138`](https://github.com/endymion/PyPixoo/commit/7e4f138ea408a3043aa37f1419ef3f7be0ba0267))

### Features

- Add animation sequences with callbacks and chained demo
  ([`48d7861`](https://github.com/endymion/PyPixoo/commit/48d78617a6265289acabeba1309c78cecad8b3ce))


## v1.2.0 (2026-03-01)

### Bug Fixes

- Use Union[str, Path] for Python 3.9 compatibility
  ([`44756bd`](https://github.com/endymion/PyPixoo/commit/44756bd3b858e6a58ef6eec827b20f4eea9b53dc))

### Features

- Add load_image to load images into buffer
  ([`c202e5c`](https://github.com/endymion/PyPixoo/commit/c202e5c9a49d0518bc6574436bb46c71eebe3ddf))


## v1.1.0 (2026-03-01)

### Chores

- Close Basic testing foundation epic
  ([`b9740b8`](https://github.com/endymion/PyPixoo/commit/b9740b876d60bf4d2f1470b02f538519f2d81651))

- Close Load image into buffer epic
  ([`7ff4ef1`](https://github.com/endymion/PyPixoo/commit/7ff4ef14f621129cd03c5e46e8fb2a45d72e32ea))

- Update coverage badge [skip ci]
  ([`e7eff11`](https://github.com/endymion/PyPixoo/commit/e7eff112c1d270bdec56cbe2506f429d11aa8bb4))

### Features

- **tests**: Add 100% coverage scenarios and gate
  ([`784984b`](https://github.com/endymion/PyPixoo/commit/784984bb355a98fa2ed38a2a0503754887dc2da9))


## v1.0.3 (2026-03-01)

### Bug Fixes

- Paths-ignore coverage.json to prevent workflow loop from badge pushes
  ([`f963d94`](https://github.com/endymion/PyPixoo/commit/f963d94c4bbd5da011815729736aaaf0f3652845))

- **ci**: Run coverage-badge after release to avoid push race
  ([`89ee185`](https://github.com/endymion/PyPixoo/commit/89ee185cbcbd8b52b6f3ef3723a0c7f0ecf21083))

### Chores

- Self-hosted coverage badge, no third-party service
  ([`0a69639`](https://github.com/endymion/PyPixoo/commit/0a69639b4816ec09ed52605eafe7e65992399dfc))

- Update coverage badge [skip ci]
  ([`0b7b02d`](https://github.com/endymion/PyPixoo/commit/0b7b02da5aaa2625dacbb51f13265613f8c6fa7c))


## v1.0.2 (2026-03-01)

### Bug Fixes

- Codecov OIDC, upload once from 3.12 job, use official badge URL
  ([`666faab`](https://github.com/endymion/PyPixoo/commit/666faabbc5b5ff6df9409cdbd6d062083adde259))

### Documentation

- Badge order PyPI/MIT/CI/coverage; fix Codecov upload with v5 and token
  ([`cac6088`](https://github.com/endymion/PyPixoo/commit/cac60880d74a6e898313c9f043fcf14288173855))

- PyPI version badge label, shields.io codecov badge for main
  ([`6cd8807`](https://github.com/endymion/PyPixoo/commit/6cd88078b7f77a87b7a9d981023eb8dc7e8fe30e))


## v1.0.1 (2026-03-01)

### Bug Fixes

- Full clone in release job so semantic-release sees tags and history
  ([`530f4d2`](https://github.com/endymion/PyPixoo/commit/530f4d251e6cbb09b70eb8c7c5436c93fd556c1d))


## v1.0.0 (2026-03-01)

- Initial Release
