# Vendored dependencies

This directory contains third-party Python packages bundled with Crucible so
that the report renderer (`scripts/render_report.py`) works without requiring
the end user to `pip install` or `uv add` anything before running
`/crucible:run`.

## Packages

| Package    | Version | License | Source |
|------------|---------|---------|--------|
| jinja2     | 3.1.6   | BSD-3-Clause | https://pypi.org/project/Jinja2/3.1.6/ |
| markupsafe | 3.0.3   | BSD-3-Clause | https://pypi.org/project/MarkupSafe/3.0.3/ |

Both are BSD-3-Clause licensed, which is compatible with Crucible's MIT
license. Full license texts ship alongside the package sources as
`JINJA2_LICENSE.txt` and `MARKUPSAFE_LICENSE.txt` in this directory.

## What's included, what isn't

- `jinja2/`: full package source as published on PyPI for 3.1.6.
- `markupsafe/`: pure-Python source only. The optional `_speedups.c` Cython
  extension is **not** included — it would require a C toolchain on the user's
  machine to compile, defeating the point of vendoring. MarkupSafe's pure-Python
  fallback (`_native.py`) is fully functional and is what gets imported on any
  system that does not have the compiled speedup. Performance impact is
  negligible for Crucible's use case (rendering ~10KB markdown reports).

## How it is imported

`scripts/render_report.py` prepends `scripts/_vendor/` to `sys.path` before
importing Jinja2. That keeps the dependency lookup local to the plugin without
polluting the user's Python environment.

## Updating

When bumping to a newer Jinja2 / MarkupSafe:

```bash
mkdir -p /tmp/jinja-vendor
cd /tmp/jinja-vendor
python3 -m pip download jinja2==<NEW> markupsafe==<NEW> --no-deps --no-binary :all: --dest .
tar -xzf jinja2-<NEW>.tar.gz
tar -xzf markupsafe-<NEW>.tar.gz
rm -rf <plugin_root>/scripts/_vendor/jinja2 <plugin_root>/scripts/_vendor/markupsafe
cp -r jinja2-<NEW>/src/jinja2 <plugin_root>/scripts/_vendor/jinja2
cp -r markupsafe-<NEW>/src/markupsafe <plugin_root>/scripts/_vendor/markupsafe
rm <plugin_root>/scripts/_vendor/markupsafe/_speedups.c
rm <plugin_root>/scripts/_vendor/markupsafe/_speedups.pyi
cp jinja2-<NEW>/LICENSE.txt <plugin_root>/scripts/_vendor/JINJA2_LICENSE.txt
cp markupsafe-<NEW>/LICENSE.txt <plugin_root>/scripts/_vendor/MARKUPSAFE_LICENSE.txt
```

Then update the version table at the top of this file and run the byte-stability
test (`uv run pytest tests/test_render_report.py`) to confirm rendered output
is unchanged.
