#ifndef _PC_GFX_GPU_H_
#define _PC_GFX_GPU_H_

#include "geom.h"

/*
 * the limits of the ps1's gpu (pc). it doesn't draw a polygon more than
 * 1023 wide or 511 tall on screen, such as one with a corner the gte has
 * pushed out to the edge of its range because it's beside or behind the
 * camera, so those never show as a stretch across the screen.
 */
#define GPU_POLY_W_MAX 1023
#define GPU_POLY_H_MAX 511

/* whether the gpu draws a polygon with these screen corners */
static inline int GpuPolygonFits(vec *v) {
  int32_t x_min, x_max, y_min, y_max;
  int i;

  x_min = x_max = v[0].x;
  y_min = y_max = v[0].y;
  for (i=1;i<3;i++) {
    if (v[i].x < x_min) { x_min = v[i].x; }
    if (v[i].x > x_max) { x_max = v[i].x; }
    if (v[i].y < y_min) { y_min = v[i].y; }
    if (v[i].y > y_max) { y_max = v[i].y; }
  }
  return x_max - x_min <= GPU_POLY_W_MAX && y_max - y_min <= GPU_POLY_H_MAX;
}

#endif /* _PC_GFX_GPU_H_ */
