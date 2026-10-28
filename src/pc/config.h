#ifndef _PC_CONFIG_H_
#define _PC_CONFIG_H_

#include "common.h"

/*
 * handler for one "name = value" line of a config file.
 * returns 1 if the line was applied, 0 if it was skipped (having reported
 * why), or -1 if it is invalid (ConfigLoad reports it)
 */
typedef int (*config_line_t)(char *name, char *value, const char *path,
  int line_num, void *data);

extern int ConfigParseLine(const char *line, char *buf, size_t size,
  char **name, char **value);
extern int ConfigLoad(const char *path, const char *what, const char *expected,
  config_line_t handle, void *data);

#endif /* _PC_CONFIG_H_ */
