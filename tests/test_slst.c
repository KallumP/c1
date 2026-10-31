#include "utest.h"
#include "slst.h"

UTEST(slst, the_games_levels_keep_their_sort_list_size) {
  ASSERT_EQ(1460, SlstPolyIdCount(LID_NSANITYBEACH));
  ASSERT_EQ(2610, SlstPolyIdCount(LID_TITLE));
  ASSERT_EQ(2610, SlstPolyIdCount(LID_INTRO));
}

UTEST(slst, custom_levels_list_as_many_polygons_as_a_delta_can_index) {
  /* a remove node holds a list index + 1 in 12 bits (SlstUpdate), so the
     last place it can reach is 4094 */
  ASSERT_EQ(4095, SlstPolyIdCount(LID_TEST));
  ASSERT_EQ(SLST_CUSTOM_POLY_IDS, SlstPolyIdCount(LID_TEST));
}
