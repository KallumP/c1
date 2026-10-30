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

UTEST(time, is_fixed_reports_the_mode) {
  TimeSetFixed(1);
  ASSERT_TRUE(TimeIsFixed());
  TimeSetFixed(0);
  ASSERT_FALSE(TimeIsFixed());
}
