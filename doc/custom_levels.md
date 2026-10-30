# Custom levels

The game can boot straight into a level from the `custom_levels/` folder (next to `streams/`) instead of the title screen. Set `boot_level` in `settings.cfg` to the level's name:

```
boot_level = mock
```

This loads `custom_levels/mock.nsd` and `custom_levels/mock.nsf`. Leave `boot_level` out to start the game normally. If the level's files aren't there, the game says so in the console and starts normally.

A custom level loads as the test level (`LID_TEST`), so code that does something special for a particular real level doesn't apply to it. Leaving a custom level (dying with no lives left, or finishing it) goes to the title screen or level end screen as usual, which load from `streams/`.

Custom levels are made with `tools/nslevel.py`, from the real levels in `streams/` (see [Running](running.md)). They contain game data copied from the disc, so `custom_levels/` is ignored by git; anyone can make them again from their own copy of the game.

## Making levels

From the project directory:

| Command | What it does |
|---|---|
| `python tools/nslevel.py course [name]` | Makes an obstacle course, `custom_levels/<name>` (`course` by default): gaps to jump, steps and a ledge, a row of boxes, a checkpoint, two crabs, and the warp pad at the end. |
| `python tools/nslevel.py mock [name]` | Makes a level from scratch, `custom_levels/<name>` (`mock` by default): a long flat sandy floor, a camera that follows Crash along it, and Crash. |
| `python tools/nslevel.py copy <lid> <name>` | Copies a real level, e.g. `copy 9 beach_copy` for N. Sanity Beach, as `custom_levels/<name>`. |
| `python tools/nslevel.py list <lid>` | Lists a real level's entries by type, and the GOOL executables it uses. |

`lid` is the level id in hex, as in the file names in `streams/` (`9` is `s0000009`, N. Sanity Beach).

### The mock level

The mock level is built from scratch, apart from Crash, the HUD and the other objects every level has, which come from N. Sanity Beach with everything they use (their code, models, textures and sounds). It is one zone of 4096 by 3200 by 8192 zone units with:

- a flat floor 400 units above the bottom of the zone: solid ground in the zone's collision octree, and a world mesh of 512 unit squares with N. Sanity Beach's most common texture (sand)
- one camera path that follows Crash along the zone, with the same offset and angles as N. Sanity Beach's follow cameras
- Crash, near one end

The sizes, the floor and the camera are set by the `MOCK_` constants and `make_mock` in `tools/nslevel.py`.

### The course level

The course is built the same way, along a zone of 4096 by 4096 by 8192 zone units. From the start:

1. the start platform
2. a gap (falling in loses a life, and you start again from the start or the last checkpoint)
3. a platform with a row of boxes: plain, `?`, arrow (bounce), Aku Aku and life
4. two steps up, the top one with a checkpoint box
5. a gap to a ledge
6. a drop to a wide stretch with two crabs
7. a gap to the end platform, with the warp pad that finishes the level

The layout is a list of solid blocks (`COURSE_PLATFORMS` and `COURSE_GAPS` in `tools/nslevel.py`, on a 128 unit grid), which `blocks_rect_bytes` turns into the collision octree and `blocks_mesh` into the world mesh (N. Sanity Beach's two most used textures, on tops and sides). Under each gap is a thin floor whose octree leaf kills what lands on it (subtype 11, the game's fall death). The boxes, crabs and warp pad are copies of N. Sanity Beach's own, moved into place (`place_entity`); the box kinds are the `BoxsC` subtypes listed by `COURSE_BOXES`. The camera follows Crash along the course, at a height that follows the ground.

## How levels are made

A level is a `.nsd` and a `.nsf`. The `.nsf` holds the level's entries (zones, world meshes, models, GOOL code, sounds and so on) in 64 KB pages, and the `.nsd` holds a table of which page each entry is in and the level header (`LDAT`: the zone and camera path to start in, the GOOL executables the level uses, and the loading screen image). See `src/ns.h` and `src/formats/` for the layouts. `tools/nslevel.py` reads and writes them:

- **Reading.** The game's pages are read uncompressed from where `pages_offset` says they start; the compressed copies at the front of a `.nsf`, which the PS1 loaded first, aren't needed on pc.
- **Writing.** Levels are written uncompressed with no compressed copies, and with the page table grouped by each entry id's lookup bucket, since the game finds an entry by scanning forward from its bucket.
- **Cutting a level down.** `cut_level` keeps the entries a set of entries uses, following entry ids mentioned in their data, and repacks them. Each page lists its entries in bucket order: the game finds a page's entries by scanning forward from its first entry's bucket.
- **Zones.** A zone's collision is an octree in its second item. It has to split along x and z as well as y, so that no cell is more than about 2000 zone units across: the game stores a cell's position relative to the point it is testing as a 16 bit number, so a bigger cell ends up in the wrong place.
- **Sort lists.** Each camera path has a sort list (`SLST`) giving the world polygons to draw from each point along it. It must only list polygons in front of the camera: the renderer can't draw a polygon with a corner behind the camera, and spreads it across the screen instead. A whole entry has to fit in a 64 KB page, which limits how many polygons and camera path points a level can have, since each point gets a full list.
- **Texture pages.** A texture page is only put in video memory when something opens it, which for a zone is its load list. A model whose texture page nobody opened is drawn blank, so a custom level's zone lists every texture page in the level.
- **Objects.** An object's lighting comes from a region of the zone's octree named by the entity's spawn flags; a copied object is pointed at the plain region Crash uses, since its own zone's regions aren't in the custom level.

## Tests

The tool's tests are in `tools/tests/`; run them from the project directory with:

```
python -m unittest discover -s tools/tests
```

The tests that read N. Sanity Beach are skipped if it isn't in `streams/`.
