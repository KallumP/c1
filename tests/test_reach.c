#include "utest.h"
#include "pc/reach.h"

static vec at(int32_t z) {
  vec v;
  v.x = 0; v.y = 0; v.z = z;
  return v;
}

UTEST(reach, the_terrain_reaches_its_farthest_corner) {
  vec poly[3];
  int32_t reach;

  reach = REACH_UNKNOWN;
  poly[0] = at(1000); poly[1] = at(3000); poly[2] = at(2000);
  reach = ReachWithPolygon(reach, poly);
  ASSERT_EQ(3000, reach);
  poly[0] = at(500); poly[1] = at(800); poly[2] = at(700); /* nearer: no further */
  reach = ReachWithPolygon(reach, poly);
  ASSERT_EQ(3000, reach);
  poly[0] = at(9000); poly[1] = at(4000); poly[2] = at(4000);
  reach = ReachWithPolygon(reach, poly);
  ASSERT_EQ(9000, reach);
}

UTEST(reach, a_custom_level_hides_objects_past_the_terrain) {
  ASSERT_TRUE(ReachHidesObject(LID_TEST, 9000, 9001));
  ASSERT_FALSE(ReachHidesObject(LID_TEST, 9000, 9000));
  ASSERT_FALSE(ReachHidesObject(LID_TEST, 9000, 400));
}

UTEST(reach, the_games_own_levels_hide_nothing) {
  ASSERT_FALSE(ReachHidesObject(LID_NSANITYBEACH, 9000, 50000));
}

UTEST(reach, with_no_terrain_drawn_nothing_is_hidden) {
  ASSERT_FALSE(ReachHidesObject(LID_TEST, REACH_UNKNOWN, 50000));
}
