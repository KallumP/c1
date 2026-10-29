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
