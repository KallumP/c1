#include "utest.h"
#include <SDL2/SDL.h>
#include "pc/time.h"

UTEST(time, fixed_clock_does_not_move_on_its_own) {
  TimeSetFixed(1);
  SetTicksElapsed(100);
  SDL_Delay(20);
  ASSERT_EQ(100, GetTicksElapsed());
  TimeSetFixed(0);
}

UTEST(time, fixed_clock_advances_when_told) {
  TimeSetFixed(1);
  SetTicksElapsed(100);
  TimeAdvance(34);
  ASSERT_EQ(134, GetTicksElapsed());
  TimeAdvance(34);
  ASSERT_EQ(168, GetTicksElapsed());
  TimeSetFixed(0);
}

UTEST(time, real_clock_carries_on_from_the_fixed_one) {
  int ticks;

  TimeSetFixed(1);
  SetTicksElapsed(5000);
  TimeSetFixed(0);
  ticks = GetTicksElapsed();
  ASSERT_GE(ticks, 5000);
  ASSERT_LT(ticks, 5100);
}

UTEST(time, waiting_a_frame_moves_the_fixed_clock_on_one_frame) {
  uint32_t start_ms;

  TimeSetFixed(1);
  SetTicksElapsed(100);
  TimeWaitFrame(34);
  start_ms = SDL_GetTicks();
  TimeWaitFrame(34);
  ASSERT_EQ(168, GetTicksElapsed());
  ASSERT_GE(SDL_GetTicks() - start_ms, 25u); /* 34 ticks is about 33ms */
  TimeSetFixed(0);
}

UTEST(time, faster_speed_waits_less_but_moves_a_whole_frame) {
  uint32_t start_ms;

  TimeSetFixed(1);
  SetTicksElapsed(100);
  TimeSetSpeed(4);
  TimeWaitFrame(34);
  start_ms = SDL_GetTicks();
  TimeWaitFrame(34);
  ASSERT_EQ(168, GetTicksElapsed());
  ASSERT_LT(SDL_GetTicks() - start_ms, 20u); /* about 8ms, not 33 */
  TimeSetSpeed(1);
  TimeSetFixed(0);
}

UTEST(time, speed_0_does_not_wait) {
  uint32_t start_ms;
  int i;

  TimeSetFixed(1);
  SetTicksElapsed(100);
  TimeSetSpeed(0);
  start_ms = SDL_GetTicks();
  for (i=0;i<10;i++)
    TimeWaitFrame(34);
  ASSERT_EQ(100 + 340, GetTicksElapsed());
  ASSERT_LT(SDL_GetTicks() - start_ms, 20u); /* 10 frames would be 330ms */
  TimeSetSpeed(1);
  TimeSetFixed(0);
}

UTEST(time, speed_is_normal_by_default) {
  ASSERT_EQ(1u, TimeGetSpeed());
}

/* 34 ticks a frame at about 30 frames a second: 34000000/32768 a second */
UTEST(time, counter_converts_to_ticks) {
  ASSERT_EQ(0, TimeTicksFromCount(0, 10000000));
  ASSERT_EQ(1037, TimeTicksFromCount(10000000, 10000000)); /* a second */
  ASSERT_EQ(1037, TimeTicksFromCount(3000000, 3000000)); /* at another frequency */
}

UTEST(time, counter_converts_long_after_the_machine_started) {
  /* 10 hours of a 10 MHz performance counter overflowed 1000000*count*34
     (int64) and gave negative ticks, so the first frame waited for hours */
  int64_t freq = 10000000;

  ASSERT_EQ(37353515, TimeTicksFromCount(36000LL*freq, freq)); /* 10 hours */
  ASSERT_EQ(2141486389, TimeTicksFromCount(2063889LL*freq, freq)); /* nearly 24 days */
}

UTEST(time, real_clock_starts_near_0) {
  /* ticks count from the game starting, not the machine, so they stay
     small and positive however long it has been up */
  int ticks;

  TimeSetFixed(0);
  ticks = TimeRealTicks();
  ASSERT_GE(ticks, 0);
  ASSERT_LT(ticks, 1037 * 60); /* within a minute of the tests starting */
}

UTEST(time, is_fixed_reports_the_mode) {
  TimeSetFixed(1);
  ASSERT_TRUE(TimeIsFixed());
  TimeSetFixed(0);
  ASSERT_FALSE(TimeIsFixed());
}
