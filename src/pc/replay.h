#ifndef _PC_REPLAY_H_
#define _PC_REPLAY_H_

#include <stdio.h>
#include <time.h>
#include "common.h"

#define REPLAY_DIR   "recorded_inputs" /* one file per run, named by start time */
#define REPLAY_MAGIC 0x31434552 /* "REC1" */

/* state needed to start a level the same way again */
typedef struct {
  uint32_t magic;
  uint32_t lid;         /* level the recording starts in */
  uint32_t seed;        /* random seed at the start */
  int32_t start_ticks;  /* tick count at the start */
} replay_header;

/* one frame of input */
typedef struct {
  int32_t ticks;        /* tick count when the frame was drawn */
  uint32_t held;        /* buttons held */
} replay_frame;

typedef struct {
  FILE *file;           /* open recording, or 0 */
} replay_recorder;

extern int ReplayRecordStart(replay_recorder *r, const char *path,
  replay_header *header);
extern void ReplayRecordFrame(replay_recorder *r, int32_t ticks,
  uint32_t held);
extern void ReplayRecordStop(replay_recorder *r);

/* recording files */
extern void ReplayFileName(char *name, size_t size, const char *dir,
  struct tm *start);
extern int ReplayNewestFile(const char *dir, char *path, size_t size);
extern int ReplayMakeDir(const char *dir);

/* game side */
#define REPLAY_RECORD 1
#define REPLAY_PLAY   2

extern int ReplayStart(const char *path, int mode, uint32_t lid,
  uint32_t seed);
extern void ReplayUpdate();
extern int ReplayHeld(uint32_t *held);
extern void ReplayStop();

#endif /* _PC_REPLAY_H_ */
