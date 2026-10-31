# Level sources

The sources that [custom levels](../doc/custom_levels.md) are built from with `python tools/build_level.py level_src/<name>`, one folder each: a map modelled in Blender, as its `.obj`, `.mtl` and images, a `level.cfg` with its `turn` and `scale` if they aren't the defaults, and an `objects.json` placing objects in it, if it has any (see [Objects](#objects)). The built level goes to `build/levels/<name>`.

Some level sources are included in the repository, made for c1x, listed below. Build one with `python tools/build_level.py level_src/<name>` and boot into it with `boot_level = <name>` set in `settings.cfg`. The rest of `level_src/` is ignored by git, so sources you add stay local.

| Source | Build it with | Origin |
|---|---|---|
| `tide_ruins/` | `python tools/build_level.py level_src/tide_ruins` | Made for c1x, with procedural textures. |
| `mossy_creek/` | `python tools/build_level.py level_src/mossy_creek` | Made for c1x, with procedural textures: a more organic map, its shores and ledges curves rather than straight lines. Its `make_map.py` generates its `.obj`, `.mtl` and `objects.json`; to change the level, change it and run it (`python level_src/mossy_creek/make_map.py`) before building. |

## Objects

An object in `objects.json` has a `kind`:

- `spawn`: where Crash starts (one at most)
- `end`: the warp pad that ends the level (one at most)
- `box`: a box, by its `type`: `basic`, `arrow`, `checkpoint`, `iron`, `slatted`, `switch`, `life`, `aku_aku`, `question` or `outline`; `stack` makes a stack of them

See [Objects](../doc/custom_levels.md#objects) in the custom levels doc for what each box looks like, and the other settings (`at`, `raise`, `subtype`).
