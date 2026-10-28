/*
 * crash's speed display (pc)
 */
#include "speed.h"

/* integer square root (floor) */
static uint64_t SpeedSqrt(uint64_t n) {
  uint64_t x, y;

  if (n < 2) { return n; }
  x = n;
  y = (x + 1) / 2;
  while (y < x) { /* newton's method, converges from above */
    x = y;
    y = (x + n / x) / 2;
  }
  return x;
}

/*
 * horizontal (x/z) speed of a move from prev to cur over ticks, in the
 * game's speed units: velocity is in position units per 1024 ticks, and
 * the game's own unit for it is 4096 of those (e.g. terminal velocity
 * 0x2EE000 is 750). returns 0 if no time has passed.
 */
uint32_t SpeedMeasure(vec *prev, vec *cur, int32_t ticks) {
  int64_t dx, dz;
  uint64_t dist;

  if (ticks <= 0) { return 0; }
  dx = (int64_t)cur->x - prev->x;
  dz = (int64_t)cur->z - prev->z;
  dist = SpeedSqrt((uint64_t)(dx*dx) + (uint64_t)(dz*dz));
  return (uint32_t)((dist * 1024) / ((uint64_t)ticks * 4096));
}
