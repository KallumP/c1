#include <string.h>
#include "utest.h"
#include "pc/loading.h"

#define IMAGE_SIZE 0xF5F8 /* size of nsd_ldat.image_data */

static uint8_t image_data[IMAGE_SIZE];
static uint32_t rgba[512*240];

/* set palette entry idx to a ps1 5551 colour */
static void set_colour(int idx, int r, int g, int b) {
  uint16_t *palette;

  palette = (uint16_t*)image_data;
  palette[idx] = (uint16_t)(r | (g << 5) | (b << 10));
}

UTEST(loading, converts_palette_indices_to_rgba) {
  uint8_t *pixels;

  memset(image_data, 0, sizeof(image_data));
  set_colour(1, 31, 0, 0);  /* red */
  set_colour(2, 0, 31, 0);  /* green */
  set_colour(3, 0, 0, 31);  /* blue */
  set_colour(4, 31, 31, 31);  /* white */
  pixels = &image_data[512];
  pixels[0] = 1; pixels[1] = 2;
  pixels[2] = 3; pixels[3] = 4;
  ASSERT_EQ(1, LoadingImageConvert(image_data, sizeof(image_data), 2, 2, rgba, 512*240));
  /* rgba is stored as bytes r, g, b, a */
  ASSERT_EQ(0xFF0000FFu, rgba[0]);
  ASSERT_EQ(0xFF00FF00u, rgba[1]);
  ASSERT_EQ(0xFFFF0000u, rgba[2]);
  ASSERT_EQ(0xFFFFFFFFu, rgba[3]);
}

UTEST(loading, accepts_full_size_level_image) {
  memset(image_data, 0, sizeof(image_data));
  ASSERT_EQ(1, LoadingImageConvert(image_data, sizeof(image_data), 432, 144, rgba, 512*240));
}

UTEST(loading, rejects_image_larger_than_its_data) {
  memset(image_data, 0, sizeof(image_data));
  /* the garbage header in s0000004.nsd */
  ASSERT_EQ(0, LoadingImageConvert(image_data, sizeof(image_data), 47, 671097453, rgba, 512*240));
  ASSERT_EQ(0, LoadingImageConvert(image_data, sizeof(image_data), 512, 240, rgba, 512*240));
}

UTEST(loading, rejects_image_larger_than_destination) {
  memset(image_data, 0, sizeof(image_data));
  ASSERT_EQ(0, LoadingImageConvert(image_data, sizeof(image_data), 432, 144, rgba, 100));
}

UTEST(loading, rejects_empty_image) {
  memset(image_data, 0, sizeof(image_data));
  ASSERT_EQ(0, LoadingImageConvert(image_data, sizeof(image_data), 0, 144, rgba, 512*240));
  ASSERT_EQ(0, LoadingImageConvert(image_data, sizeof(image_data), 432, 0, rgba, 512*240));
}
