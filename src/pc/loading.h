#ifndef _PC_LOADING_H_
#define _PC_LOADING_H_

#include "common.h"

extern int LoadingImageConvert(uint8_t *image_data, size_t image_size,
  uint32_t w, uint32_t h, uint32_t *dst, size_t dst_count);
extern uint32_t LoadingRemaining(uint32_t shown_at, uint32_t now,
  uint32_t min_ms);
extern void LoadingShown();
extern void LoadingWait();

#endif /* _PC_LOADING_H_ */
