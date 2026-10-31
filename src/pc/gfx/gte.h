#ifndef _PC_GFX_GTE_H_
#define _PC_GFX_GTE_H_

#include <stdint.h>

/*
 * perspective projection with the limits of the ps1's gte (RTPS), for a
 * point already rotated and translated into camera space (pc).
 *
 * the gte clamps depth (SZ) to 0..0xFFFF, so a point behind the camera has
 * depth 0. its divide saturates (the quotient tops out at 0x1FFFF, about 2)
 * when depth is at or under half the projection distance, and screen x/y are
 * clamped to -0x400..0x3FF. so a point behind or right in front of the camera
 * ends up off to the side, never mirrored through the middle of the screen.
 * otherwise this is the same divide as SwRotTransPers.
 */
#define GTE_SZ_MAX    0xFFFF
#define GTE_IR_MIN   -0x8000
#define GTE_IR_MAX    0x7FFF
#define GTE_SXY_MIN  -0x400
#define GTE_SXY_MAX   0x3FF
#define GTE_DIV_MAX   0x1FFFF

static inline int32_t GteLimit(int32_t v, int32_t min, int32_t max) {
  return v < min ? min : (v > max ? max : v);
}

/* the same, with the screen offset (ofx, ofy) added before the clamp, as
   the gte does */
static inline void GtePerspectiveAt(int32_t x, int32_t y, int32_t z,
  int32_t proj, int32_t ofx, int32_t ofy, int32_t *sx, int32_t *sy, int32_t *sz) {
  int64_t px, py;

  *sz = GteLimit(z, 0, GTE_SZ_MAX);
  if (*sz * 2 <= proj) { /* divide overflow: the quotient saturates */
    px = ((int64_t)GteLimit(x, GTE_IR_MIN, GTE_IR_MAX) * GTE_DIV_MAX) >> 16;
    py = ((int64_t)GteLimit(y, GTE_IR_MIN, GTE_IR_MAX) * GTE_DIV_MAX) >> 16;
  }
  else {
    px = ((int64_t)x * ((int64_t)proj << 16) / *sz) >> 16;
    py = ((int64_t)y * ((int64_t)proj << 16) / *sz) >> 16;
  }
  px += ofx;
  py += ofy;
  *sx = (int32_t)(px < GTE_SXY_MIN ? GTE_SXY_MIN : (px > GTE_SXY_MAX ? GTE_SXY_MAX : px));
  *sy = (int32_t)(py < GTE_SXY_MIN ? GTE_SXY_MIN : (py > GTE_SXY_MAX ? GTE_SXY_MAX : py));
}

static inline void GtePerspective(int32_t x, int32_t y, int32_t z,
  int32_t proj, int32_t *sx, int32_t *sy, int32_t *sz) {
  GtePerspectiveAt(x, y, z, proj, 0, 0, sx, sy, sz);
}

#endif /* _PC_GFX_GTE_H_ */
