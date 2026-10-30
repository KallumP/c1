#ifndef _PC_FOLLOW_H_
#define _PC_FOLLOW_H_

#include "common.h"

/*
 * the follow camera (cam_mode 9, for custom levels): it moves along its
 * path as the follow crash camera (cam_mode 5) does, and slides sideways
 * from the path's x towards crash's, so he stays in view off the path
 */
#define FOLLOW_CAM_EASE     8      /* moves this fraction of the way each frame */
#define FOLLOW_CAM_STEP_MAX 64000  /* and at most this far (game units, 250 zone units) */

extern int32_t FollowCamOffset(int32_t offset, int32_t target);

#endif /* _PC_FOLLOW_H_ */
