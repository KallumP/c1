#include "utest.h"
#include "pc/speed.h"

/* one game speed unit per second is 4096 position units per 1024 ticks */
#define UNITS(n) ((n)*4096)

UTEST(speed, standing_still_is_zero) {
  vec prev = { .x=UNITS(5), .y=0, .z=UNITS(7) };
  vec cur = prev;

  ASSERT_EQ(0u, SpeedMeasure(&prev, &cur, 34));
}

UTEST(speed, moving_100_units_in_1024_ticks_is_100) {
  vec prev = { .x=0, .y=0, .z=0 };
  vec cur = { .x=UNITS(100), .y=0, .z=0 };

  ASSERT_EQ(100u, SpeedMeasure(&prev, &cur, 1024));
}

UTEST(speed, combines_x_and_z) {
  vec prev = { .x=0, .y=0, .z=0 };
  vec cur = { .x=UNITS(30), .y=0, .z=UNITS(-40) };

  ASSERT_EQ(50u, SpeedMeasure(&prev, &cur, 1024));
}

UTEST(speed, divides_by_elapsed_ticks) {
  vec prev = { .x=0, .y=0, .z=0 };
  vec cur = { .x=UNITS(50), .y=0, .z=0 };

  ASSERT_EQ(100u, SpeedMeasure(&prev, &cur, 512));
}

UTEST(speed, ignores_vertical_movement) {
  vec prev = { .x=0, .y=0, .z=0 };
  vec cur = { .x=0, .y=UNITS(200), .z=0 };

  ASSERT_EQ(0u, SpeedMeasure(&prev, &cur, 1024));
}

UTEST(speed, zero_ticks_is_zero) {
  vec prev = { .x=0, .y=0, .z=0 };
  vec cur = { .x=UNITS(10), .y=0, .z=0 };

  ASSERT_EQ(0u, SpeedMeasure(&prev, &cur, 0));
}

UTEST(speed, large_moves_do_not_overflow) {
  vec prev = { .x=-0x40000000, .y=0, .z=-0x40000000 };
  vec cur = { .x=0x3FFFFFFF, .y=0, .z=0x3FFFFFFF };

  /* sqrt(2)*0x7FFFFFFF / 4 per tick, over 1024 ticks */
  ASSERT_EQ(741455u, SpeedMeasure(&prev, &cur, 1024));
}
