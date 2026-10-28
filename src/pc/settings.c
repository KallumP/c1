/*
 * game settings (pc), read from settings.cfg
 */
#include <SDL2/SDL.h>
#include "settings.h"
#include "config.h"

pc_settings game_settings = {
  .loading_screen = 1,
  .loading_screen_min_ms = 2000
};

/* restore the default settings */
void SettingsReset(pc_settings *s) {
  s->loading_screen = 1;
  s->loading_screen_min_ms = 2000;
}

/* parse "on"/"off" into flag; returns 0 for any other value */
static int SettingsParseOnOff(const char *value, int *flag) {
  if (SDL_strcasecmp(value, "on") == 0) { *flag = 1; return 1; }
  if (SDL_strcasecmp(value, "off") == 0) { *flag = 0; return 1; }
  return 0;
}

/* parse a whole number from 0 to max into num; returns 0 if it isn't one */
static int SettingsParseNumber(const char *value, uint32_t max, uint32_t *num) {
  uint32_t n;

  if (*value == 0) { return 0; }
  for (n=0;*value;value++) {
    if (*value < '0' || *value > '9') { return 0; }
    n = (n*10) + (*value - '0');
    if (n > max) { return 0; }
  }
  *num = n;
  return 1;
}

/* apply one setting; returns 1, or -1 if the name or value is invalid */
static int SettingsApply(const char *name, const char *value, pc_settings *s) {
  if (SDL_strcasecmp(name, "loading_screen") == 0)
    return SettingsParseOnOff(value, &s->loading_screen) ? 1 : -1;
  if (SDL_strcasecmp(name, "loading_screen_min_ms") == 0)
    return SettingsParseNumber(value, SETTINGS_LOADING_SCREEN_MAX_MS,
      &s->loading_screen_min_ms) ? 1 : -1;
  return -1;
}

/*
 * parse one line of a settings file, in the form "name = value", into s.
 * returns 1 if a setting was applied, 0 for a blank or comment line,
 * and -1 for an invalid line (s is left unchanged).
 */
int SettingsParseLine(const char *line, pc_settings *s) {
  char buf[128], *name, *value;
  int res;

  res = ConfigParseLine(line, buf, sizeof(buf), &name, &value);
  if (res != 1) { return res; }
  return SettingsApply(name, value, s);
}
