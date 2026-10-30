#ifndef _TIME_H_
#define _TIME_H_

#include "common.h"

extern void SetTicksElapsed(int32_t ticks);
extern int GetTicksElapsed();
extern void TimeSetFixed(int fixed);
extern int TimeIsFixed();
extern void TimeAdvance(int32_t ticks);
extern void TimeWaitFrame(int32_t ticks);

#endif /* _TIME_H_ */
