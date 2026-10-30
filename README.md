# C1

This is a port of the game *Crash Bandicoot* to C.

The code was designed to compile for both psx and pc. As of 30 October 2026, this fork no longer supports building for the PS1 and only builds for pc; see [PS1 build](doc/psx-build.md) for why.

This repository is a fork of [wurlyfox/c1](https://github.com/wurlyfox/c1), the original port by wurlyfox (with contributions from others, such as ManDude). The port itself, and the reverse engineering behind it, is their work.

## Status

- Code - 100% ported
- Functionality - 78%

At the moment the game is only partially playable with a number of currently identified [issues](doc/issues.md).

## Documentation

- [Building](doc/building.md): dependencies, compiling on Linux and Windows, and running the tests
- [PS1 build](doc/psx-build.md): why building for the PS1 is no longer supported, and what bringing it back would take
- [Running](doc/running.md): getting the game files from your disc or a disc image, and starting the game
- [Controls](doc/controls.md): the default keys and changing them with `controls.cfg`
- [Settings](doc/settings.md): game settings in `settings.cfg`, such as the loading screen, speed display and skipping the splash screens
- [Custom levels](doc/custom_levels.md): booting into a level from `custom_levels/`, and making levels with `tools/nslevel.py`
- [Structure](doc/structure.md): what each file and directory in the project is for
- [Contributing](doc/contributing.md): commit messages, pull requests and coding standards

Further documentation, such as the [changelog](doc/changelog.md), known [issues](doc/issues.md) and descriptions of the game's files and functions, is in the [`doc`](doc) directory.
