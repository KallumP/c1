# Maps

Maps modelled in Blender, for making [custom levels](../doc/custom_levels.md) with `python tools/generate_level_terrain.py maps/<map>`. Each map is a folder holding its `.obj`, `.mtl` and images.

| Map | Make it with | Source |
|---|---|---|
| `simple_afps_level/` | `python tools/generate_level_terrain.py maps/simple_afps_level --turn 90` | [Simple AFPS Level](https://opengameart.org/content/simple-afps-level) by drummyfish, [CC0](https://creativecommons.org/publicdomain/zero/1.0/). Changed: an object named `spawn` added on the main floor at the start of the right hand side, and `simple_afps_level.mtl` written for its three materials, with the textures packed in the original `level.blend` saved next to it. |
