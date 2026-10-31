#include <stddef.h>
#include "utest.h"
#include "gfx.h"
#include "gool.h"

cam_state cam, cam_prev; /* gfx.c's, which the tests don't build */

/* the game reads the camera's position, rotation and scale as a
   gool_vectors, so they have to be laid out as its first three */

UTEST(cam_state, is_laid_out_as_the_start_of_gool_vectors) {
  ASSERT_EQ(offsetof(gool_vectors, trans), offsetof(cam_state, trans));
  ASSERT_EQ(offsetof(gool_vectors, rot), offsetof(cam_state, rot));
  ASSERT_EQ(offsetof(gool_vectors, scale), offsetof(cam_state, scale));
}

UTEST(cam_state, the_names_are_its_parts) {
  ASSERT_EQ((void*)&cam.trans, (void*)&cam_trans);
  ASSERT_EQ((void*)&cam.scale, (void*)&cam_scale);
  ASSERT_EQ((void*)&cam_prev.rot, (void*)&cam_rot_prev);
}
