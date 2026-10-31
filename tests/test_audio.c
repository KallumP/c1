#include "utest.h"
#include "audio.h"

/* the master volume is 0 to 0x7F, as the ps1's SsSetMVol takes (SwSetMVol
   amplifies by vol / 0x7F); fades run fade_vol from 0 to 0x3FFF */

UTEST(audio, a_full_fade_is_full_volume) {
  ASSERT_EQ(0x7Fu, AudioFadeMVol(0x3FFF)); /* as AudioInit sets it */
}

UTEST(audio, a_faded_out_volume_is_silent) {
  ASSERT_EQ(0u, AudioFadeMVol(0));
}

UTEST(audio, a_fade_scales_the_volume) {
  ASSERT_EQ(0x40u, AudioFadeMVol(0x2000));
}
