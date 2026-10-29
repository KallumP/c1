# Running

To run c1, `cd` into the main project directory and run `./c1` (`build/c1.exe` on Windows). See [building](building.md) for how to compile it.

Copies of the asset files from the Crash Bandicoot game disc are needed for the game to function. Asset files are the (.NSD/.NSF) files located in the `/S0`, `/S1`, `/S2`, and `/S3` directories, respectively. Each of these files must be copied from its respective `/S*` directory into the `/streams` directory. Additionally, after copying files to the `/streams` directory, they must renamed from the uppercase format `S00000%%.NS[F,D]` to the lowercase format `s00000%%.ns[f,d]`.

If you have a disc image (`.bin` or `.iso`) made from a copy of the game you own, rather than the disc itself, `tools/extract_streams.py` does all of the above in one step. It reads the image directly, including raw 2352-byte-sector `.bin` dumps that many tools cannot open:

```
python tools/extract_streams.py crash.bin
```

If an asset file is missing, the game shows a *"Could not open ./streams/…"* error naming the file and exits.

The game is hardcoded to boot into level `25` (aka. title sequence/main menu screen(s)). To choose a different boot level, redefine the `LID_BOOTLEVEL` constant in `common.h` and recompile.
