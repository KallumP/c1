#ifndef _PC_SPEED_H_
#define _PC_SPEED_H_

#include "common.h"
#include "geom.h"

/* moves faster than this are teleports (e.g. respawning), not movement */
#define SPEED_TELEPORT 5000

typedef struct {
  void *obj; /* object being tracked, or 0 */
  vec prev;  /* its position last frame */
} speed_tracker;

extern uint32_t SpeedMeasure(vec *prev, vec *cur, int32_t ticks);
extern uint32_t SpeedTrack(speed_tracker *t, void *obj, vec *trans,
  int32_t ticks);

#endif /* _PC_SPEED_H_ */
