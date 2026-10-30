#include "utest.h"
#include "ns.h"

/* ns.c references these from the rest of the game */
ns_subsystem subsys[21];
int use_cd = 0;
entry *cur_zone;
eid_t insts[8];
int TitleLoading(lid_t lid, uint8_t *image_data, nsd *nsd) { return 0; }

extern ns_struct ns;

UTEST(ns_files, custom_level_loads_from_custom_levels) {
  NSSetCustomLevel("mock");
  ASSERT_STREQ("./custom_levels/mock.nsd", NSGetFilename(0, LID_TEST));
  ASSERT_STREQ("./custom_levels/mock.nsf", NSGetFilename(1, LID_TEST));
  NSSetCustomLevel("");
}

UTEST(ns_files, other_levels_still_load_from_streams) {
  NSSetCustomLevel("mock");
  ASSERT_STREQ("./streams/s0000009.nsd", NSGetFilename(0, LID_NSANITYBEACH));
  NSSetCustomLevel("");
  ASSERT_STREQ("./streams/s0000001.nsf", NSGetFilename(1, LID_TEST));
}

/* leave junk where the next call's locals will go, as the game's own calls would */
static __attribute__((noinline)) void FillStackWithJunk() {
  volatile uint32_t junk[256];
  int i;
  for (i=0;i<256;i++)
    junk[i] = 0x7F7F7F7F;
}

UTEST(ns_pages, no_entries_need_no_pages) {
  FillStackWithJunk();
  ASSERT_EQ(0, NSCountAvailablePages2(0, 0));
}

UTEST(ns_pages, entry_in_an_unloaded_page_needs_one_page) {
  page_struct *page_map[2];
  page_struct **page_map_prev;
  nsd_pte pte;
  entry_ref ref, *list[1];
  int count;

  page_map[1] = (page_struct*)NULL_PAGE; /* page not loaded */
  pte.pgid = 3; /* page 1 */
  ref.pte = &pte;
  list[0] = &ref;
  page_map_prev = ns.page_map;
  ns.page_map = page_map;
  FillStackWithJunk();
  count = NSCountAvailablePages2(list, 1);
  ns.page_map = page_map_prev;
  ASSERT_EQ(1, count);
}
