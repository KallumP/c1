#ifndef _PIXEL_H_
#define _PIXEL_H_

#include "common.h"

/* convert a ps1 5551 (bgr + stp) pixel to 8888 rgba (stored as bytes r, g, b, a) */
static inline uint32_t pixel_5551_8888(uint16_t p, int mode) {
  int r, g, b, a;

  r = (p >> 0) & 0x1F;
  g = (p >> 5) & 0x1F;
  b = (p >> 10) & 0x1F;
  a = (p >> 15);

  r = ((r*510)+31)/62;
  g = ((g*510)+31)/62;
  b = ((b*510)+31)/62;

  switch (mode) {
  case 0: a = a == 1 ? 0x7F : (r|g|b) == 0 ? 0 : 0xFF; break;
  case 1: a = a == 1 ? 0xFF : (r|g|b) == 0 ? 0 : 0xFF; break;
  case 2: a = a == 1 ? 0xFF : (r|g|b) == 0 ? 0 : 0xFF; break;
  case 3: a = a == 1 ? 0xFF : (r|g|b) == 0 ? 0 : 0xFF; break;
  }
  return (a << 24) | (b << 16) | (g << 8) | r;
}

#endif /* _PIXEL_H_ */
