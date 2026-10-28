#include <stdint.h>
#include "utest.h"
#include "pc/sound/formats/sf2.h"

/*
 * the soundfont is written by laying these structs out in memory, so each
 * one must be exactly the size the SF2 spec gives its record
 */

UTEST(sf2, modulator_is_2_bytes) {
  ASSERT_EQ(2, (int)sizeof(SFModulator));
}

UTEST(sf2, modulator_list_record_is_10_bytes) {
  ASSERT_EQ(10, (int)sizeof(sfModList));
  ASSERT_EQ(10, (int)sizeof(sfInstModList));
}

UTEST(sf2, generator_and_transform_are_2_bytes) {
  ASSERT_EQ(2, (int)sizeof(SFGenerator));
  ASSERT_EQ(2, (int)sizeof(SFTransform));
}

UTEST(sf2, other_records_have_spec_sizes) {
  ASSERT_EQ(38, (int)sizeof(sfPresetHeader));
  ASSERT_EQ(4, (int)sizeof(sfPresetBag));
  ASSERT_EQ(4, (int)sizeof(sfGenList));
  ASSERT_EQ(22, (int)sizeof(sfInst));
  ASSERT_EQ(4, (int)sizeof(sfInstBag));
  ASSERT_EQ(46, (int)sizeof(sfSample));
}
