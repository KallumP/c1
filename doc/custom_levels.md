# Custom levels

A map modelled in Blender can be built into a level the game boots straight into: its faces become the level's geometry and collision, and Crash starts on it. An `objects.json` beside the map can set where he starts, put a warp pad where the level ends, and place boxes (see [Objects](#objects)); there are no other objects yet (eg: enemies or fruit). What a level is built from is its *level source*, a folder in `level_src/`; the built level goes to `build/levels/`, next to the game. One level source is included to try it with, `level_src/tide_ruins` (see [level_src/README.md](../level_src/README.md) for instructions to play it); the sources you add are ignored by git.

## From Blender to the game

The examples below use the included level source, `level_src/tide_ruins`. It's ready to use, so to try it, do step 1 and then start at step 6.

1. **Get set up (once).** You need the game built (see [Building](building.md)), its files in `streams/` (see [Running](running.md)), Python 3, and [Pillow](https://pypi.org/project/pillow/) for textures (`pip install pillow`). Without Pillow, a map with no images still works.
2. **Get the map ready in Blender** (see [Modelling](#modelling) below): the route running towards +Y, faces pointing the right way, and optionally a `spawn` object and `pit` objects.
3. **Unpack textures** if they're packed in the `.blend`: File > External Data > Unpack Resources. That saves them as image files that the export can point at.
4. **Export** with File > Export > Wavefront (.obj) into a folder of its own in `level_src/`, such as `level_src/tide_ruins/`:
   - keep the default axes (Forward -Z, Up Y)
   - turn on Materials, so it writes a `.mtl` next to the `.obj`. It only writes a material's image if the image goes into a Principled BSDF's Base Color. Maps from older Blender versions often use a Diffuse BSDF instead, and then the `.mtl` has no `map_Kd` lines. Swap each Diffuse BSDF for a Principled BSDF with the image in its Base Color before exporting.
   - leave the rest as it is: the object names (`spawn`, `pit…`) go into the `.obj` as they are
5. **Put the images in the folder too**, and make the `.mtl` point at them there. Blender writes the path each image had when it was exported. Edit each `map_Kd` line to just the file name (or a path inside the folder, such as `textures/floor.png`). The folder is then the whole level source, with nothing outside it:

   ```
   level_src/tide_ruins/tide_ruins.obj
   level_src/tide_ruins/tide_ruins.mtl
   level_src/tide_ruins/grass.png
   level_src/tide_ruins/rock.png
   ...
   ```

   The folder must hold exactly one `.obj`. The files in it can have any names.
6. **Build the level.** From the project directory, run:

   ```
   python tools/build_level.py level_src/tide_ruins
   ```

   It writes `build/levels/tide_ruins` (the `.nsd` and `.nsf`), named after the folder. Add a name to save it as something else (`python tools/build_level.py level_src/tide_ruins other_name`). It prints `wrote …` when it's done. It also takes a `.obj` instead of a folder, and names the level after the file.
   - If the route runs along X in Blender, add `--turn 90` (or `--turn 270` if Crash ends up facing backwards).
   - If the map isn't modelled at 1 m to a Blender unit, or Crash looks too big or small in it, add `--scale <units per m>` (the default is 400). If the map is too wide or too tall for the game at that scale, the tool says so and gives the largest scale that fits.
   - A warning that a `.mtl` or image wasn't found means those faces get N. Sanity Beach's textures instead. Check the paths in the `.mtl`.
   - Once the turn and scale look right, save them in a `level.cfg` in the level source's folder, so the level always builds the same without the flags. `--turn` and `--scale` on the command line still override it. It holds one setting a line, and lines starting with `#` are comments:

     ```
     # the route runs along blender's +y, modelled at 1 m to a unit, so the defaults suit it
     turn = 0
     scale = 400
     ```

     That's `level_src/tide_ruins/level.cfg`. Its values are the defaults, so it builds the same without it; it's there as an example. A map whose route runs along X, modelled at a different size, would have something like `turn = 90` and `scale = 2000`.

     A setting other than `turn` or `scale`, or a value that isn't a whole number, stops the tool with a message naming the line.
7. **Setup which level to boot into** In `settings.cfg`:

   ```
   boot_level = tide_ruins
   ```
8. **Run the game** (`build/c1.exe`). It starts in your level. Crash runs with the camera behind him, looking along the route. If the level named in `boot_level` doesn't exist, the game says so in the console and starts normally. Remove `boot_level` to start at the title screen again.

Levels are built from your copy of the game, so they go in `build/`, which is ignored by git (and emptied by `make clean`; build them again afterwards). `level_src/` is ignored too, apart from the included `tide_ruins` source and `level_src/README.md`.

To change the level, edit the map in Blender, export over the old files, and run step 6 again. `settings.cfg` doesn't need changing, and you don't need to rebuild the game.

### If you only have an .obj

Make a folder in `level_src/` for it, such as `level_src/tide_ruins/`, and start at step 5. The `.obj` should have Y up, with the route running towards -Z in the file, which is what Blender's default export gives. Without a `.mtl`, the map uses N. Sanity Beach's textures. If it comes out on its side or facing the wrong way, re-export it from Blender with the default axes, or use `--turn`.

### Objects

Objects go in an `objects.json` in the level source's folder, next to the `.obj`. It's a list of objects, each with a `kind` and where it is in Blender (`at`, as `[x, y, z]` in metres, which is what Blender's N panel shows as an object's Location). For example:

```json
[
  {"kind": "spawn", "at": [0.5, 3.5, 0.3]},
  {"kind": "box", "type": "basic", "at": [7.5, 25.5, 0.7]},
  {"kind": "box", "type": "basic", "at": [-9.5, 35.5, 0], "stack": 3},
  {"kind": "end", "at": [0, 50, 1.2], "raise": 0.15}
]
```

That's part of `level_src/tide_ruins/objects.json`, which also has a row of one box of each type across the route just after the start.

(`tide_ruins` also has a `spawn` object in its `.obj`, from before `objects.json`, at the same place. The `spawn` in `objects.json` is the one used.)

| Kind | What it does |
|---|---|
| `spawn` | Crash starts on the ground below it. It takes the place of a `spawn` object in the map (see [Modelling](#modelling)). |
| `end` | N. Sanity Beach's warp pad goes on the ground below it. Crash stepping on it ends the level. |
| `box` | A box goes on the ground below it: a copy of one of N. Sanity Beach's, by its `type`. With `stack`, that many boxes go one on top of another. |

In the game's own levels, the warp pad object (`WarpC`) is only the animated part: the stone base it stands on is part of the level's terrain, about 3 m across and sunk 1 m into the ground with its top level with the floor. So for an `end`, the build also copies that base out of N. Sanity Beach's terrain (from your copy of the game, like its textures) and puts it under the pad, centred on it with its top on the floor. It only shows; Crash walks on the floor under it, so the floor there should be flat, about 3 m across.

An object can also have `raise`, in metres, to put it that far above the ground it goes on, such as when the warp pad clips into the floor around it. The floor Crash stands on is made of 0.3 m steps (see [Limits](#limits)), so it can be a little above or below the floor you see, and raising by 0.1 to 0.2 m usually covers it.

A box's `type` is which of the game's boxes it is. A custom level can have the boxes N. Sanity Beach has, named here by how they look in the game:

| `type` | Looks like | `subtype` |
|---|---|---|
| `basic` | a wooden crate with an X on it | 2 |
| `arrow` | a wooden crate with an up arrow | 3 |
| `checkpoint` | a wooden crate with a C | 4 |
| `iron` | a plain metal crate | 5 |
| `slatted` | a crate of wooden slats | 6 |
| `switch` | a metal crate with a ! | 7 |
| `life` | a wooden crate with Crash's face | 8 |
| `aku_aku` | a wooden crate with Aku Aku's mask | 9 |
| `question` | a wooden crate with a ? | 10 |
| `outline` | only the crate's edges, until a `switch` makes it solid | 13 |

`subtype` is the game's own number for it, which a box can have instead of `type`. Other boxes, such as TNT, aren't on the beach, and the other subtypes either crash the game (0, 1, 11, 12 and 15) or aren't boxes (14), so a custom level can't have them yet. `tide_ruins` has one of each, in the order above from left to right, in a row just after the start.

`stack` (1 by default) is how many boxes high it is. The game stacks a box on another when it's 400 units (1 m at the default scale) above it, at the same place, and comes straight after it in the level, which is how a stack is built.

A level can have one `spawn` and one `end`, and neither is needed, and any number of boxes, up to about 300 objects in all (the game has 304 places to keep track of objects, by their ids). "On the ground below it" means the highest floor below `at`, or less than 0.3 m (at the default scale) above it, so `at` can be on the floor itself. If there's no floor there, the build stops and says so.

`objects.json` is read every time the level is built, so after changing it, run step 6 again. If it isn't valid (not JSON, an unknown `kind` or setting, a second `spawn` or `end`, `at` that isn't three numbers, `raise` that isn't a number, a box `type` or `subtype` the beach doesn't have, or both or neither of them, or a `stack` that isn't a whole number of at least 1), the build stops with a message saying which object is wrong.

### Modelling

- Model the route so Crash runs towards +Y (forward in Blender's front view, away from you). The camera follows him from behind along that direction. It also slides sideways after him and keeps the same height above the floor he's on (a camera mode c1x adds for custom levels), so he can take paths that run beside each other, such as several walkways, and climb onto higher floors or drop to lower ones without leaving the view. It rises when he lands somewhere higher, not with each jump, and follows him straight down when he drops. It doesn't turn, so the route as a whole should run straight.
- 1 m is 400 of the game's units; Crash is about 1.7 m tall. Use `--scale <units per m>` for another scale.
- Faces have to point towards where Crash can be (normals out of the walkable side; Blender's Face Orientation overlay shows them blue). Faces pointing up are floors, the rest are walls. Faces pointing down, such as ceilings, are left out, so the camera can see in from above. So are walls facing away from the camera (towards -Y in Blender, the way the route runs), as it always looks that way and never sees them; they're still solid.
- Name an object `spawn` (it can be any small mesh) to put Crash on the floor below it, or use a `spawn` in [`objects.json`](#objects). Without either, he starts down the middle of the map, at the beginning of the longest stretch of floor he can walk along the route. Each step can go up or down at most 128 units (about 0.3 m at the default scale), so a ledge or a building he can't get past doesn't count. He starts far enough along that stretch for the camera behind him to be over it too.
- Name objects `pit…` (e.g. `pit.001`) for floors that kill Crash when he lands on them.

### Textures

- Each material's image (its Base Color texture, `map_Kd` in the `.mtl`) goes on its faces. It's shrunk or scaled up to 64 x 64 pixels with 16 colours, as the game's own textures are.
- The game can't use Blender's UVs: an image covers 1024 units (2.6 m) of a face and repeats, lined up with the zone, on floors from above and on walls upright.
- Faces whose material has no image get N. Sanity Beach's sand (floors) or another of its textures (walls).
- Faces are shaded by which way they face.
- Up to 93 materials can have images.
- The game puts each part of a texture on a triangle by its corners, so a face that isn't a rectangle lined up with the 2.6 m grid shows its texture a little stretched.

### Limits

- Collision is made of 128 unit cubes (about 30 cm), so a slope is a staircase of small steps. Crash walks up steps of up to about 240 units (0.6 m); anything higher he has to jump.
- A wall hanging over a floor, such as the top of a doorway, isn't solid: the game would treat it as a wall all the way down.
- Along the route, the map can be any length. A level is made of zones, as the game's own levels are, and the game's collision can't reach further than 16,384 units in one zone. So a longer map is split into a chain of zones, each 16,384 units long, that lead on to each other.
- Across and up, the map has to fit in one zone: at most 16,384 units, including a margin of 128 at each side (about 40 m at the default scale).
- On a long map, each zone can have at most 4 world meshes, because a zone also draws the next zone's meshes as the camera looks ahead into it. A zone that needs more is an error; use fewer faces there.
- The game draws at most 4095 polygons of a custom level at once (its own levels draw 1460), and faces are cut into pieces about 1.3 m long along the route and 2.6 m across, so a big, detailed map leaves out what's farthest from the camera. `tide_ruins` is drawn about 28 m ahead.
- The game has no depth test for level geometry: it draws faces farthest first, by the middle of each piece along the route. Where two big faces overlap at about the same distance, one can show through the other a little.
