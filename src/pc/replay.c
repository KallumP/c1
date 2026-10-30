/*
 * input recording and replay (pc)
 */
#include "replay.h"

/* start recording to path; returns 0 if the file can't be opened */
int ReplayRecordStart(replay_recorder *r, const char *path,
  replay_header *header) {
  return 0;
}

/* record one frame */
void ReplayRecordFrame(replay_recorder *r, int32_t ticks, uint32_t held) {
}

/* finish the recording */
void ReplayRecordStop(replay_recorder *r) {
}
