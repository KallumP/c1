/*
 * input recording and replay (pc)
 */
#include "replay.h"

/* start recording to path; returns 0 if the file can't be opened */
int ReplayRecordStart(replay_recorder *r, const char *path,
  replay_header *header) {
  r->file = fopen(path, "wb");
  if (!r->file) { return 0; }
  header->magic = REPLAY_MAGIC;
  fwrite(header, sizeof(replay_header), 1, r->file);
  return 1;
}

/* record one frame */
void ReplayRecordFrame(replay_recorder *r, int32_t ticks, uint32_t held) {
  replay_frame frame;

  if (!r->file) { return; }
  frame.ticks = ticks;
  frame.held = held;
  fwrite(&frame, sizeof(replay_frame), 1, r->file);
}

/* finish the recording */
void ReplayRecordStop(replay_recorder *r) {
  if (!r->file) { return; }
  fclose(r->file);
  r->file = 0;
}

int ReplayStart(const char *path, int mode, uint32_t lid, uint32_t seed) {
  return 0;
}

void ReplayUpdate() {
}

void ReplayStop() {
}
