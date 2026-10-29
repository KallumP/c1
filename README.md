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

## Structure
Project structure is listed below, including descriptions for each file.

Note that further documentation can be found in the `doc` directory.
```
.
├── doc                      # documentation
│   ├── changelog.md         # project changelog
│   ├── issues.md            # project issues
│   ├── coding.md            # project coding standards
│   ├── settings.md          # settings.cfg settings and their defaults
│   ├── outline.md           # game outline
│   ├── funcs.md             # function descriptions
│   ├── files.md             # detailed file descriptions (incomplete)
│   └── memmap.xlsx          # memory map
├── src                      # source code
│   ├── formats              # entry [item] formats
│   │   ├── cvtx.h           # cvtx type entry item formats
│   │   ├── gool.h           # gool type entry item formats
│   │   ├── imag.h           # imag type entry item formats
│   │   ├── inst.h           # inst type entry item formats
│   │   ├── ipal.h           # ipal type entry item formats
│   │   ├── mdat.h           # mdat type entry item formats
│   │   ├── pbak.h           # pbak type entry item formats
│   │   ├── slst.h           # slst type entry item formats
│   │   ├── svtx.h           # svtx type entry item formats
│   │   ├── tgeo.h           # tgeo type entry item formats
│   │   ├── wgeo.h           # wgeo type entry item formats
│   │   └── zdat.h           # zdat type entry item formats
│   ├── pc                   # pc-specific code (non-inline)
│   │   ├── gfx              # pc graphics
│   │   │   ├── gl.c,h       # OpenGL backend (2D primitive rasterization)
│   │   │   ├── tex.c,h      # texture cache
│   │   │   ├── pixel.h      # ps1 5551 to rgba pixel conversion
│   │   │   └── pcgfx.h      # graphics primitives
│   │   │── sound            # pc sound
│   │   │   ├── audio.c,h    # audio/sfx backend
│   │   │   ├── midi.c,h     # midi backend
│   │   │   ├── util.c,h     # utility functions for SEQ/VAB conversion
│   │   │   └── formats      # audio and midi formats
│   │   │       ├── psx.h    # psx SEP, SEQ, VAB, and VAG formats
│   │   │       ├── sf2.h    # soundfont (sf2) format
│   │   │       └── smf.h    # standard midi format
│   │   │── init.c,h         # pc-specific initialization (incl. SDL)
│   │   │── math.c,h         # fixed point implementations of math functions
│   │   │── pad.c,h          # joypad emulation (keyboard bindings, controls.cfg loading)
│   │   │── config.c,h       # "name = value" file parsing shared by controls.cfg and settings.cfg
│   │   │── settings.c,h     # game settings (settings.cfg loading)
│   │   │── loading.c,h      # level loading screen image conversion and minimum display time
│   │   │── speed.c,h        # crash's speed measurement for the speed display
│   │   └── time.c,h         # tick counter
│   ├── psx                  # psx-specific code (non-inline)
│   │   ├── card.c,h         # memory card
│   │   ├── cdr.c,h          # cd-rom
│   │   ├── gpu.c,h          # gpu interface (2D primitive rasterization)
│   │   ├── init.c,h         # psx-specific initialization
│   │   ├── r3000a.s         # r3000a assembly code; includes all functions from the game that were originally written in assembly
│   │   ├── r3000a.c         # c equivalents of the code in r3000a.s; here for sake of readability
│   │   └── r3000a.h         # header for r3000a.s and r3000a.c
│   ├── common.h             # common includes, macros, and codes
│   ├── geom.h               # geometric primitives (point, vector, angle, rect, matrix etc.)
│   ├── globals.h            # GOOL globals
│   ├── audio.c,h            # audio engine
│   ├── cam.c,h              # camera engine
│   ├── gfx.c,h              # upper-level graphics code
│   ├── gool.c,h             # GOOL object engine
│   ├── level.c,h            # level state and zone functions
│   ├── main.c,h             # main function and game loop
│   ├── math.c,h             # misc math functions
│   ├── midi.c,h             # midi/seq engine
│   ├── misc.c,h             # per-frame updates for world shader parameters
│   ├── ns.c,h               # paging/entry subsystem
│   ├── pad.c,h              # joypad interface
│   ├── pbak.c,h             # demo playback
│   ├── slst.c,h             # polygon id sort lists
│   ├── solid.c,h            # solidity and collision detection and movement limiting
│   ├── title.c,h            # handles title screen loading, transition between title states, and drawing of title card backdrops
│   ├── util                 # utilities
│   │   ├── list.c,h         # generic linked list
│   │   └── tree.c,h         # generic tree
│   └── ext                  # extensions to original game code
│       ├── lib              # libraries
│       │   ├── gui.c        # minimal GUI library ([c]imgui thin wrapper)
│       │   ├── refl.c       # minimal type reflection library
│       │   └── cimgui       # cimgui and imgui
│       ├── gui.c,h          # in-game GUI
│       ├── refl.c,h         # game-specific type metadata
│       └── disgool.c,h      # GOOL disassembler
├── streams                  # game assets (.NSD/.NSF files)
├── tests                    # unit tests (make test)
│   ├── main.c               # test runner
│   ├── utest.h              # utest.h test framework (vendored)
│   ├── test_pad.c           # key state to joypad buttons
│   ├── test_pad_parse.c     # controls.cfg line parsing
│   ├── test_pad_config.c    # controls.cfg loading
│   ├── test_config.c        # shared "name = value" file parsing
│   ├── test_settings.c      # settings.cfg parsing and loading
│   ├── test_loading.c       # loading screen image conversion and timing
│   ├── test_gui.c           # in-game GUI tree node insertion and removal
│   ├── test_speed.c         # crash's speed measurement and tracking
│   └── test_sf2.c           # soundfont record struct sizes
├── tools                    # helper scripts
│   └── extract_streams.py   # extracts game assets from a disc image
├── controls.example.cfg     # example key bindings (copy to controls.cfg to change the controls)
├── settings.example.cfg     # example settings (copy to settings.cfg to change the settings)
├── Makefile                 # project makefile
└── README.md                # project overview; this file
```

## Contributing

Commit messages use [gitmoji](https://gitmoji.dev/): start the message with the emoji code that matches the change, followed by a short lowercase summary, e.g. `:sparkles: configurable controls` or `:bug: fix debug GUI node inserted under the wrong parent`. Pull requests are squash merged, so the PR title becomes the commit message on `master`.

Coding standards are in [`doc/coding.md`](doc/coding.md).
