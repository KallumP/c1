#include "utest.h"
#include "pc/gfx/gte.h"

#define PROJ 280 /* screen_proj, the projection distance */

UTEST(gte, point_in_front_is_projected_by_its_depth) {
  int32_t sx, sy, sz;

  GtePerspective(100, -50, 400, PROJ, &sx, &sy, &sz);
  ASSERT_EQ(70, sx); /* 100*280/400 */
  ASSERT_EQ(-35, sy);
  ASSERT_EQ(400, sz);
}

UTEST(gte, point_behind_the_camera_has_depth_0) {
  int32_t sx, sy, sz;

  GtePerspective(-160, 40, -2000, PROJ, &sx, &sy, &sz);
  ASSERT_EQ(0, sz);
}

UTEST(gte, point_behind_the_camera_is_not_mirrored) {
  int32_t sx, sy, sz;

  /* dividing by the negative depth would put it at +22, -5 */
  GtePerspective(-160, 40, -2000, PROJ, &sx, &sy, &sz);
  ASSERT_LT(sx, 0);
  ASSERT_GT(sy, 0);
}

UTEST(gte, divide_saturates_at_or_under_half_the_projection_distance) {
  int32_t sx, sy, sz;

  /* the gte's quotient tops out at 0x1FFFF, about 2 */
  GtePerspective(100, -60, 140, PROJ, &sx, &sy, &sz);
  ASSERT_EQ(199, sx); /* (100*0x1FFFF)>>16 */
  ASSERT_EQ(-120, sy);
  ASSERT_EQ(140, sz);
}

UTEST(gte, screen_coords_are_clamped) {
  int32_t sx, sy, sz;

  GtePerspective(10000, -10000, 500, PROJ, &sx, &sy, &sz);
  ASSERT_EQ(0x3FF, sx);
  ASSERT_EQ(-0x400, sy);
  GtePerspective(-5000, 5000, -10, PROJ, &sx, &sy, &sz);
  ASSERT_EQ(-0x400, sx);
  ASSERT_EQ(0x3FF, sy);
}

UTEST(gte, depth_is_clamped_to_16_bits) {
  int32_t sx, sy, sz;

  GtePerspective(0, 0, 0x12345, PROJ, &sx, &sy, &sz);
  ASSERT_EQ(0xFFFF, sz);
}
