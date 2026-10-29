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

/*
 * signed speed along one axis of a move from prev to cur over ticks, in the
 * same units as SpeedMeasure. returns 0 if no time has passed.
 */
int32_t SpeedAxis(int32_t prev, int32_t cur, int32_t ticks) {
  int64_t d;

  if (ticks <= 0) { return 0; }
  d = (int64_t)cur - prev;
  return (int32_t)((d * 1024) / ((int64_t)ticks * 4096));
}

/*
 * track obj's position from frame to frame and return its horizontal speed
 * this frame (see SpeedMeasure), also recording its speed along each axis in
 * t->x, t->y and t->z. tracking restarts, with every speed 0, when obj
 * changes or is 0 (e.g. not in play), and when it jumps further than
 * SPEED_TELEPORT allows horizontally or vertically (e.g. respawning).
 */
uint32_t SpeedTrack(speed_tracker *t, void *obj, vec *trans, int32_t ticks) {
  uint32_t speed;

  t->x = 0; t->y = 0; t->z = 0;
  if (!obj) {
    t->obj = 0;
    return 0;
  }
  if (obj != t->obj) {
    t->obj = obj;
    t->prev = *trans;
    return 0;
  }
  speed = SpeedMeasure(&t->prev, trans, ticks);
  t->x = SpeedAxis(t->prev.x, trans->x, ticks);
  t->y = SpeedAxis(t->prev.y, trans->y, ticks);
  t->z = SpeedAxis(t->prev.z, trans->z, ticks);
  t->prev = *trans;
  if (speed > SPEED_TELEPORT
   || t->y > SPEED_TELEPORT || t->y < -SPEED_TELEPORT) {
    t->x = 0; t->y = 0; t->z = 0;
    return 0;
  }
  return speed;
}
