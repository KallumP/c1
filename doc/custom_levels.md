# Custom levels

A map modelled in Blender can become a level the game boots straight into: its faces become the level's geometry and collision, and Crash starts on it. There are no objects yet (eg: enemies, fruit or crates). Maps go in `maps/`, a folder each; like `custom_levels/`, it's ignored by git.

## From Blender to the game

1. **Get set up (once).** You need the game built (see [Building](building.md)), its files in `streams/` (see [Running](running.md)), Python 3, and [Pillow](https://pypi.org/project/pillow/) for textures (`pip install pillow`). Without Pillow, a map with no images still works.
2. **Get the map ready in Blender** (see [Modelling](#modelling) below): the route running towards +Y, faces pointing the right way, and optionally a `spawn` object and `pit` objects.
3. **Unpack textures** if they're packed in the `.blend`: File > External Data > Unpack Resources. That saves them as image files that the export can point at.
4. **Export** with File > Export > Wavefront (.obj) into a folder of the map's own, `maps/my_map/`:
   - keep the default axes (Forward -Z, Up Y)
   - turn on Materials, so it writes a `.mtl` next to the `.obj`. It only writes a material's image if the image goes into a Principled BSDF's Base Color. Maps from older Blender versions often use a Diffuse BSDF instead, and then the `.mtl` has no `map_Kd` lines. Swap each Diffuse BSDF for a Principled BSDF with the image in its Base Color before exporting.
   - leave the rest as it is: the object names (`spawn`, `pit…`) go into the `.obj` as they are
5. **Put the images in the folder too**, and make the `.mtl` point at them there. Blender writes the path each image had when it was exported. Edit each `map_Kd` line to just the file name (or a path inside the folder, such as `textures/floor.png`). The folder is then the whole map, with nothing outside it:

   ```
   maps/my_map/my_map.obj
   maps/my_map/my_map.mtl
   maps/my_map/floor.png
   maps/my_map/wall.png
   ```

   The folder must hold exactly one `.obj`. The files in it can have any names.
6. **Make the level.** From the project directory, run:

   ```
   python tools/generate_level_terrain.py maps/my_map
   ```

   It writes `custom_levels/my_map` (the `.nsd` and `.nsf`), named after the folder. Add a name to save it as something else (`python tools/generate_level_terrain.py maps/my_map other_name`). It prints `wrote …` when it's done. It also takes a `.obj` instead of a folder, and names the level after the file.
   - If the route runs along X in Blender, add `--turn 90` (or `--turn 270` if Crash ends up facing backwards).
   - If the map isn't modelled at 1 m to a Blender unit, or Crash looks too big or small in it, add `--scale <units per m>` (the default is 400). If the map is too wide or too tall for the game at that scale, the tool says so and gives the largest scale that fits.
   - A warning that a `.mtl` or image wasn't found means those faces get N. Sanity Beach's textures instead. Check the paths in the `.mtl`.
7. **Setup which level to boot into** In `settings.cfg`:

   ```
   boot_level = my_map
   ```
8. **Run the game** (`build/c1.exe`). It starts in your map. Crash runs with the camera behind him, looking along the route. If the level named in `boot_level` doesn't exist, the game says so in the console and starts normally. Remove `boot_level` to start at the title screen again.

Levels are made from your copy of the game, so `custom_levels/` is ignored by git, and so is `maps/`.

To change the map, edit it in Blender, export over the old files, and run step 6 again. `settings.cfg` doesn't need changing, and you don't need to rebuild the game.

### If you only have an .obj

Make a folder `maps/my_map/` for it and start at step 5. The `.obj` should have Y up, with the route running towards -Z in the file, which is what Blender's default export gives. Without a `.mtl`, the map uses N. Sanity Beach's textures. If it comes out on its side or facing the wrong way, re-export it from Blender with the default axes, or use `--turn`.

### Modelling

- Model the route so Crash runs towards +Y (forward in Blender's front view, away from you). The camera follows him from behind along that direction only, at the X he starts at, so the route should run straight.
- 1 m is 400 of the game's units; Crash is about 1.7 m tall. Use `--scale <units per m>` for another scale.
- Faces have to point towards where Crash can be (normals out of the walkable side; Blender's Face Orientation overlay shows them blue). Faces pointing up are floors, the rest are walls. Faces pointing down, such as ceilings, are left out, so the camera can see in from above.
- Name an object `spawn` (it can be any small mesh) to put Crash on the floor below it. Without one, he starts down the middle of the map, at the beginning of the longest stretch of floor he can walk along the route. Each step can go up or down at most 128 units (about 0.3 m at the default scale), so a ledge or a building he can't get past doesn't count. He starts far enough along that stretch for the camera behind him to be over it too.
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
- The game draws at most 1460 polygons at once, and faces are cut into pieces about 1.3 m long along the route and 2.6 m across, so a big, detailed map leaves out what's farthest from the camera.
- The game has no depth test for level geometry: it draws faces farthest first, by the middle of each piece along the route. Where two big faces overlap at about the same distance, one can show through the other a little.
