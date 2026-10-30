#include "common.h"

int32_t ticks_base = 0;

/*
 * a counter's count (at freq a second) as ticks: 34000000/0x8000 a second.
 * whole seconds and the rest are converted apart, as 1000000*34*count
 * overflows an int64 once count passes about 2.7e11 (7.5 hours of a
 * 10 MHz counter)
 */
int32_t TimeTicksFromCount(int64_t count, int64_t freq) {
  int64_t secs, rest;

  secs = count / freq;
  rest = count % freq;
  return ((secs*34000000) + ((rest*34000000) / freq)) / 0x8000;
}

#ifdef _WIN32
#include <windows.h>
static inline int64_t GetCount(int64_t *freq) {
  LARGE_INTEGER _freq, _count;

  QueryPerformanceFrequency(&_freq);
  QueryPerformanceCounter(&_count);
  *freq = _freq.QuadPart;
  return _count.QuadPart;
}
#elif __linux__
#include <time.h>
static inline int64_t GetCount(int64_t *freq) {
  struct timespec tp;

  clock_gettime(CLOCK_MONOTONIC_RAW, &tp);
  *freq = 1000000000;
  return ((int64_t)tp.tv_sec*1000000000)+tp.tv_nsec;
}
#endif

/*
 * ticks since the first call, so they stay small and positive however long
 * the machine has been up (counted from its start, they went negative and
 * the first frame waited for hours)
 */
static inline int32_t GetTicks() {
  static int64_t start = -1;
  int64_t freq, count;

  count = GetCount(&freq);
  if (start < 0)
    start = count;
  return TimeTicksFromCount(count - start, freq);
}

int32_t TimeRealTicks() {
  return GetTicks();
}

/*
 * fixed clock (for recording and replaying inputs): game time only moves
 * when TimeAdvance is called, so every read of it is the same on replay
 */
static int fixed_clock = 0;
static int32_t fixed_ticks = 0;

void SetTicksElapsed(int32_t ticks) {
  if (fixed_clock) { fixed_ticks = ticks; return; }
  ticks_base = GetTicks() - ticks;
}

int GetTicksElapsed() {
  int32_t ticks;

  if (fixed_clock) { return fixed_ticks; }
  ticks = GetTicks() - ticks_base;
  return ticks;
}

/* switch between the fixed and real clocks, carrying on from the current time */
void TimeSetFixed(int fixed) {
  int32_t ticks;

  ticks = GetTicksElapsed();
  fixed_clock = fixed;
  SetTicksElapsed(ticks);
}

int TimeIsFixed() {
  return fixed_clock;
}

/* move the fixed clock on */
void TimeAdvance(int32_t ticks) {
  fixed_ticks += ticks;
}

static uint32_t speed = 1; /* times normal speed, 0 = as fast as possible */

/*
 * wait until a frame's worth of real time (divided by the speed) has passed
 * since the last call, then move the fixed clock on that frame. a slow frame
 * isn't made up for, so game time only ever moves a whole frame at a time
 */
void TimeWaitFrame(int32_t ticks) {
  static int32_t real_stamp = 0;

  if (speed)
    while (GetTicks() - real_stamp < ticks / (int32_t)speed);
  real_stamp = GetTicks();
  fixed_ticks += ticks;
}

/* how fast TimeWaitFrame lets the fixed clock run, for replays */
void TimeSetSpeed(uint32_t new_speed) {
  speed = new_speed;
}

uint32_t TimeGetSpeed() {
  return speed;
}
