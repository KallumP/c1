#ifndef _PC_SETTINGS_H_
#define _PC_SETTINGS_H_

#include "common.h"

#define SETTINGS_LOADING_SCREEN_MAX_MS 60000
#define SETTINGS_REPLAY_SPEED_MAX      16
#define SETTINGS_BOOT_LEVEL_MAX        31

/* game settings (pc), read from settings.cfg */
typedef struct {
  int loading_screen;             /* show each level's loading screen */
  uint32_t loading_screen_min_ms; /* minimum time it is shown for */
  int speed_display;              /* show crash's speed in the top right */
  int skip_splash_screens;        /* boot straight to the main menu */
  int fix_model_draw_order;       /* depth test 3d models against each other */
  int replay_inputs;              /* replay the newest recording instead of recording */
  uint32_t replay_speed;          /* times normal speed, 0 = as fast as possible */
  char boot_level[SETTINGS_BOOT_LEVEL_MAX+1]; /* custom level to boot into, or "" */
} pc_settings;

extern pc_settings game_settings;

extern void SettingsReset(pc_settings *s);
extern int SettingsParseLine(const char *line, pc_settings *s);
extern int SettingsLoad(const char *path);

#endif /* _PC_SETTINGS_H_ */
