#include <string.h>
#include "utest.h"
#include "pc/replay.h"
#include "pc/pad.h"
#include "pc/time.h"

#define TEST_REPLAY "build/test_replay.rec"

extern uint8_t keys[512]; /* defined in test_pad.c */

/* read back a recording's header and up to max frames; returns the frame count */
static int ReadRecording(replay_header *header, replay_frame *frames, int max) {
  FILE *file;
  int count;

  file = fopen(TEST_REPLAY, "rb");
  if (!file) { return -1; }
  if (fread(header, sizeof(replay_header), 1, file) != 1) { fclose(file); return -1; }
  count = (int)fread(frames, sizeof(replay_frame), max, file);
  fclose(file);
  return count;
}

UTEST(replay, start_recording_fixes_the_clock_and_writes_the_header) {
  replay_header header;
  replay_frame frames[1];

  ASSERT_EQ(1, ReplayStart(TEST_REPLAY, REPLAY_RECORD, 0x19, 12345));
  ASSERT_TRUE(TimeIsFixed());
  ReplayStop();
  ASSERT_EQ(0, ReadRecording(&header, frames, 1));
  ASSERT_EQ((uint32_t)REPLAY_MAGIC, header.magic);
  ASSERT_EQ(0x19u, header.lid);
  ASSERT_EQ(12345u, header.seed);
}

UTEST(replay, each_update_records_the_clock_and_the_buttons_held) {
  replay_header header;
  replay_frame frames[3];
  int32_t start;

  memset(keys, 0, sizeof(keys));
  PadResetBindings();
  ASSERT_EQ(1, ReplayStart(TEST_REPLAY, REPLAY_RECORD, 0x19, 12345));
  start = GetTicksElapsed();
  keys[SDL_SCANCODE_Z] = 1;
  ReplayUpdate();
  keys[SDL_SCANCODE_Z] = 0;
  TimeAdvance(34);
  ReplayUpdate();
  ReplayStop();
  ASSERT_EQ(2, ReadRecording(&header, frames, 3));
  ASSERT_EQ(start, header.start_ticks);
  ASSERT_EQ(start, frames[0].ticks);
  ASSERT_EQ((uint32_t)PAD_CROSS << 16, frames[0].held);
  ASSERT_EQ(start + 34, frames[1].ticks);
  ASSERT_EQ(0u, frames[1].held);
}

UTEST(replay, stopping_goes_back_to_the_real_clock) {
  ASSERT_EQ(1, ReplayStart(TEST_REPLAY, REPLAY_RECORD, 0x19, 12345));
  ReplayStop();
  ASSERT_FALSE(TimeIsFixed());
}

/* record frames holding each of held[] in turn */
static void Record(uint32_t lid, SDL_Scancode *held, int count) {
  int i;

  memset(keys, 0, sizeof(keys));
  PadResetBindings();
  ReplayStart(TEST_REPLAY, REPLAY_RECORD, lid, 12345);
  for (i=0;i<count;i++) {
    memset(keys, 0, sizeof(keys));
    if (held[i]) { keys[held[i]] = 1; }
    ReplayUpdate();
    TimeWaitFrame(34);
  }
  ReplayStop();
  memset(keys, 0, sizeof(keys));
}

UTEST(replay, replay_feeds_the_recorded_buttons_instead_of_the_keyboard) {
  SDL_Scancode held[2] = { SDL_SCANCODE_Z, 0 };

  Record(0x19, held, 2);
  ASSERT_EQ(1, ReplayStart(TEST_REPLAY, REPLAY_PLAY, 0x19, 12345));
  keys[SDL_SCANCODE_LEFT] = 1; /* ignored while replaying */
  ReplayUpdate();
  ASSERT_EQ((uint32_t)PAD_CROSS << 16, SwPadRead(0));
  TimeWaitFrame(34);
  ReplayUpdate();
  ASSERT_EQ(0u, SwPadRead(0));
  ReplayStop();
  keys[SDL_SCANCODE_LEFT] = 0;
}

UTEST(replay, replay_starts_on_the_fixed_clock_at_the_recorded_time) {
  SDL_Scancode held[1] = { 0 };
  replay_header header;
  replay_frame frames[1];

  Record(0x19, held, 1);
  ASSERT_EQ(1, ReadRecording(&header, frames, 1));
  SetTicksElapsed(header.start_ticks + 1000);
  ASSERT_EQ(1, ReplayStart(TEST_REPLAY, REPLAY_PLAY, 0x19, 12345));
  ASSERT_TRUE(TimeIsFixed());
  ASSERT_EQ(header.start_ticks, GetTicksElapsed());
  ReplayStop();
}

UTEST(replay, replay_refuses_a_recording_from_another_boot_level) {
  SDL_Scancode held[1] = { 0 };

  Record(0x19, held, 1);
  ASSERT_EQ(0, ReplayStart(TEST_REPLAY, REPLAY_PLAY, 0x09, 12345));
  ASSERT_FALSE(TimeIsFixed());
}

UTEST(replay, replay_of_a_missing_file_fails_cleanly) {
  remove("build/no_such_file.rec");
  ASSERT_EQ(0, ReplayStart("build/no_such_file.rec", REPLAY_PLAY, 0x19, 12345));
  ASSERT_FALSE(TimeIsFixed());
}

UTEST(replay, start_fails_cleanly_for_a_bad_path) {
  ASSERT_EQ(0, ReplayStart("build/no/such/dir/test.rec", REPLAY_RECORD, 0x19, 12345));
  ASSERT_FALSE(TimeIsFixed());
}

UTEST(replay, recording_writes_the_header_then_each_frame) {
  replay_recorder r = { 0 };
  replay_header header = { .lid = 9, .seed = 1234, .start_ticks = 5678 };
  replay_header header_read;
  replay_frame frames_read[3];
  FILE *file;
  size_t count;

  ASSERT_EQ(1, ReplayRecordStart(&r, TEST_REPLAY, &header));
  ReplayRecordFrame(&r, 34, 0x10);
  ReplayRecordFrame(&r, 68, 0x30);
  ReplayRecordStop(&r);
  ASSERT_TRUE(r.file == 0);

  file = fopen(TEST_REPLAY, "rb");
  ASSERT_TRUE(file != 0);
  ASSERT_EQ(1u, fread(&header_read, sizeof(header_read), 1, file));
  count = fread(frames_read, sizeof(replay_frame), 3, file);
  fclose(file);
  ASSERT_EQ((uint32_t)REPLAY_MAGIC, header_read.magic);
  ASSERT_EQ(9u, header_read.lid);
  ASSERT_EQ(1234u, header_read.seed);
  ASSERT_EQ(5678, header_read.start_ticks);
  ASSERT_EQ(2u, count);
  ASSERT_EQ(34, frames_read[0].ticks);
  ASSERT_EQ(0x10u, frames_read[0].held);
  ASSERT_EQ(68, frames_read[1].ticks);
  ASSERT_EQ(0x30u, frames_read[1].held);
}

UTEST(replay, recording_to_a_bad_path_fails) {
  replay_recorder r = { 0 };
  replay_header header = { 0 };

  ASSERT_EQ(0, ReplayRecordStart(&r, "build/no/such/dir/test.rec", &header));
  ASSERT_TRUE(r.file == 0);
}

UTEST(replay, frames_are_ignored_when_not_recording) {
  replay_recorder r = { 0 };

  ReplayRecordFrame(&r, 34, 0x10); /* must not crash */
  ReplayRecordStop(&r);
  ASSERT_TRUE(r.file == 0);
}
