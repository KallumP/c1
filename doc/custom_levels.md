# Custom levels

You can make a level with `tools/nslevel.py` and have the game boot straight into it.

## 1. Make the level

You need the game's files in `streams/` first (see [Running](running.md)). Then, from the project directory, run one of:

| Command | Makes |
|---|---|
| `python tools/nslevel.py course` | `custom_levels/course`: a short obstacle course with gaps, steps, crates, a checkpoint, two crabs and the warp pad at the end |
| `python tools/nslevel.py mock` | `custom_levels/mock`: a long flat floor with Crash on it |
| `python tools/nslevel.py copy 9 beach_copy` | `custom_levels/beach_copy`: a copy of N. Sanity Beach |
| `python tools/nslevel.py map maps/simple_afps_level.obj --turn 90` | `custom_levels/simple_afps_level`: a map modelled in Blender (see [below](#maps-from-blender)) |

Add a name to save it under a different one, e.g. `python tools/nslevel.py course my_course`.

## 2. Boot into it

In `settings.cfg`, set `boot_level` to the level's name, and turn off `replay_inputs` (a recording made from the title screen won't replay in a custom level):

```
boot_level = course
replay_inputs = off
```

Then run the game. It starts in the level instead of the title screen. Remove `boot_level` to start normally again.

## Notes

- Custom levels are made from your copy of the game, so `custom_levels/` is ignored by git.
- If the level named in `boot_level` doesn't exist, the game says so in the console and starts normally.

## Maps from Blender

`python tools/nslevel.py map <file.obj> [name]` makes a level from a map modelled in Blender: its faces become the level's geometry and collision, and Crash starts on it. There are no enemies, fruit or crates. [`maps/`](../maps) has an example.

In Blender:

- Model the route so Crash runs towards +Y (forward in Blender's front view, away from you). The camera follows him from behind along that direction only, at the X he starts at, so the route should run straight.
- 1 m is 400 of the game's units; Crash is about 1.7 m tall. Use `--scale <units per m>` for another scale.
- Faces have to point towards where Crash can be (normals out of the walkable side; Blender's Face Orientation overlay shows them blue). Faces pointing up are floors, the rest are walls. Faces pointing down, such as ceilings, are left out, so the camera can see in from above.
- Name an object `spawn` (it can be any small mesh) to put Crash on the floor below it. Without one he starts on the floor nearest the start of the route (the -Y end), in the middle.
- Name objects `pit…` (e.g. `pit.001`) for floors that kill Crash when he lands on them.

Export with File > Export > Wavefront (.obj), keeping the default axes (Forward -Z, Up Y). Materials, UVs and normals aren't used: floors get N. Sanity Beach's sand and walls another of its textures, shaded by which way they face.

If the route runs along X instead, add `--turn 90` (or 270) to turn the map a quarter about the up axis.

Limits:

- Collision is made of 128 unit cubes (about 30 cm), so a slope is a staircase of small steps. Crash walks up steps of up to about 240 units (0.6 m); anything higher he has to jump.
- A wall hanging over a floor, such as the top of a doorway, isn't solid: the game would treat it as a wall all the way down.
- Each side of the map can be at most about 32,700 units (80 m at the default scale).
- The game draws at most 1460 polygons at once, and faces are cut into pieces about 1.3 m long along the route and 2.6 m across, so a big, detailed map leaves out what's farthest from the camera.
