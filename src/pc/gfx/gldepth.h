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

/*
 * prim flags bit marking a level (world) triangle that can write depth.
 * a custom level's sort lists can't order its polygons against the models
 * the way the original levels' hand-made ones do (e.g. a crate just behind
 * a pillar is drawn over it), so in custom levels the level writes depth
 * and models are depth tested against it. the level itself is still drawn
 * in sort list order
 */
#define GL_PRIM_LEVEL 8

static inline int GLPrimLevelWritesDepth(int flags, int custom_level) {
  return custom_level && (flags & GL_PRIM_LEVEL) != 0
    && GLPrimBlendMode(flags) != 1 && GLPrimBlendMode(flags) != 2;
}

/* model tris are depth tested with fix_model_draw_order (against each other), and in custom levels (against the level) */
static inline int GLPrimModelDepthTested(int flags, int fix_model_draw_order, int custom_level) {
  return GLPrimDepthTested(flags) && (fix_model_draw_order || custom_level);
}

/*
 * whether a level tri's corner depths can go in the depth buffer: not when
 * a corner is at or under half the projection distance, as the gte then
 * pushes it to the side of the screen (see gte.h) and depths across the
 * tri would be wrong
 */
static inline int GLLevelTriHasDepth(int32_t z0, int32_t z1, int32_t z2, int32_t proj) {
  return z0*2 > proj && z1*2 > proj && z2*2 > proj;
}

#endif /* _PC_GFX_GLDEPTH_H_ */
