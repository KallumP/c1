#ifndef _PC_LEVELEND_H_
#define _PC_LEVELEND_H_

#include "common.h"

/* the level end screen object's exec slot; it looks up the box total of the
   level that ended by its id (from a list of the game's own levels) and keeps
   it in memory[6] */
#define LEVELEND_EXEC_GAMOC  52
#define LEVELEND_BOX_TOTAL   6

extern int LevelEndBoxTotal(int exec, uint32_t lid, uint32_t *total);

#endif /* _PC_LEVELEND_H_ */
