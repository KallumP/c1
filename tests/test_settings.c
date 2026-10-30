#include "utest.h"
#include "pc/settings.h"

UTEST(settings, defaults_show_loading_screen_for_2_seconds) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, s.loading_screen);
  ASSERT_EQ(2000u, s.loading_screen_min_ms);
}

UTEST(settings, loading_screen_on_and_off) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, SettingsParseLine("loading_screen = off", &s));
  ASSERT_EQ(0, s.loading_screen);
  ASSERT_EQ(1, SettingsParseLine("loading_screen = on", &s));
  ASSERT_EQ(1, s.loading_screen);
}

UTEST(settings, names_and_on_off_are_case_insensitive) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, SettingsParseLine("Loading_Screen = OFF", &s));
  ASSERT_EQ(0, s.loading_screen);
}

UTEST(settings, loading_screen_rejects_other_values) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(-1, SettingsParseLine("loading_screen = maybe", &s));
  ASSERT_EQ(1, s.loading_screen);
}

UTEST(settings, loading_screen_min_ms) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, SettingsParseLine("loading_screen_min_ms = 500", &s));
  ASSERT_EQ(500u, s.loading_screen_min_ms);
  ASSERT_EQ(1, SettingsParseLine("loading_screen_min_ms = 0", &s));
  ASSERT_EQ(0u, s.loading_screen_min_ms);
  ASSERT_EQ(1, SettingsParseLine("loading_screen_min_ms = 60000", &s));
  ASSERT_EQ(60000u, s.loading_screen_min_ms);
}

UTEST(settings, loading_screen_min_ms_rejects_bad_numbers) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(-1, SettingsParseLine("loading_screen_min_ms = 60001", &s));
  ASSERT_EQ(-1, SettingsParseLine("loading_screen_min_ms = -5", &s));
  ASSERT_EQ(-1, SettingsParseLine("loading_screen_min_ms = abc", &s));
  ASSERT_EQ(-1, SettingsParseLine("loading_screen_min_ms = 12abc", &s));
  ASSERT_EQ(-1, SettingsParseLine("loading_screen_min_ms = 99999999999", &s));
  ASSERT_EQ(2000u, s.loading_screen_min_ms);
}

UTEST(settings, unknown_name_is_invalid) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(-1, SettingsParseLine("fullscreen = on", &s));
}

UTEST(settings, blank_comment_and_malformed_lines) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(0, SettingsParseLine("", &s));
  ASSERT_EQ(0, SettingsParseLine("# loading_screen = off", &s));
  ASSERT_EQ(-1, SettingsParseLine("loading_screen off", &s));
  ASSERT_EQ(1, s.loading_screen);
}

#define SETTINGS_TEST_PATH "build/test_settings.cfg"

/* write contents to the test settings file */
static void write_settings(const char *contents) {
  FILE *file;

  file = fopen(SETTINGS_TEST_PATH, "wb");
  fputs(contents, file);
  fclose(file);
}

UTEST(settings, load_missing_file_keeps_defaults) {
  SettingsReset(&game_settings);
  remove(SETTINGS_TEST_PATH);
  ASSERT_EQ(-1, SettingsLoad(SETTINGS_TEST_PATH));
  ASSERT_EQ(1, game_settings.loading_screen);
  ASSERT_EQ(2000u, game_settings.loading_screen_min_ms);
}

UTEST(settings, load_applies_each_setting) {
  SettingsReset(&game_settings);
  write_settings("# settings\r\nloading_screen = off\r\nloading_screen_min_ms = 750\r\n");
  ASSERT_EQ(2, SettingsLoad(SETTINGS_TEST_PATH));
  ASSERT_EQ(0, game_settings.loading_screen);
  ASSERT_EQ(750u, game_settings.loading_screen_min_ms);
  SettingsReset(&game_settings);
}

UTEST(settings, load_skips_invalid_lines) {
  SettingsReset(&game_settings);
  write_settings("fullscreen = on\nloading_screen_min_ms = lots\nloading_screen = off\n");
  ASSERT_EQ(1, SettingsLoad(SETTINGS_TEST_PATH));
  ASSERT_EQ(0, game_settings.loading_screen);
  ASSERT_EQ(2000u, game_settings.loading_screen_min_ms);
  SettingsReset(&game_settings);
}

/* the example file documents the defaults, so it must match them */
UTEST(settings, example_settings_file_matches_defaults) {
  pc_settings defaults;

  SettingsReset(&defaults);
  SettingsReset(&game_settings);
  game_settings.loading_screen = !defaults.loading_screen; /* so a match proves it was read */
  game_settings.loading_screen_min_ms = defaults.loading_screen_min_ms + 1;
  game_settings.speed_display = !defaults.speed_display;
  game_settings.skip_splash_screens = !defaults.skip_splash_screens;
  game_settings.fix_model_draw_order = !defaults.fix_model_draw_order;
  game_settings.record_inputs = !defaults.record_inputs;
  game_settings.replay_inputs = !defaults.replay_inputs;
  /* run from the project root */
  ASSERT_EQ(7, SettingsLoad("settings.example.cfg"));
  ASSERT_EQ(defaults.loading_screen, game_settings.loading_screen);
  ASSERT_EQ(defaults.loading_screen_min_ms, game_settings.loading_screen_min_ms);
  ASSERT_EQ(defaults.speed_display, game_settings.speed_display);
  ASSERT_EQ(defaults.skip_splash_screens, game_settings.skip_splash_screens);
  ASSERT_EQ(defaults.fix_model_draw_order, game_settings.fix_model_draw_order);
  ASSERT_EQ(defaults.record_inputs, game_settings.record_inputs);
  ASSERT_EQ(defaults.replay_inputs, game_settings.replay_inputs);
  SettingsReset(&game_settings);
}

/*
 * settings.cfg is the player's own (untracked) settings. this only checks
 * for typos, and passes if there is no settings.cfg.
 */
UTEST(settings, local_settings_file_is_valid) {
  FILE *file;
  char line[128];
  pc_settings s;
  int line_num;

  file = fopen("settings.cfg", "rb");
  if (!file) { return; }
  SettingsReset(&s);
  for (line_num=1;fgets(line, sizeof(line), file);line_num++) {
    if (SettingsParseLine(line, &s) == -1)
      fprintf(stderr, "settings.cfg:%d: invalid setting: %s", line_num, line);
    EXPECT_NE(-1, SettingsParseLine(line, &s));
  }
  fclose(file);
}

UTEST(settings, speed_display_is_off_by_default) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(0, s.speed_display);
}

UTEST(settings, speed_display_on_and_off) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, SettingsParseLine("speed_display = on", &s));
  ASSERT_EQ(1, s.speed_display);
  ASSERT_EQ(1, SettingsParseLine("speed_display = off", &s));
  ASSERT_EQ(0, s.speed_display);
  ASSERT_EQ(-1, SettingsParseLine("speed_display = fast", &s));
  ASSERT_EQ(0, s.speed_display);
}

UTEST(settings, skip_splash_screens_is_off_by_default) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(0, s.skip_splash_screens);
}

UTEST(settings, skip_splash_screens_on_and_off) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, SettingsParseLine("skip_splash_screens = on", &s));
  ASSERT_EQ(1, s.skip_splash_screens);
  ASSERT_EQ(1, SettingsParseLine("skip_splash_screens = off", &s));
  ASSERT_EQ(0, s.skip_splash_screens);
  ASSERT_EQ(-1, SettingsParseLine("skip_splash_screens = yes", &s));
  ASSERT_EQ(0, s.skip_splash_screens);
}

UTEST(settings, fix_model_draw_order_is_off_by_default) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(0, s.fix_model_draw_order);
}

UTEST(settings, fix_model_draw_order_on_and_off) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, SettingsParseLine("fix_model_draw_order = off", &s));
  ASSERT_EQ(0, s.fix_model_draw_order);
  ASSERT_EQ(1, SettingsParseLine("fix_model_draw_order = on", &s));
  ASSERT_EQ(1, s.fix_model_draw_order);
  ASSERT_EQ(-1, SettingsParseLine("fix_model_draw_order = 1", &s));
  ASSERT_EQ(1, s.fix_model_draw_order);
}

UTEST(settings, record_inputs_is_off_by_default) {
  pc_settings s;

  s.record_inputs = 1;
  SettingsReset(&s);
  ASSERT_EQ(0, s.record_inputs);
}

UTEST(settings, record_inputs_on_and_off) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, SettingsParseLine("record_inputs = on", &s));
  ASSERT_EQ(1, s.record_inputs);
  ASSERT_EQ(1, SettingsParseLine("record_inputs = off", &s));
  ASSERT_EQ(0, s.record_inputs);
  ASSERT_EQ(-1, SettingsParseLine("record_inputs = yes", &s));
  ASSERT_EQ(0, s.record_inputs);
}

UTEST(settings, replay_speed_is_normal_by_default) {
  pc_settings s;

  s.replay_speed = 7;
  SettingsReset(&s);
  ASSERT_EQ(1u, s.replay_speed);
}

UTEST(settings, replay_speed_takes_0_to_16) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, SettingsParseLine("replay_speed = 4", &s));
  ASSERT_EQ(4u, s.replay_speed);
  ASSERT_EQ(1, SettingsParseLine("replay_speed = 0", &s));
  ASSERT_EQ(0u, s.replay_speed);
  ASSERT_EQ(1, SettingsParseLine("replay_speed = 16", &s));
  ASSERT_EQ(16u, s.replay_speed);
  ASSERT_EQ(-1, SettingsParseLine("replay_speed = 17", &s));
  ASSERT_EQ(-1, SettingsParseLine("replay_speed = fast", &s));
  ASSERT_EQ(16u, s.replay_speed);
}

UTEST(settings, replay_inputs_is_off_by_default) {
  pc_settings s;

  s.replay_inputs = 1;
  SettingsReset(&s);
  ASSERT_EQ(0, s.replay_inputs);
}

UTEST(settings, replay_inputs_on_and_off) {
  pc_settings s;

  SettingsReset(&s);
  ASSERT_EQ(1, SettingsParseLine("replay_inputs = on", &s));
  ASSERT_EQ(1, s.replay_inputs);
  ASSERT_EQ(1, SettingsParseLine("replay_inputs = off", &s));
  ASSERT_EQ(0, s.replay_inputs);
  ASSERT_EQ(-1, SettingsParseLine("replay_inputs = 1", &s));
  ASSERT_EQ(0, s.replay_inputs);
}
