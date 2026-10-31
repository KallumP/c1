#ifndef _SLST_H_
#define _SLST_H_

#include "common.h"
#include "formats/slst.h"

extern poly_id_list *poly_id_buf1;
extern poly_id_list *poly_id_buf2;
extern poly_id_list *next_poly_ids;

#define cur_poly_ids poly_id_buf1
#define prev_poly_ids poly_id_buf2

/* custom levels (pc) list more polygons than the game's own levels, so
   they draw further: as many as a delta node can index (12 bits) */
#define SLST_CUSTOM_POLY_IDS 4096

/* how many polygons a level's sort lists hold */
static inline int SlstPolyIdCount(lid_t lid) {
  if (lid == LID_TITLE || lid == LID_INTRO)
    return 2610;
  if (lid == LID_TEST) /* not in orig */
    return SLST_CUSTOM_POLY_IDS;
  return 1460;
}

extern int SlstInit();
extern int SlstKill();
extern poly_id_list *SlstUpdate(slst_item *item,
  poly_id_list *src, poly_id_list *dst, int dir);

#endif /* _SLST_H_ */
