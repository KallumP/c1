#include "utest.h"
#include "pc/gfx/gldepth.h"

UTEST(gldepth, nearer_vertex_has_smaller_depth) {
  ASSERT_LT(GLDepthFromZ(1000), GLDepthFromZ(2000));
}

UTEST(gldepth, depth_is_linear_in_1_over_z) {
  /* 1 - near/z, so twice and four times the near distance give 1/2 and 3/4 */
  ASSERT_EQ(0.5f, GLDepthFromZ(GL_DEPTH_NEAR*2));
  ASSERT_EQ(0.75f, GLDepthFromZ(GL_DEPTH_NEAR*4));
}

UTEST(gldepth, depth_at_or_before_near_is_0) {
  ASSERT_EQ(0.0f, GLDepthFromZ(GL_DEPTH_NEAR));
  ASSERT_EQ(0.0f, GLDepthFromZ(1));
  ASSERT_EQ(0.0f, GLDepthFromZ(-5));
}

UTEST(gldepth, furthest_depth_is_below_1) {
  ASSERT_LT(GLDepthFromZ(0xFFFF), 1.0f);
}

UTEST(gldepth, tolerance_pushes_depth_back) {
  ASSERT_LT(GLDepthFromZ(1000), GLDepthFromZ(1000 + GL_DEPTH_TOLERANCE));
}
