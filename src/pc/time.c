#include "common.h"

int32_t ticks_base = 0;

#ifdef _WIN32
#include <windows.h>
static inline int32_t GetTicks() {
  LARGE_INTEGER _freq, _count;
  int64_t freq, count;
  int32_t ticks;

  QueryPerformanceFrequency(&_freq);
  QueryPerformanceCounter(&_count);
  freq = _freq.QuadPart;
  count = _count.QuadPart;

  ticks = ((1000000*(count*34)) / 0x8000) / freq;
  return ticks;
}
#elif __linux__
#include <time.h>
static inline int32_t GetTicks() {
  struct timespec tp;
  int32_t ticks;

  clock_gettime(CLOCK_MONOTONIC_RAW, &tp);
  ticks = ((((int64_t)tp.tv_sec*1000000000)+tp.tv_nsec) / 963765);
  //printf("%i ticks elapsed\n", ticks);
  return ticks;
}
#endif

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

void TimeWaitFrame(int32_t ticks) {
}
