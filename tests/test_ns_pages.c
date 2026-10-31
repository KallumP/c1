#include "utest.h"
#include "ns.h"

/* ns.c references these from the rest of the game */
ns_subsystem subsys[21];
int use_cd = 0;
entry *cur_zone;
eid_t insts[8];
int TitleLoading(lid_t lid, uint8_t *image_data, nsd *nsd) { return 0; }

extern ns_struct ns;

UTEST(ns_files, custom_level_loads_from_its_path) {
  NSSetCustomLevel("build/levels/mock");
  ASSERT_STREQ("build/levels/mock.nsd", NSGetFilename(0, LID_TEST));
  ASSERT_STREQ("build/levels/mock.nsf", NSGetFilename(1, LID_TEST));
  NSSetCustomLevel("");
}

UTEST(ns_files, a_long_custom_level_path_isnt_cut_short) {
  char path[300], nsd[310];

  memset(path, 'a', 299);
  path[299] = 0;
  snprintf(nsd, sizeof(nsd), "%s.nsd", path);
  NSSetCustomLevel(path);
  ASSERT_STREQ(nsd, NSGetFilename(0, LID_TEST));
  NSSetCustomLevel("");
}

UTEST(ns_files, other_levels_still_load_from_streams) {
  NSSetCustomLevel("build/levels/mock");
  ASSERT_STREQ("./streams/s0000009.nsd", NSGetFilename(0, LID_NSANITYBEACH));
  NSSetCustomLevel("");
  ASSERT_STREQ("./streams/s0000001.nsf", NSGetFilename(1, LID_TEST));
}

static nsd_ldat ldat; /* big (its loading image), so not on the stack */

UTEST(ns_box_total, a_custom_level_keeps_its_box_total) {
  NSSetCustomLevel("build/levels/mock");
  ldat.box_total = 58;
  NSKeepBoxTotal(LID_TEST, &ldat);
  ASSERT_EQ(58, NSCustomBoxTotal());
  NSSetCustomLevel("");
  NSKeepBoxTotal(LID_TEST, &ldat);
}

UTEST(ns_box_total, the_total_stays_while_the_level_end_screen_loads) {
  NSSetCustomLevel("build/levels/mock");
  ldat.box_total = 58;
  NSKeepBoxTotal(LID_TEST, &ldat);
  ldat.box_total = 0;
  NSKeepBoxTotal(LID_NSANITYBEACH, &ldat); /* another level's nsd, such as the end screen's */
  ASSERT_EQ(58, NSCustomBoxTotal());
  NSSetCustomLevel("");
  NSKeepBoxTotal(LID_TEST, &ldat);
}

UTEST(ns_box_total, the_games_own_test_level_has_none) {
  NSSetCustomLevel("");
  ldat.box_total = 7;
  NSKeepBoxTotal(LID_TEST, &ldat);
  ASSERT_EQ(0, NSCustomBoxTotal());
}

static nsd probe_nsd;
static nsd_pte probe_table[3];
static nsd_pte *probe_buckets[NSD_PTB_COUNT];

/* a page table of three entries, all in the bucket the eids hash to (0) */
static void set_probe_table() {
  int i;

  for (i=0;i<3;i++) {
    probe_table[i].pgid = i;
    probe_table[i].eid = 0x10 + i;
  }
  probe_nsd.page_table_size = 3;
  probe_buckets[0] = probe_table;
  ns.nsd = &probe_nsd;
  ns.page_table = probe_table;
  ns.pte_buckets = probe_buckets;
}

UTEST(ns_probe, finds_an_entry_in_the_table) {
  set_probe_table();
  ASSERT_EQ(&probe_table[1], NSProbeSafe(0x11));
}

UTEST(ns_probe, finds_the_last_entry_in_the_table) {
  set_probe_table();
  ASSERT_EQ(&probe_table[2], NSProbeSafe(0x12));
}

UTEST(ns_probe, an_entry_not_in_the_table_is_an_invalid_ref) {
  set_probe_table();
  ASSERT_EQ((nsd_pte*)ERROR_INVALID_REF, NSProbeSafe(0x13));
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
