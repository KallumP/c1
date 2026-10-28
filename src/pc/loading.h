#ifndef _PC_LOADING_H_
#define _PC_LOADING_H_

#include "common.h"

extern int LoadingImageConvert(uint8_t *image_data, size_t image_size,
  uint32_t w, uint32_t h, uint32_t *dst, size_t dst_count);

#endif /* _PC_LOADING_H_ */
