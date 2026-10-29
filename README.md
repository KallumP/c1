# C1

This is a port of the game *Crash Bandicoot* to C.

The code is designed to compile for both psx and pc. At the moment only pc-specific code is working.

This repository is a fork of [wurlyfox/c1](https://github.com/wurlyfox/c1), the original port by wurlyfox (with contributions from others, such as ManDude). The port itself, and the reverse engineering behind it, is their work.

## Status

- Code - 100% ported
- Functionality - 78%

At the moment the game is only partially playable with a number of currently identified [issues](doc/issues.md).

## Documentation

- [Building](doc/building.md): dependencies, compiling on Linux and Windows, and running the tests
- [Running](doc/running.md): getting the game files from your disc or a disc image, and starting the game
- [Controls](doc/controls.md): the default keys and changing them with `controls.cfg`
- [Settings](doc/settings.md): game settings in `settings.cfg`, such as the loading screen, speed display and skipping the splash screens
- [Structure](doc/structure.md): what each file and directory in the project is for

## Contributing

Commit messages use [gitmoji](https://gitmoji.dev/): start the message with the emoji code that matches the change, followed by a short lowercase summary, e.g. `:sparkles: configurable controls` or `:bug: fix debug GUI node inserted under the wrong parent`. Pull requests are squash merged, so the PR title becomes the commit message on `master`.

Coding standards are in [`doc/coding.md`](doc/coding.md).
