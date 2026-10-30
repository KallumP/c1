#include "utest.h"
#include "pc/replay.h"

#define TEST_REPLAY "build/test_replay.rec"

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
