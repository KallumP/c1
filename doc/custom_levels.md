# Custom levels

You can make a level with `tools/nslevel.py` and have the game boot straight into it.

## 1. Make the level

You need the game's files in `streams/` first (see [Running](running.md)). Then, from the project directory, run one of:

| Command | Makes |
|---|---|
| `python tools/nslevel.py course` | `custom_levels/course`: a short obstacle course with gaps, steps, crates, a checkpoint, two crabs and the warp pad at the end |
| `python tools/nslevel.py mock` | `custom_levels/mock`: a long flat floor with Crash on it |
| `python tools/nslevel.py copy 9 beach_copy` | `custom_levels/beach_copy`: a copy of N. Sanity Beach |

Add a name to save it under a different one, e.g. `python tools/nslevel.py course my_course`.

## 2. Boot into it

In `settings.cfg`, set `boot_level` to the level's name, and turn off `replay_inputs` (a recording made from the title screen won't replay in a custom level):

```
boot_level = course
replay_inputs = off
```

Then run the game. It starts in the level instead of the title screen. Remove `boot_level` to start normally again.

## Notes

- Custom levels are made from your copy of the game, so `custom_levels/` is ignored by git.
- If the level named in `boot_level` doesn't exist, the game says so in the console and starts normally.
