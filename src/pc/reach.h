#ifndef _PC_REACH_H_
#define _PC_REACH_H_

#include "common.h"
#include "geom.h"
#include "ns.h"

/*
 * how far the terrain reaches (pc): a custom level's sort lists hold its
 * nearest polygons, as many as fit, so the terrain stops short of the far
 * end of the zones, whose objects are all loaded; objects past where it
 * stops are left out, so none is drawn over nothing
 */
#define REACH_UNKNOWN -1 /* no terrain drawn this frame */

extern int32_t terrain_reach; /* camera depth of the farthest terrain drawn this frame */

/* reach, widened to take in a polygon's corners (in camera space) */
static inline int32_t ReachWithPolygon(int32_t reach, vec *verts) {
  int i;

  for (i=0;i<3;i++) {
    if (verts[i].z > reach)
      reach = verts[i].z;
  }
  return reach;
}

/* whether an object z deep in front of the camera is past the terrain */
static inline int ReachHidesObject(lid_t lid, int32_t reach, int32_t z) {
  return lid == LID_TEST && reach != REACH_UNKNOWN && z > reach;
}

#endif /* _PC_REACH_H_ */
