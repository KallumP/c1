/*
 * "name = value" config files (pc), shared by controls.cfg and settings.cfg
 */
#include <ctype.h>
#include "config.h"

/* strip leading and trailing whitespace from str in place */
static char *ConfigTrim(char *str) {
  char *end;

  while (isspace((unsigned char)*str)) { str++; }
  end = str + strlen(str);
  while (end > str && isspace((unsigned char)end[-1])) { end--; }
  *end = 0;
  return str;
}

/*
 * split one config file line, in the form "name = value", on its first '='.
 * line is copied into buf, and name and value are set to the trimmed halves.
 * returns 1 for a name/value pair, 0 for a blank or comment ('#') line,
 * and -1 for an invalid line (no '=' or an empty side).
 */
int ConfigParseLine(const char *line, char *buf, size_t size,
  char **name, char **value) {
  char *str, *sep;

  snprintf(buf, size, "%s", line);
  str = ConfigTrim(buf);
  if (*str == 0 || *str == '#') { return 0; }
  sep = strchr(str, '=');
  if (!sep) { return -1; }
  *sep = 0;
  *name = ConfigTrim(str);
  *value = ConfigTrim(sep+1);
  if (**name == 0 || **value == 0) { return -1; }
  return 1;
}

/*
 * read a config file line by line, calling handle for each name/value pair.
 * invalid lines (from ConfigParseLine or handle) are reported as
 * "path:line: invalid <what>, expected \"<expected>\"" and skipped.
 * returns the number of lines applied, or -1 if the file can't be opened.
 */
int ConfigLoad(const char *path, const char *what, const char *expected,
  config_line_t handle, void *data) {
  FILE *file;
  char line[128], buf[128], *name, *value;
  int res, line_num, applied;

  file = fopen(path, "rb");
  if (!file) { return -1; }
  applied = 0;
  for (line_num=1;fgets(line, sizeof(line), file);line_num++) {
    res = ConfigParseLine(line, buf, sizeof(buf), &name, &value);
    if (res == 1)
      res = (*handle)(name, value, path, line_num, data);
    if (res == -1) {
      fprintf(stderr, "%s:%d: invalid %s, expected \"%s\"\n",
        path, line_num, what, expected);
      continue;
    }
    applied += res;
  }
  fclose(file);
  return applied;
}
