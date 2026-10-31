#include "utest.h"
#include "pc/gfx/gpu.h"

static void set(vec *v, int32_t x, int32_t y) {
  v->x = x; v->y = y; v->z = 1000;
}

UTEST(gpu, a_polygon_on_screen_is_drawn) {
  vec v[3];

  set(&v[0], -100, -50); set(&v[1], 120, 40); set(&v[2], 0, 100);
  ASSERT_TRUE(GpuPolygonFits(v));
}

UTEST(gpu, a_polygon_up_to_1023_wide_and_511_tall_is_drawn) {
  vec v[3];

  set(&v[0], -0x200, -0x100); set(&v[1], 0x1FF, -0x100); set(&v[2], 0, 0xFF);
  ASSERT_TRUE(GpuPolygonFits(v));
}

UTEST(gpu, a_polygon_wider_than_1023_is_not_drawn) {
  vec v[3];

  set(&v[0], -0x400, 0); set(&v[1], 0x400, 0); set(&v[2], 0, 10);
  ASSERT_FALSE(GpuPolygonFits(v));
}

UTEST(gpu, a_polygon_taller_than_511_is_not_drawn) {
  vec v[3];

  set(&v[0], 0, -0x100); set(&v[1], 10, 0x100); set(&v[2], 0, 0);
  ASSERT_FALSE(GpuPolygonFits(v));
}
