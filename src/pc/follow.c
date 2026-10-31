#include "follow.h"

int32_t follow_cam_offset = 0; /* the camera's x less its path's (game units) */
int32_t follow_cam_ground_y = FOLLOW_CAM_NO_GROUND; /* height of the floor crash was last on */

/*
 * the follow camera's next sideways offset from its path, from offset
 * towards target (crash's x less the path's): 1/FOLLOW_CAM_EASE of the way,
 * at most FOLLOW_CAM_STEP_MAX, and the rest of the way once it's that close
 */
int32_t FollowCamOffset(int32_t offset, int32_t target) {
  int32_t step;

  step = (target - offset) / FOLLOW_CAM_EASE;
  if (step == 0)
    return target;
  step = limit(step, -FOLLOW_CAM_STEP_MAX, FOLLOW_CAM_STEP_MAX);
  return offset + step;
}

/*
 * the height of the floor the follow camera keeps above: crash's height
 * while he's on the floor, else ground (the floor he was last on), unless
 * he's dropped below it. so it rises when he lands somewhere higher, but
 * not with each jump, and goes down with him when he falls
 */
int32_t FollowCamGroundY(int32_t ground, int32_t crash_y, int on_floor) {
  if (on_floor)
    return crash_y;
  return min(ground, crash_y);
}
