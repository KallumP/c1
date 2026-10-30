#ifndef _PC_TIME_H_
#define _PC_TIME_H_

#include "common.h"

extern void SetTicksElapsed(int32_t ticks);
extern int GetTicksElapsed();
extern void TimeSetFixed(int fixed);
extern int TimeIsFixed();
extern void TimeAdvance(int32_t ticks);
extern void TimeWaitFrame(int32_t ticks);
extern void TimeSetSpeed(uint32_t speed);
extern uint32_t TimeGetSpeed();
extern int32_t TimeTicksFromCount(int64_t count, int64_t freq);
extern int32_t TimeRealTicks();

#endif /* _PC_TIME_H_ */
