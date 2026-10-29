# Controls

The default key bindings are below. To change them, create a `controls.cfg` (see [Changing the controls](#changing-the-controls)).

- X - <kbd>Z</kbd>
- square - <kbd>X</kbd>
- circle - <kbd>C</kbd>
- triangle - <kbd>S</kbd>
- L1 - <kbd>A</kbd>
- R1 - <kbd>D</kbd>
- L2 - <kbd>Q</kbd>
- R2 - <kbd>E</kbd>
- L3 - <kbd>1</kbd>
- R3 - <kbd>3</kbd>
- d-pad up - <kbd>&#8593;</kbd>
- d-pad down - <kbd>&#8595;</kbd>
- d-pad left - <kbd>&#8592;</kbd>
- d-pad right - <kbd>&#8594;</kbd>
- start - <kbd>Enter</kbd>
- select - <kbd>Space</kbd>
- toggle in-game GUI - <kbd>Esc</kbd>
- toggle in-game GUI keyboard focus - <kbd>Tab</kbd>

Only keyboard input is supported, and only for player 1.

## Changing the controls

Key bindings are read from `controls.cfg` when the game starts, so they can be changed without recompiling; just restart the game. To make one, copy [`controls.example.cfg`](../controls.example.cfg) (which lists the defaults) to `controls.cfg` in the same directory and edit the copy. The game looks for `controls.cfg` in the same directory as `streams/`. It is ignored by git, so your layout stays local. Each line binds a PlayStation button to a key:

```
cross    = Z
triangle = Left Shift
up       = Keypad 8
```

- **Buttons:** `cross`, `square`, `circle`, `triangle`, `l1`, `r1`, `l2`, `r2`, `l3`, `r3`, `up`, `down`, `left`, `right`, `start`, `select`.
- **Keys** use [SDL scancode names](https://wiki.libsdl.org/SDL2/SDL_Scancode) (the names, not the `SDL_SCANCODE_` constants), e.g. `Z`, `Space`, `Return`, `Left Shift`, `Left Ctrl`, `Keypad 8`, `F1`. Names are not case-sensitive. Keys are matched by their position on the keyboard, so on a non-QWERTY layout `Z` means the key where Z is on a US keyboard.
- **Several keys for one button:** repeat the button's line. The first line for a button replaces its default key; later lines add more.
- **Defaults:** a button that isn't listed keeps its default key, and if `controls.cfg` is missing all buttons use the defaults above (built into `src/pc/pad.c`).
- **Mistakes:** an invalid line (an unknown button or key name, or a line without `=`) is skipped with a warning naming the line, e.g. `controls.cfg:12: invalid binding, expected "button = key name"`. Lines starting with `#` are comments. `make test` also checks your `controls.cfg` for invalid lines.
- Avoid <kbd>Esc</kbd> and <kbd>Tab</kbd>, which the in-game GUI uses.
