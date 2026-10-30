#include "follow.h"

int32_t follow_cam_offset = 0; /* the camera's x less its path's (game units) */

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
