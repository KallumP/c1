/*
 * level loading screen (pc)
 */
#include "loading.h"
#include "gfx/pixel.h"

/*
 * convert a level loading image (a 256 entry ps1 5551 palette followed by
 * w x h 8-bit palette indices) to rgba.
 * returns 0 if the image is empty or doesn't fit in image_data or dst.
 */
int LoadingImageConvert(uint8_t *image_data, size_t image_size,
  uint32_t w, uint32_t h, uint32_t *dst, size_t dst_count) {
  uint16_t *palette;
  uint8_t *src;
  size_t i, count;

  if (w == 0 || h == 0 || image_size < 512) { return 0; }
  if (w > dst_count || h > dst_count / w) { return 0; } /* w*h > dst_count */
  count = (size_t)w * h;
  if (count > image_size - 512) { return 0; }
  palette = (uint16_t*)image_data;
  src = &image_data[512];
  for (i=0;i<count;i++)
    dst[i] = pixel_5551_8888(palette[src[i]], 1);
  return 1;
}
