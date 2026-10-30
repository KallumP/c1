# Changelog

## 2026-10-30

### Added

- `fix_model_draw_order` setting (default off): 3D models are depth tested against each other, so a model behind another (e.g. a crate behind Crash) can't be drawn over it, which the original game's draw order sometimes allows
- every run records the buttons held each frame to its own `.inputs` file in `build/recorded_inputs/`, for reproducing bugs; the `replay_inputs` setting (default off) plays the newest recording back instead, and `replay_speed` plays it back faster. Game time now moves exactly one frame per frame drawn, so that replays play out the same
- `boot_level` setting to boot straight into a level from `custom_levels/`, and `tools/nslevel.py` to make them: a copy of a real level, or levels built from scratch: a mock level (a flat floor, a follow camera and Crash) and an obstacle course (gaps, steps, boxes, a checkpoint, crabs and the warp pad)
- `python tools/nslevel.py map <file.obj>` makes a custom level from a map modelled in Blender and exported as `.obj`: its geometry and Crash, with no other objects. faces get their material's image as a texture (from the `.mtl`). `maps/` has an example, drummyfish's CC0 "Simple AFPS Level"

### Fixed

- landing on the warp pad at the end of a level skipped Crash's 'win level' animation and went straight to the level end screen
- fixed the gem briefly showing small in the top left of the level end screen before flying in, after a level with every box broken

## 2026-10-28

### Added

- Windows build support via MSYS2 MinGW32; `c1.exe` and the DLLs it needs are output to `build/`
- `streams/` is also found next to or one directory above the executable, so it no longer has to be run from the project directory
- `tools/extract_streams.py` for extracting asset files from a `.bin`/`.iso` disc image
- error message naming the missing file when an asset file cannot be opened
- key bindings are loaded from `controls.cfg` at startup, so they can be changed without recompiling; a button can have several keys. `controls.cfg` is ignored by git; `controls.example.cfg` lists the defaults to copy from
- Shift, Ctrl, Alt and other keys that could not be bound before can now be used (keys are tracked by SDL scancode)
- unit tests (`make test`) using utest.h
- game settings are loaded from `settings.cfg` at startup (ignored by git; `settings.example.cfg` lists the defaults): `loading_screen` turns the level loading screen on or off, and `loading_screen_min_ms` sets how long it stays up (default 2000)
- `speed_display` setting (default off) to show how fast Crash is moving in the top right corner, as a horizontal speed and per-axis (x, y, z) speeds
- `skip_splash_screens` setting (default off) to boot straight to the main menu, skipping the Sony, Universal and Naughty Dog screens

### Fixed

- build fails with GCC 15+ (C23 default); now builds as gnu17
- crash while loading the soundfont in 32-bit builds with FluidSynth 2.2+ (loader callback signatures did not match)
- no music on Windows: FluidSynth rejected the generated soundfont ("'pmod' chunk size is not a multiple of 10 bytes") because MinGW's bitfield layout made each SF2 modulator record 14 bytes instead of 10
- asset files were opened in text mode, which corrupts them on Windows
- README controls list did not match the actual key bindings
- game freezes while the in-game GUI shows the object tree: removing a node only moved its first child to the parent, leaving the rest pointing at the freed node
- game freezes while the in-game GUI shows the object tree: a node inserted after a sibling under a different parent was linked into that parent's children, corrupting the tree; it is now added last under its own parent
- level loading screen never appeared on pc: the image was not converted from its palette and the frame was never shown. It is now drawn and kept up for at least 2 seconds, since levels load from disk much faster than from the ps1 cd
- Crash drawn behind crates he is in front of, especially while jumping: his draw-order bias was dropped in the air (state flags masked with 0x18 instead of the original's 0x10), the object-below-Crash lookup read uninitialised values and treated an object as a floor node, and animated models were sorted by min/max vertex depth instead of the sum like the original

## 2022-12-28

### Fixed

- object shading inaccuracy
- press X icon at level win is scaled incorrectly
- hot pipe shading intensity appears to be inverted
- sound dies after collecting 3 aku aku and any level transitions thereafter cause the game to crash 
- map controls do not work
- (partial) attempting to enter any title state other than the map from the main menu ultimately results in the game entering an infinite loop and/or crashing
- issue with singular/plural text
- Papu Papu: staff does no damage to Crash
- Hog Wild: works fine up until a certain point in the level where it is not possible to veer away from the camera path

## 2022-12-27

### Fixed

- aku aku sparkle fragments do not appear
- aku aku mask does not appear/invincibility is not completely effective
- wumpa fruit is collected in 'groups' of 3 (and then 1 for a total of 10) instead of 1 at a time when the [top of the] player hits the bottom face of a bouncy wumpa fruit box after being launched upwards from an bounceable object
- returning from a bonus round brings you back to the map instead of a level
- Jungle Rollers: camera is not positioned correctly at the beginning of the level
- The Great Gate: camera does not adjust quickly enough when moving upward
- The Great Gate: bounceable fire pit never transitions to flame state

## 2022-12-26

### Fixed

- broken sfx code
- broken music/midi player code
- myriad of issues related to audio
- no initialization of gool globals at game init
- transparency/blending behavior is incorrect for some objects

### Added

- custom audio sampler and mixer implementation

### Removed

- SDL mixer dependency

### Other

- Sound effects and music are now working. Volume levels may not be completely accurate to the original game, however. Expect a fix for this in future updates.

## 2022-12-19

### Fixed

- flickering colors during intro sequence
- rot matrix calc errors
- some text does not render
- issues preventing level transitions
- more ripple shader inaccuracies
- fog shader inaccuracies
- lightning shader inaccuracies
- dark shader inaccuracies
- background color not visible in levels that have one
- animated textures do not animate
- some objects randomly respawn
- some object collisions do not register (namely collisions with wumpa fruit)
- some objects appear to not complete their paths
- pausing the game does not work correctly
- beach does not display in N. Sanity Beach
- boot level is N. Sanity Beach instead of title

### Added

- top and bottom screen borders present in original
- toggleable render of object bounds (press <key>q</key> to toggle)
- issue tracking document

### Removed

- patches code (no longer used)

## 2022-12-13

### Fixed

- (most) transparency has not been implemented
- (most) semi-transparency/blending behavior is inaccurate
- incorrect starting location for pickups when moving to hud

## 2022-12-12

### Fixed

- textures should not use anti-aliasing
- (partial) object phong shading is inaccurate
- (partial) transparency has not been implemented
- screen does not fade out/in after death/before respawn
- player does not inherit zone brightness levels
- (some) gool issues
- timing issue with gool animations
- no deceleration of player when jumping
- (partial) it is sometimes possible to jump in mid-air when beside walls
- auto-cam transition takes multiple button presses to skip
- (many) solidity check/collision issues
- ripple shader inaccuracies
- text is not rendered at the correct locations

### Removed

- vertex buffer based draw code
- gl extensions dependency

### Added

- immediate mode based draw code
- toggleable render of wall bitmap image (press <key>d</key> to toggle)

## 2022-12-7

### Fixed

- path traversing objects are not oriented correctly
- display list ordering of objects is incorrect
- object geometry outside of viewing frustum is not rejected as it should be

## 2022-11-24

### Fixed

- (some) solidity check/collision issues
- wumpa fruit and other icon-based sprites are at incorrect scale
- (partial) HUD fails to render
- camera lags behind player
- camera path selection at divergences is incorrect
- infinite loop in `GoolObjectSearchTree`
- segfault on exit

### Added

- changelog (this file)
- in-game GUI re-write using [c]imgui as backend (press <key>esc</key> to toggle)
  - GOOL object code debugger
- toggleable render of zone octree query results (press <key>a</key> to toggle)

### Removed

- old in-game GUI implementation
- freetype dependency

### Other

Audio SFX are still disabled by default as they are not working 100% correctly, however they can now be enabled with compilation flag `-DCFLAGS_SFX_FLUIDSYNTH`.
