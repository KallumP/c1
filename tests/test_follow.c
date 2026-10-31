#include "utest.h"
#include "pc/follow.h"

UTEST(follow, stays_put_on_target) {
  ASSERT_EQ(5000, FollowCamOffset(5000, 5000));
}

UTEST(follow, eases_a_fraction_of_the_way_each_frame) {
  ASSERT_EQ(8000 / FOLLOW_CAM_EASE, FollowCamOffset(0, 8000));
  ASSERT_EQ(-8000 / FOLLOW_CAM_EASE, FollowCamOffset(0, -8000));
}

UTEST(follow, moves_at_most_a_step_a_frame) {
  ASSERT_EQ(FOLLOW_CAM_STEP_MAX, FollowCamOffset(0, 100 * FOLLOW_CAM_STEP_MAX));
  ASSERT_EQ(-FOLLOW_CAM_STEP_MAX, FollowCamOffset(0, -100 * FOLLOW_CAM_STEP_MAX));
}

UTEST(follow, keeps_up_with_crash_running_sideways) {
  /* crash runs about 140 zone units (35840 game units) a frame */
  ASSERT_GT(FOLLOW_CAM_STEP_MAX, 140 << 8);
}

UTEST(follow, reaches_the_target_in_the_end) {
  int32_t offset = 0;
  int i;

  for (i=0;i<200;i++)
    offset = FollowCamOffset(offset, 123456);
  ASSERT_EQ(123456, offset);
}

UTEST(follow, takes_crashs_height_as_the_ground_while_hes_on_it) {
  ASSERT_EQ(5000, FollowCamGroundY(0, 5000, 1));
  ASSERT_EQ(-5000, FollowCamGroundY(0, -5000, 1));
}

UTEST(follow, keeps_the_ground_while_crash_jumps) {
  ASSERT_EQ(0, FollowCamGroundY(0, 5000, 0));
}

UTEST(follow, follows_crash_down_when_he_drops_below_the_ground) {
  ASSERT_EQ(-5000, FollowCamGroundY(0, -5000, 0));
}

UTEST(follow, starts_from_crashs_height) {
  ASSERT_EQ(5000, FollowCamGroundY(FOLLOW_CAM_NO_GROUND, 5000, 0));
}

UTEST(follow, aims_its_usual_height_above_crashs_floor) {
  /* the path is already that height above the floor: no offset */
  ASSERT_EQ(0, FollowCamHeightTarget(1000, 1000 + FOLLOW_CAM_HEIGHT));
  /* crash's floor is higher than the path's: the camera goes up by the difference */
  ASSERT_EQ(5000, FollowCamHeightTarget(6000, 1000 + FOLLOW_CAM_HEIGHT));
  ASSERT_EQ(-5000, FollowCamHeightTarget(-4000, 1000 + FOLLOW_CAM_HEIGHT));
}
