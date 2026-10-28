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
