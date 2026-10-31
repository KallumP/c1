/*
 * the level end screen's box total in custom levels (pc)
 */
#include "levelend.h"
#include "ns.h"

/*
 * the box total an object of exec should start with when the level with id
 * lid (as gool keeps it, shifted 8 left) has ended. the level end
 * screen only knows the totals of the game's own levels, so for a custom
 * level (the test level id) it gets the total from the level's nsd; returns
 * 0, leaving total as it is, for anything else
 */
int LevelEndBoxTotal(int exec, uint32_t lid, uint32_t *total) {
  if (exec != LEVELEND_EXEC_GAMOC || lid != (LID_TEST << 8)) { return 0; }
  *total = NSCustomBoxTotal() << 8;
  return 1;
}
