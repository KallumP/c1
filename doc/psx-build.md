# PS1 build

As of 30 October 2026, c1x no longer supports building for the PS1.

c1x contained the code for a PS1 build alongside the PC one, selected with the `PSX` flag (`#ifdef PSX` branches, and `src/psx/` with the original's annotated assembly in `r3000a.s`). It couldn't be compiled for the PS1 the way the original game was: every shared source file failed with a compiler of the era, for the reasons below. So the `PSX` flag and PS1-specific code were removed. This page records what was tried and why it failed.

The last version with the PS1 code is tagged `psx-last`. File names and examples below refer to that version.

## What was tried

The original game was built with Psy-Q, Sony's PS1 SDK, whose C compiler is a version of GCC from around 1996. The check uses the community's rebuilds of those compilers ([decompals/old-gcc](https://github.com/decompals/old-gcc): `gcc-2.6.3-psx` and `gcc-2.7.2-psx`), the same tools matching-decompilation projects use, and runs them in Docker:

- a modern `cpp` for preprocessing, since c1x's headers use C99 variadic macros the old preprocessor can't read (preprocessing doesn't affect the generated code)
- the old `cc1` with Psy-Q-style options (`-O2 -G0 -mips1`)
- [maspsx](https://github.com/mkst/maspsx) and MIPS binutils to assemble the result
- empty stand-ins for the Psy-Q SDK headers (`LIBGTE.H`, `LIBGPU.H` and so on), which are proprietary and not in the repository, plus a header that defines `int8_t` to `uint64_t`, `size_t` and `NULL`

All 15 shared source files (`src/*.c`) fail. Most of the errors are in the compiler stage; `audio.c`, `gool.c` and `slst.c` don't get that far because of a missing include (see [Missing and misplaced files](#missing-and-misplaced-files)).

## Why it fails

In order of impact. The counts are compiler errors with GCC 2.7.2. Many are knock-on errors from an earlier one, so fixing the first few causes removes most of them.

### Unnamed struct and union members

About 1,890 errors (`union has no member named 'x'`, `structure has no member named ...`, `request for member ...`).

c1x's data structures use members without a name in two forms:

- **unnamed nested structs and unions** (119, mostly in `geom.h`, `ns.h` and `gool.h`). For example, `vec` in `geom.h` lets `v.x` reach into an unnamed struct:

  ```c
  typedef union {
    struct {
      int32_t x, y, z;
    };
    int32_t c[3];
  } vec;
  ```

- **typedef names used as members** (about 17, in `geom.h`, `gool.h`, `level.h`, `title.h`, `formats/gool.h` and `formats/zdat.h`). For example, `gool_object` in `gool.h` includes `gool_process;` so that `obj->size` reaches `obj->process.size`. This is GCC's Plan 9 extension, which the PC build turns on with `-fplan9-extensions`.

Unnamed members became standard in C11, and the Plan 9 form only exists in GCC 4.6 and later. The 1996 compilers reject both, and almost every source file accesses the game's objects, vectors and entries through them.

**To fix:** give every unnamed member a name and change every access that goes through it (for example `v.x` to `v.p.x` and `obj->size` to `obj->process.size`). This touches most of the game code, including the PC build's.

### Decompiler output in PS1-only code

PS1-only branches (`#ifdef PSX`) in `gfx.c` still contain output from the decompiler that never became C:

- 10 MSVC-style inline assembly blocks, e.g. in `GfxTransformFragment`:

  ```c
  __asm {
    mtc2    $a2, $0
  ```

- 16 lines that use the decompiler's register pseudo-variables, e.g. `_$T6 = 0;` and `_$A2 = (bound->p2.y << 16) | bound->p1.x;`
- `__fastcall` on 3 functions (`sub_8001A5F4`, `sub_8001A754`, `sub_8001A850`)

No GCC accepts these. They cause the `parse error before '$'`, `initializer element is not constant`, `redefinition of ...` and `variable-size type` errors in `gfx.c`, because the compiler loses track of the function body.

**To fix:** rewrite those functions in C (or as GCC inline assembly, or move them to `src/psx/r3000a.s`).

### Newer C syntax

- **Flexible array members**, e.g. `uint8_t data[];` in `ns.h` (15 in 10 headers, 140 errors): C99. The compilers of the era only accept GCC's `data[0]`, which has the same layout.
- **Binary literals**, e.g. `0b00000000000011111111000000000000,` in `solid.c` (32, `nondigits in number`): a GCC extension from 4.3, standard only in C23. They can be written in hex.
- **Designated initializers into unnamed members**, e.g. `rect216 tpage_rect = { .x=0,.y=0,.w=256,.h=128 };` in `ns.c` (`unknown field`): fixed along with the unnamed members.
- **Variadic macros** (`...`) in `geom.h`: C99. The check works around this by preprocessing with a modern `cpp`; the original `cpp` rejects them.

### Missing and misplaced files

- `src/psx/r3000a.h` includes `"zdat.h"`, but the file is `src/formats/zdat.h`, so `audio.c`, `gool.c` and `slst.c` stop at the preprocessor.
- `src/main.c` includes `"psx/init.h"`, which doesn't exist (there is only `src/psx/init.c`).
- With `PSX` defined, `common.h` includes no standard headers, so `int32_t`, `uint8_t`, `size_t` and `NULL` are undefined. Psy-Q's C library headers don't define the `<stdint.h>` types either, so the PS1 build needs its own definitions.
- `gool.c` includes `<LIBGTE.h>`, while the other files use `<LIBGTE.H>`. These are the same file on Windows but not on a case-sensitive file system.

### Errors in PS1-only code

Code that only the PS1 build compiles has mistakes the PC build never sees:

- undeclared names, e.g. `TransMatrix(&mn_cam_rot, t);` in `gfx.c` (the variable is `trans`) and `RGteTransformWorlds(poly_ids, ...)` in `gfx.c` (there's `cur_poly_ids`)
- prototypes that don't match: `GfxTransformFontChar` is declared `void` in `gfx.h` but the PS1 version in `gfx.c` returns `int`; `NSUpdate2` is declared as taking a `pgid_t` in `ns.h`, but defined and called with no arguments (`ns.c`, `level.c`)

### The Psy-Q SDK

The PS1 code uses the Psy-Q SDK's headers and libraries (`LIBGTE`, `LIBGPU`, `LIBSPU`, `LIBSND`, `LIBCD`, `LIBAPI`, `LIBPAD`), for types such as `DISPENV`, `RECT`, `POLY_FT4` and `POLY_GT4` and functions such as `RotTrans` and `SetGeomOffset`. They are proprietary and not part of the repository. With empty stand-ins they cause the remaining `parse error` and `undeclared` errors (e.g. in `src/psx/gpu.h`). A real build needs the SDK (or compatible headers that declare the same types), and linking needs its libraries.

## What bringing it back would take

Starting from the `psx-last` tag:

1. Name every unnamed struct and union member and update all accesses (the bulk of the work; changes PC code too).
2. Rewrite the decompiler leftovers in `gfx.c` as C or assembly.
3. Replace flexible array members with `[0]` and binary literals with hex.
4. Fix the `zdat.h` include, add `src/psx/init.h`, give the PS1 build its own `stdint`-style types, and fix the include spelling.
5. Fix the undeclared names and prototype mismatches in the PS1-only code.
6. Build against the Psy-Q SDK headers and link with its libraries.

Even then, c1x is a functional decompilation: it was written to behave like the original, not to compile to the same instructions, so a successful build would differ from the original executable in its instruction order and register use.
