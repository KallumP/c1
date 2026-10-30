# Settings

Game settings are read from `settings.cfg` when the game starts, in the same `name = value` format as `controls.cfg`:

```
loading_screen = on
loading_screen_min_ms = 2000
```

To change them, copy [`settings.example.cfg`](../settings.example.cfg) to `settings.cfg` next to `streams/` and edit the copy; it is ignored by git. Each setting goes on its own line, and changes take effect the next time the game starts.

A setting left out of the file, or a missing `settings.cfg`, uses the default below. Invalid lines are skipped with a warning naming the line, e.g. `settings.cfg:2: invalid setting, expected "name = value"`, and `make test` checks your `settings.cfg` for them. Lines starting with `#` are comments.

| Setting | Values | Default | Effect |
|---|---|---|---|
| `loading_screen` | `on`, `off` | `on` | Show each level's loading screen while it loads. |
| `loading_screen_min_ms` | `0` to `60000` | `2000` | Keep the loading screen up for at least this many milliseconds. Levels load from disk much faster than from the PS1 CD, so without this it would only flash. `0` shows it only for as long as loading takes. |
| `speed_display` | `on`, `off` | `off` | Show how fast Crash is moving in the top right corner: the horizontal speed, then the signed speed along the x, y (up) and z axes. These are in the game's own speed units per second (the scale of its velocity values, where terminal falling speed is 750), measured from how far Crash actually moved each frame, so they read 0 against a wall. |
| `skip_splash_screens` | `on`, `off` | `off` | Skip the Sony, Universal and Naughty Dog screens when the game starts and go straight to the main menu. |
| `fix_model_draw_order` | `on`, `off` | `off` | Draw 3D models (Crash, crates, enemies) in front of or behind each other by their actual depth, so a model behind another can't be drawn over it. This is an enhancement over the original game, whose draw order sometimes draws one model over another that is in front of it (e.g. a crate over Crash); `off` keeps the original draw order. The level, sprites and HUD always use the original draw order. |
| `replay_inputs` | `on`, `off` | `off` | Play back the newest recording in `recorded_inputs/` (see [Recorded inputs](#recorded-inputs)) instead of recording this run: the game starts the same way and the recorded buttons are used instead of the keyboard, and `REPLAYING INPUTS` shows in the top right corner. At the end of the recording the keyboard takes over and `REPLAYING INPUTS` goes away. |
| `replay_speed` | `0` to `16` | `1` | How fast `replay_inputs` plays the recording back: this many times normal speed, or `0` for as fast as the computer can go (about 10 times normal speed). It plays out the same at any speed, and goes back to normal speed when the recording ends. Music runs at the same speed, and level loads take as long as they always do. |

## Recorded inputs

For reproducing bugs, every run records the buttons held each frame, from when the game starts until it closes, unless `replay_inputs` is on. Each run gets its own file in `recorded_inputs/` next to the executable (`build/recorded_inputs/` when built from source), named by when it started, e.g. `2026-10-30_14-05-09.inputs`, so nothing is overwritten. To replay an older run, delete or move the newer files, since replay plays the newest. Old recordings are never deleted for you; each is about 8 bytes per frame (about 15 KB a minute). `make clean` deletes `build/`, recordings included, so copy any you want to keep somewhere else first.

So that a replay plays out the same, game time moves exactly one frame (1/30 s) per frame drawn instead of following the real clock, in normal play as well as in replays. The game still runs at normal speed, but a slow frame makes game time fall behind rather than catch up. A recording only replays the same way with the same game data and the same `skip_splash_screens` setting, and in a build with the same boot level; if it gets out of step, the console says so.
