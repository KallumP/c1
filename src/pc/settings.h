#ifndef _PC_SETTINGS_H_
#define _PC_SETTINGS_H_

#include "common.h"

#define SETTINGS_LOADING_SCREEN_MAX_MS 60000

/* game settings (pc), read from settings.cfg */
typedef struct {
  int loading_screen;             /* show each level's loading screen */
  uint32_t loading_screen_min_ms; /* minimum time it is shown for */
} pc_settings;

extern pc_settings game_settings;

extern void SettingsReset(pc_settings *s);
extern int SettingsParseLine(const char *line, pc_settings *s);
extern int SettingsLoad(const char *path);

#endif /* _PC_SETTINGS_H_ */
