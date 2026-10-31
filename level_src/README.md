# Level sources

The sources that [custom levels](../doc/custom_levels.md) are built from with `python tools/build_level.py level_src/<name>`, one folder each: a map modelled in Blender, as its `.obj`, `.mtl` and images, a `level.cfg` with its `turn` and `scale` if they aren't the defaults, and an `objects.json` with where Crash starts and the level ends, if it sets them. The built level goes to `build/levels/<name>`.

One level source is included in the repository: `tide_ruins/`, made for c1x. Build it with `python tools/build_level.py level_src/tide_ruins` and boot into it with `boot_level = tide_ruins` in `settings.cfg`. The rest of `level_src/` is ignored by git, so sources you add stay local.

| Source | Build it with | Origin |
|---|---|---|
| `tide_ruins/` | `python tools/build_level.py level_src/tide_ruins` | Made for c1x, with procedural textures. It has boxes, one of each subtype in a row just after the start, and ends at a warp pad on the gold platform at the far end. |
