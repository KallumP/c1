/*
 * level loading screen (pc)
 */
#include <SDL2/SDL.h>
#include "loading.h"
#include "gfx/pixel.h"
#include "time.h"

static uint32_t loading_shown_at;
static int loading_shown = 0;

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

/*
 * the time in ms the loading screen has left to be shown, given when it was
 * shown and the time now (from SDL_GetTicks; unsigned, so wrapping is fine)
 */
uint32_t LoadingRemaining(uint32_t shown_at, uint32_t now) {
  uint32_t elapsed;

  elapsed = now - shown_at;
  if (elapsed >= LOADING_MIN_MS) { return 0; }
  return LOADING_MIN_MS - elapsed;
}

/* record that the loading screen has just been shown */
void LoadingShown() {
  loading_shown_at = SDL_GetTicks();
  loading_shown = 1;
}

/*
 * wait until the loading screen has been shown for LOADING_MIN_MS, since
 * levels load from disk far faster than from the ps1 cd. window events are
 * pumped so the os doesn't flag the game as not responding, and the game
 * clock is paused so the wait doesn't count as one long frame
 */
void LoadingWait() {
  uint32_t left;
  int32_t ticks;

  if (!loading_shown) { return; }
  loading_shown = 0;
  ticks = GetTicksElapsed();
  while ((left = LoadingRemaining(loading_shown_at, SDL_GetTicks()))) {
    SDL_PumpEvents();
    SDL_Delay(left < 10 ? left : 10);
  }
  SetTicksElapsed(ticks);
}
