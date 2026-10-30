#include <SDL2/SDL.h>
#include <unistd.h>
#ifdef CFLAGS_GUI
#define CIMGUI_DEFINE_ENUMS_AND_STRUCTS
#define CIMGUI_USE_SDL
#include "cimgui.h"
#include "cimgui_impl.h"
#endif

#include "ns.h"
#include "math.h"
#include "pad.h"
#include "pc/gfx/gl.h"
#include "pc/time.h"
#include "pc/settings.h"
#include "pc/replay.h"

#define WINDOW_WIDTH  1024
#define WINDOW_HEIGHT 768

SDL_Window *window = 0;
SDL_GLContext ogl_context;
uint8_t keys[SDL_NUM_SCANCODES] = { 0 }; /* indexed by SDL scancode */
int32_t mousex, mousey;
int mousel;

extern ns_struct ns;
extern int done;
extern eid_t insts[8];
extern page_struct texture_pages[16];
extern uint32_t seed_a;

void SDLInit() {
  SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO);
  SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24); /* for fix_model_draw_order */
  window = SDL_CreateWindow("c1",
    SDL_WINDOWPOS_UNDEFINED,
    SDL_WINDOWPOS_UNDEFINED,
    WINDOW_WIDTH, WINDOW_HEIGHT,
    SDL_WINDOW_OPENGL | SDL_WINDOW_SHOWN);
  ogl_context = SDL_GL_CreateContext(window);
#ifdef CFLAGS_GUI
  igCreateContext(0);
  ImGui_ImplSDL2_InitForOpenGL(window, ogl_context);
#endif
}

void SDLKill() {
#ifdef CFLAGS_GUI
  ImGui_ImplSDL2_Shutdown();
#endif
  SDL_GL_DeleteContext(ogl_context);
  SDL_DestroyWindow(window);
  SDL_Quit();
}

void SDLUpdate() {
  SDL_Event e;
  while (SDL_PollEvent(&e)) {
#ifdef CFLAGS_GUI
    ImGui_ImplSDL2_ProcessEvent(&e);
#endif
    switch (e.type) {
    case SDL_QUIT:
      done = 1;
      break;
    case SDL_KEYDOWN:
      keys[e.key.keysym.scancode] = 1;
      break;
    case SDL_KEYUP:
      keys[e.key.keysym.scancode] = 0;
      break;
    case SDL_MOUSEBUTTONUP:
    case SDL_MOUSEBUTTONDOWN:
      mousel = e.type == SDL_MOUSEBUTTONDOWN;
    case SDL_MOUSEMOTION:
      mousex = e.motion.x;
      mousey = e.motion.y;
      break;
    default:
      break;
    }
  }
#ifdef CFLAGS_GUI
  ImGui_ImplSDL2_NewFrame();
#endif
}

void SDLSwap() {
  SDL_GL_SwapWindow(window);
}

void SDLInput(gl_input *input) {
  int i;

  input->window.w = WINDOW_WIDTH;
  input->window.h = WINDOW_HEIGHT;
  input->mouse.x = mousex;
  input->mouse.y = mousey;
  input->click = 0 | (mousel ? 1 : 0);
  for (i=0;i<512;i++) {
    input->keys[i] = keys[i];
  }
}

/*
 * change to the directory containing streams/, so the game also works
 * when the executable is launched from elsewhere (e.g. build/c1.exe).
 * checks the working directory, the executable's directory, then its parent.
 */
static void FindDataDir() {
  char *base, path[1024];

  if (access("streams", 0) == 0) { return; }
  base = SDL_GetBasePath();
  if (!base) { return; }
  snprintf(path, sizeof(path), "%sstreams", base);
  if (access(path, 0) == 0) {
    chdir(base);
  }
  else {
    snprintf(path, sizeof(path), "%s../streams", base);
    if (access(path, 0) == 0) {
      snprintf(path, sizeof(path), "%s..", base);
      chdir(path);
    }
  }
  SDL_free(base);
}

lid_t boot_lid = LID_BOOTLEVEL; /* level the game starts in */

/*
 * boot into custom_levels/<boot_level> (as the test level) if boot_level is
 * set and the level's files are there
 */
static void InitBootLevel() {
  char path[128];

  if (!game_settings.boot_level[0]) { return; }
  snprintf(path, sizeof(path), "custom_levels/%s.nsd", game_settings.boot_level);
  if (access(path, 0) != 0) {
    fprintf(stderr, "no custom level %s, starting normally\n", path);
    return;
  }
  NSSetCustomLevel(game_settings.boot_level);
  boot_lid = LID_TEST;
}

/*
 * replay the newest recording if replay_inputs is on, otherwise record this
 * run to a new file in recorded_inputs (next to the executable), named by
 * its start time
 */
static void InitReplay() {
  char dir[1024], path[1024], *base;
  time_t now;

  base = SDL_GetBasePath();
  snprintf(dir, sizeof(dir), "%s%s", base ? base : "", REPLAY_DIR);
  SDL_free(base);
  if (game_settings.replay_inputs) {
    if (!ReplayNewestFile(dir, path, sizeof(path)))
      fprintf(stderr, "no recordings in %s to replay\n", dir);
    else if (ReplayStart(path, REPLAY_PLAY, boot_lid, seed_a)) {
      fprintf(stderr, "replaying %s\n", path);
      TimeSetSpeed(game_settings.replay_speed);
    }
    else
      fprintf(stderr, "could not replay %s\n", path);
    return;
  }
  if (!ReplayMakeDir(dir)) {
    fprintf(stderr, "could not make %s to record inputs\n", dir);
    return;
  }
  now = time(0);
  ReplayFileName(path, sizeof(path), dir, localtime(&now));
  if (!ReplayStart(path, REPLAY_RECORD, boot_lid, seed_a))
    fprintf(stderr, "could not open %s to record inputs\n", path);
}

int init() {
  gl_callbacks callbacks;
  int i;

  FindDataDir();
  PadInit(2); /* initialize 2 joypad structs */
  PadLoadBindings("controls.cfg"); /* keeps the default bindings if missing */
  SettingsLoad("settings.cfg"); /* keeps the default settings if missing */
  SetTicksElapsed(0);
  SDLInit();
  callbacks.pre_update = SDLUpdate;
  callbacks.post_update = SDLSwap;
  callbacks.ext_supported = (int (*)(const char*))SDL_GL_ExtensionSupported;
  callbacks.proc_addr = SDL_GL_GetProcAddress;
  callbacks.input = SDLInput;
  GLInit(&callbacks);
  sranda2();
  InitBootLevel();
  InitReplay();
  for (i=1;i<4;i++)
    insts[i] = EID_NONE;
  for (i=0;i<16;i++)
    texture_pages[i].eid = EID_NONE;
  ns.draw_skip_counter = 0;
  return SUCCESS;
}

int _kill() {
  ReplayStop();
  GLKill();
  SDLKill();
}
