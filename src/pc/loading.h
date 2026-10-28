#ifndef _PC_LOADING_H_
#define _PC_LOADING_H_

#include "common.h"

#define LOADING_MIN_MS 2000 /* minimum time the loading screen is shown */

extern int LoadingImageConvert(uint8_t *image_data, size_t image_size,
  uint32_t w, uint32_t h, uint32_t *dst, size_t dst_count);
extern uint32_t LoadingRemaining(uint32_t shown_at, uint32_t now);
extern void LoadingShown();
extern void LoadingWait();

#endif /* _PC_LOADING_H_ */
