# Building

As of currently, compilation has only been tested on Ubuntu/Debian and on Windows (MSYS2 MinGW32). However, the game should build on any system with a working 32-bit GNU toolchain and other dependencies listed below.

Note that only 32-bit target executables are currently supported. If you are not already running a 32-bit OS, you will need multilib versions of gcc and g++ and 32-bit versions of the dependencies.

To compile c1x, install the dependencies listed below, `cd` into the main project directory, and run `make`.

## Dependencies

### pc
- gcc / binutils / glibc
- GNU make
- OpenGL 2.0 or higher
- SDL 2
- FluidSynth
- Dear ImGui / cimgui (embedded in project)
- g++ / libstdc++ (for ImGui compilation)

Ubuntu/Debian:

- 64-bit: `sudo apt install build-essential gcc-multilib g++-multilib libstdc++6:i386 libgl1-mesa-dev:i386 libsdl2-dev:i386 libfluidsynth-dev:i386`
- 32-bit: `sudo apt install build-essential libstdc++6 libgl1-mesa-dev libsdl2-dev libfluidsynth-dev`

Windows (MSYS2):

1. Install [MSYS2](https://www.msys2.org/) (e.g. `winget install MSYS2.MSYS2`).
2. From an MSYS2 shell: `pacman -S --needed make mingw-w64-i686-gcc mingw-w64-i686-SDL2 mingw-w64-i686-fluidsynth`
3. Open the **MSYS2 MINGW32** shell, `cd` into the project directory and run `make`. This produces `build/c1.exe` and copies the DLLs it needs next to it (see below). Alternatively, run `rebuild.bat` from the project directory (`rebuild.bat clean` for a full rebuild, `rebuild.bat test` for the tests), which runs `make` in the MINGW32 environment for you.
4. Run `build/c1.exe`, either from the project directory or by double-clicking it. The game looks for `streams/` in the working directory, then next to the executable, then in the directory above it.

`c1.exe` links dynamically against SDL2, FluidSynth (and its audio codec dependencies) and the GCC runtime. Windows only looks for DLLs next to the executable or on `PATH`, so outside the MINGW32 shell the game fails to start with an error such as *"libfluidsynth-3.dll was not found"*. To avoid this, the Windows build has an extra `dlls` step that runs after linking. It recursively follows `c1.exe`'s imports and copies each one found in the MinGW32 `bin` directory (currently 17 DLLs) into `build/`. To re-copy them on their own, run `make dlls`. The `build` directory is ignored by git, and `make clean` removes it. To run the game on another machine, copy the `build` directory with the `streams` directory beside it (or inside it), and your `controls.cfg` and `settings.cfg` (if you have them) next to `streams`.

### psx
As of 30 October 2026, c1x no longer supports building for the PS1, and the `PSX` flag and PS1-specific code have been removed (the last version with them is tagged `psx-last`). See [PS1 build](psx-build.md) for why.

## Tests

Run `make test` to build and run the unit tests in `tests/`. They use the [utest.h](https://github.com/sheredom/utest.h) single-header framework (vendored in `tests/`), build to `build/tests` (`build/tests.exe` on Windows) and only need SDL 2. Tests are plain C files in `tests/`; each `UTEST(group, name)` registers itself, so adding a file there is enough for `make test` to pick it up.

`tools/generate_level_terrain.py`, `tools/nslevel.py`, `tools/blendmap.py` and `tools/tpage.py`, which make [custom levels](custom_levels.md), have their own Python tests: `python -m unittest discover -s tools/tests`. They need [Pillow](https://pypi.org/project/pillow/) (`pip install pillow`) for map textures.
