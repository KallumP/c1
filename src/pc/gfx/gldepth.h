#ifndef _PC_GFX_GLDEPTH_H_
#define _PC_GFX_GLDEPTH_H_

#include <stdint.h>

/*
 * depth of 3d model triangles for the gl depth buffer (pc).
 *
 * vertex depths are the rotated z values used for the ot (gte sz units).
 * gl depth is 1 - near/z, which is linear in screen space, so it can be
 * interpolated across a triangle without perspective correction.
 */
#define GL_DEPTH_NEAR      64 /* vertex depths at or before this map to 0 */
#define GL_DEPTH_TOLERANCE 32 /* how far behind a model another can be and still draw over it */

static inline float GLDepthFromZ(int32_t z) {
  if (z <= GL_DEPTH_NEAR) { return 0.0f; }
  return 1.0f - ((float)GL_DEPTH_NEAR/(float)z);
}

/* prim flags bit marking a 3d model triangle for depth testing; the low 2 bits are the blend mode */
#define GL_PRIM_DEPTH 4

static inline int GLPrimDepthTested(int flags) { return (flags & GL_PRIM_DEPTH) != 0; }
static inline int GLPrimBlendMode(int flags) { return flags & 3; }

/* marked tris write depth unless they are additive (1) or subtractive (2) effects */
static inline int GLPrimWritesDepth(int flags) {
  return GLPrimDepthTested(flags) && GLPrimBlendMode(flags) != 1 && GLPrimBlendMode(flags) != 2;
}

#endif /* _PC_GFX_GLDEPTH_H_ */
