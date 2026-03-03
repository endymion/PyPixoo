# API reference export

This folder contains scripts and artifacts for the official Divoom ShowDoc API.
Raw ShowDoc exports must not be committed and are gitignored.

## Export ShowDoc

```bash
python scripts/showdoc_export.py --item-id 5 --base-url http://docin.divoom-gz.com --out-dir docs/api/showdoc
```

This generates:

- `docs/api/showdoc/raw/` – raw JSON responses per page
- `docs/api/showdoc/markdown/` – page content rendered to markdown
- `docs/api/showdoc/index.json` – page index metadata

## Build command matrix

```bash
python scripts/build_command_matrix.py --docs docs/api/showdoc --out docs/api/command_matrix.md
```

The command matrix compares the official docs to SDK support status.
