/*
 * input recording and replay (pc)
 */
#include "replay.h"
#include "pad.h"
#include "time.h"

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

static replay_recorder recorder = { 0 };

static FILE *replay_file = 0;   /* recording being replayed, or 0 */
static uint32_t replay_held = 0; /* buttons held this frame of the replay */
static int replay_desynced = 0;

/*
 * start replaying the recording at path. it must have been made with the
 * same boot level and random seed, or it would play out differently
 */
static int ReplayPlayStart(const char *path, uint32_t lid, uint32_t seed) {
  replay_header header;
  FILE *file;

  file = fopen(path, "rb");
  if (!file) { return 0; }
  if (fread(&header, sizeof(header), 1, file) != 1
   || header.magic != REPLAY_MAGIC) {
    fprintf(stderr, "%s is not an input recording\n", path);
    fclose(file);
    return 0;
  }
  if (header.lid != lid || header.seed != seed) {
    fprintf(stderr, "%s was recorded with a different boot level or seed\n", path);
    fclose(file);
    return 0;
  }
  replay_file = file;
  replay_held = 0;
  replay_desynced = 0;
  TimeSetFixed(1);
  SetTicksElapsed(header.start_ticks);
  return 1;
}

/*
 * start recording inputs to path (REPLAY_RECORD) or replaying them from it
 * (REPLAY_PLAY), on the fixed clock so that every read of game time is the
 * same on replay. returns 0 if the file can't be used
 */
int ReplayStart(const char *path, int mode, uint32_t lid, uint32_t seed) {
  replay_header header;

  if (mode == REPLAY_PLAY)
    return ReplayPlayStart(path, lid, seed);
  TimeSetFixed(1); /* first, so the start time is the one the clock stays at */
  header.lid = lid;
  header.seed = seed;
  header.start_ticks = GetTicksElapsed();
  if (!ReplayRecordStart(&recorder, path, &header)) {
    TimeSetFixed(0);
    return 0;
  }
  return 1;
}

/*
 * record this frame, or read the next frame of the replay; call once per
 * frame, after input is polled
 */
void ReplayUpdate() {
  replay_frame frame;

  if (replay_file) {
    if (fread(&frame, sizeof(frame), 1, replay_file) != 1) { return; }
    if (frame.ticks != GetTicksElapsed() && !replay_desynced) {
      fprintf(stderr, "replay out of step at tick %d (recorded at %d)\n",
        GetTicksElapsed(), frame.ticks);
      replay_desynced = 1;
    }
    replay_held = frame.held;
    return;
  }
  ReplayRecordFrame(&recorder, GetTicksElapsed(), SwPadRead(0));
  if (recorder.file)
    fflush(recorder.file); /* keep what's recorded if the game crashes */
}

/* while replaying, sets held to the replay's buttons and returns 1 */
int ReplayHeld(uint32_t *held) {
  if (!replay_file) { return 0; }
  *held = replay_held;
  return 1;
}

void ReplayStop() {
  ReplayRecordStop(&recorder);
  if (replay_file) {
    fclose(replay_file);
    replay_file = 0;
  }
  TimeSetFixed(0);
}
