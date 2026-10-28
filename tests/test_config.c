#include <string.h>
#include "utest.h"
#include "pc/config.h"

#define CONFIG_TEST_PATH "build/test_config.cfg"

/* write contents to the test config file */
static void write_file(const char *contents) {
  FILE *file;

  file = fopen(CONFIG_TEST_PATH, "wb");
  fputs(contents, file);
  fclose(file);
}

UTEST(config, splits_name_and_value) {
  char buf[128], *name, *value;

  ASSERT_EQ(1, ConfigParseLine("cross = Z", buf, sizeof(buf), &name, &value));
  ASSERT_STREQ("cross", name);
  ASSERT_STREQ("Z", value);
}

UTEST(config, trims_whitespace_and_line_endings) {
  char buf[128], *name, *value;

  ASSERT_EQ(1, ConfigParseLine("  loading_screen=on \t\r\n", buf, sizeof(buf), &name, &value));
  ASSERT_STREQ("loading_screen", name);
  ASSERT_STREQ("on", value);
}

UTEST(config, splits_on_first_equals) {
  char buf[128], *name, *value;

  ASSERT_EQ(1, ConfigParseLine("r2 = =", buf, sizeof(buf), &name, &value));
  ASSERT_STREQ("r2", name);
  ASSERT_STREQ("=", value);
}

UTEST(config, keeps_spaces_inside_value) {
  char buf[128], *name, *value;

  ASSERT_EQ(1, ConfigParseLine("l1 = Left Shift", buf, sizeof(buf), &name, &value));
  ASSERT_STREQ("Left Shift", value);
}

UTEST(config, blank_and_comment_lines_are_skipped) {
  char buf[128], *name, *value;

  ASSERT_EQ(0, ConfigParseLine("", buf, sizeof(buf), &name, &value));
  ASSERT_EQ(0, ConfigParseLine("  \r\n", buf, sizeof(buf), &name, &value));
  ASSERT_EQ(0, ConfigParseLine("# a = b", buf, sizeof(buf), &name, &value));
  ASSERT_EQ(0, ConfigParseLine("  # indented", buf, sizeof(buf), &name, &value));
}

UTEST(config, missing_parts_are_invalid) {
  char buf[128], *name, *value;

  ASSERT_EQ(-1, ConfigParseLine("cross Z", buf, sizeof(buf), &name, &value));
  ASSERT_EQ(-1, ConfigParseLine("cross =", buf, sizeof(buf), &name, &value));
  ASSERT_EQ(-1, ConfigParseLine("= Z", buf, sizeof(buf), &name, &value));
}

/* records the lines it is given; rejects names starting with "bad" */
typedef struct {
  int calls;
  int last_line_num;
  char last_name[32];
  char last_value[32];
} recorder;

static int record_line(char *name, char *value, const char *path,
  int line_num, void *data) {
  recorder *rec;

  rec = (recorder*)data;
  if (strncmp(name, "bad", 3) == 0) { return -1; }
  if (strncmp(name, "skip", 4) == 0) { return 0; }
  rec->calls++;
  rec->last_line_num = line_num;
  snprintf(rec->last_name, sizeof(rec->last_name), "%s", name);
  snprintf(rec->last_value, sizeof(rec->last_value), "%s", value);
  return 1;
}

UTEST(config, load_missing_file_returns_minus_one) {
  recorder rec;

  memset(&rec, 0, sizeof(rec));
  remove(CONFIG_TEST_PATH);
  ASSERT_EQ(-1, ConfigLoad(CONFIG_TEST_PATH, "setting", "name = value", record_line, &rec));
  ASSERT_EQ(0, rec.calls);
}

UTEST(config, load_passes_each_line_with_its_number) {
  recorder rec;

  memset(&rec, 0, sizeof(rec));
  write_file("# comment\r\n\r\nfirst = 1\r\nsecond = two words\r\n");
  ASSERT_EQ(2, ConfigLoad(CONFIG_TEST_PATH, "setting", "name = value", record_line, &rec));
  ASSERT_EQ(2, rec.calls);
  ASSERT_EQ(4, rec.last_line_num);
  ASSERT_STREQ("second", rec.last_name);
  ASSERT_STREQ("two words", rec.last_value);
}

UTEST(config, load_counts_only_applied_lines) {
  recorder rec;

  memset(&rec, 0, sizeof(rec));
  /* malformed line, handler-rejected line, handler-skipped line, good line */
  write_file("no equals\nbad = 1\nskip = 1\ngood = 1\n");
  ASSERT_EQ(1, ConfigLoad(CONFIG_TEST_PATH, "setting", "name = value", record_line, &rec));
  ASSERT_EQ(1, rec.calls);
  ASSERT_EQ(4, rec.last_line_num);
}
