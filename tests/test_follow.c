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
