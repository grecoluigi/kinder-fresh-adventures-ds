#include <nds.h>
#include "menu.h"
#include "world.h"
#include "hud.h"
#include "hud_native_bridge.h"
#include "player.h"
#include <filesystem.h>
#include "menu_graphics.h"
#include "audio.h"
#include "performance.h"
#include "storage_profile.h"
#include "game_clock.h"
#include "native_rng.h"
#include "frame_transfer.h"
#include "scene.h"
#include "game_save.h"
#include "highscore_ui.h"
#include "completion.h"
#include "credits.h"
#include "ui_feedback.h"
#include "sound_events.h"

#include "native_scene.h"
#include "gpu_prefix.h"
#include <nds/arm9/keyboard.h>
#include <nds/system_counter.h>

static uint16_t *top_pixels, *bottom_pixels;
static bool gpu_mode;
static uint32_t render_audio_last_tick;
static volatile uint32_t render_audio_services;
static void service_render_audio(void){
    uint32_t now=(uint32_t)systemCounterGetTicks();
    if(now-render_audio_last_tick<BUS_CLOCK/64u/100u)return;
    render_audio_last_tick=now;audio_poll();render_audio_services++;
}

/* Transitional mapping: keep E/F/G's existing foreground below0x06018000.
 * C uses0x06020000; its final64KiB holds the migrated H/I source-row cache.
 * Native scenery integration will move C to0 and E to extended palettes. */
static NativeBottomSurface hud_surface;
#if KF_DEBUG
static uint16_t diagnostic_pixels[256*27] __attribute__((aligned(32)));
#endif
static void hud_cache_for_surface(void){
 if(!gpu_mode)return;
 {}
}
static __attribute__((noipa)) void transfer_surface(uint16_t *destination,const uint16_t *source){
 if(destination==bottom_pixels&&hud_native_state()){
  /* Invalidate before the mapping changes; no stale H/I/C source may survive. */
  {}
  if(native_bottom_surface_rgb(&hud_surface,source,49152))hud_cache_for_surface();
  return;
 }
 frame_transfer(destination,source);
}
static __attribute__((noipa)) void publish_hud(const uint16_t *source){
 const NativeBottom *state=hud_native_state();
 if(!state){frame_transfer(bottom_pixels,source);return;}
 bool changed=hud_surface.mode!=NATIVE_BOTTOM_INDEXED;
 if(changed){}
 if(native_bottom_surface_hud(&hud_surface,state,(const uint8_t *)source,49152)&&changed)hud_cache_for_surface();
}
static bool keyboard_backdrop_ready;
static uint16_t keyboard_backdrop_palette[128];
static void preserve_keyboard_backdrop(void){
 const NativeBottom *hud=hud_native_state();keyboard_backdrop_ready=false;
 if(!hud||!hud->ready||!hud->background||(REG_DISPCNT&DISPLAY_BG1_ACTIVE))return;
 /* Freeze has released main BG1. Preserve the bare level crop before
  * world_close frees it; the keyboard owns the lower64KiB of bank C. */
 swiWaitForVBlank();
 for(int i=4;i<8;i++)bgHide(i);
 vramSetBankH(VRAM_H_LCD);vramSetBankI(VRAM_I_LCD);vramSetBankC(VRAM_C_SUB_BG);
 dmaFillWords(0,(void *)0x06200000,128u*1024u);
 volatile uint16_t *dest=(volatile uint16_t *)0x06210000;
 for(unsigned i=0;i<24576;i++)dest[i]=(uint16_t)(hud->background[i*2]|(unsigned)hud->background[i*2+1]<<8);
 for(unsigned i=0;i<128;i++)keyboard_backdrop_palette[i]=hud->palette[128+i];
 hud_surface.scenery_epoch++;keyboard_backdrop_ready=true;
}
static void prepare_bottom_keyboard(void){
 if(!hud_native_state())return;
 {}swiWaitForVBlank();
 for(int i=4;i<8;i++)bgHide(i);
 vramSetBankH(VRAM_H_LCD);vramSetBankI(VRAM_I_LCD);vramSetBankC(VRAM_C_SUB_BG);
 /* C still holds 8bpp scenery tiles; the keyboard writes only its own map
  * rows, so clear the bank or the rows above it show tiles as map entries. */
 dmaFillWords(0,(void *)0x06200000,keyboard_backdrop_ready?64u*1024u:128u*1024u);
 hud_surface.scenery_epoch++;hud_surface.mode=NATIVE_BOTTOM_RGB;hud_surface.visible_rgb=false;
 hud_surface.background=keyboard_backdrop_ready?bgInitSub(3,BgType_Bmp8,BgSize_B8_256x256,4,0):bgInitSub(3,BgType_Bmp16,BgSize_B16_256x256,0,0);
 bgSetPriority(hud_surface.background,3);bgWrapOff(hud_surface.background);bgHide(hud_surface.background);bgUpdate();hud_cache_for_surface();
}
static void finish_bottom_keyboard(void){
 if(hud_native_state()){
  hud_surface.mode=NATIVE_BOTTOM_RGB;hud_surface.visible_rgb=false;
  hud_surface.background=bgInitSub(3,BgType_Bmp16,BgSize_B16_256x256,0,0);bgHide(hud_surface.background);bgUpdate();
 }
}
#if KF_DEBUG
static __attribute__((noipa)) void draw_bottom_diagnostics(unsigned reads,int state){
 const NativeBottom *hud=hud_native_state();
 if(!hud||hud_surface.mode!=NATIVE_BOTTOM_INDEXED){performance_draw(bottom_pixels,reads,state);return;}
 performance_draw(diagnostic_pixels,reads,state);
 /* Staging reserves indices123..127; these two diagnostic entries are never
  * used by the backdrop (128..255) or HUD patches (1..122). */
 BG_PALETTE_SUB[126]=0;BG_PALETTE_SUB[127]=32767;
 volatile uint16_t *dest=(volatile uint16_t *)bottom_pixels;
 for(unsigned i=0;i<256u*27u;i+=2){
  unsigned a=diagnostic_pixels[i]==0xffff?127:126,b=diagnostic_pixels[i+1]==0xffff?127:126;
  dest[i/2]=(uint16_t)(a|(b<<8));
 }
}
#endif

static void render_bottom_menu(void){
    const uint16_t *image=menu_graphics_pixels(menu_focus_index());
    if(image)transfer_surface(bottom_pixels,image);
}

/* Root menu uses the touch screen. During gameplay render_bottom_menu()
 * leaves the frozen top scene intact instead of clearing it. */
static void render_menu(void)
{
    frame_forget_foreground_transfer();
    gpu_prefix_hide();
    dmaFillHalfWords(0x8000,top_pixels,256u*192u*2u);
    render_bottom_menu();
}

static void play_menu_music(void){
    if(audio_play_menu())audio_set_volume(ui_feedback_music_volume(game_save_state()->options[20]));
}
static void play_ui_feedback(unsigned channel,unsigned key,unsigned repeat,int attenuation,void *context){
    (void)context;
    if(sound_play(channel,key,repeat))sound_channel_volume(channel,attenuation);
}
static void discard_keyboard_fifo(int character){(void)character;}

static uint16_t frame_pixels[256*192] __attribute__((aligned(32)));
static void freeze_top_scene(int parallax,unsigned background_x){
    (void)background_x;
    if(gpu_prefix_native_freeze(frame_pixels))return;
    if(gpu_prefix_is_visible()&&gpu_prefix_snapshot_frame(frame_pixels)){
        swiWaitForVBlank();gpu_prefix_hide();transfer_surface(top_pixels,frame_pixels);
        bgHide(parallax);bgUpdate();
    }
}

int main(void)
{
    videoSetModeSub(MODE_5_2D);
    gpu_mode=gpu_prefix_init();
    if(!gpu_mode){consoleDemoInit();printf("Graphics initialization failed.\n");for(;;)swiWaitForVBlank();}
    hud_native_enable(gpu_mode);
    videoSetMode(gpu_mode?MODE_5_3D:MODE_5_2D);
    if(!gpu_mode){vramSetBankA(VRAM_A_MAIN_BG);vramSetBankB(VRAM_B_MAIN_BG);}
    vramSetBankC(VRAM_C_SUB_BG);
    /* D retains parallax. GPU mode uses A/B textures, E/F/G foreground,
     * and48KiB LCDC H/I rows. Allocation failure retains the bitmap backend. */
    vramSetBankD(VRAM_D_MAIN_BG_0x06040000);
    vramSetBankE(gpu_mode?VRAM_E_MAIN_BG:VRAM_E_LCD);
    vramSetBankF(gpu_mode?VRAM_F_MAIN_BG_0x06010000:VRAM_F_LCD);
    vramSetBankG(gpu_mode?VRAM_G_MAIN_BG_0x06014000:VRAM_G_LCD);
    vramSetBankH(VRAM_H_LCD);vramSetBankI(VRAM_I_LCD);
    scene_set_service_callback(service_render_audio);
    {}
    scene_set_hardware_background(BG_BMP_RAM_MAIN(16),128u*1024u);
    /* Legacy visible bitmaps use192 of256 lines. Each bank's final64 lines supplies
     * 32KiB of sampled background cache, independent of the D..I source cache.
     * Transfers/clears touch only the visible192 lines. world_close invalidates
     * entries before the optional keyboard can repurpose sub-screen bank C. */
    if(gpu_mode){}
    else {}
    int top = bgInit(2, BgType_Bmp16, BgSize_B16_256x256, 0, 0);
    int bottom = bgInitSub(3, BgType_Bmp16, BgSize_B16_256x256, 0, 0);
    int parallax = bgInit(3,BgType_Bmp16,BgSize_B16_256x256,16,0);
    if(gpu_mode){bgInit(0,BgType_Text4bpp,BgSize_T_256x256,0,0);bgSetPriority(0,1);bgHide(0);}
    bgSetPriority(top,0);bgSetPriority(parallax,3);bgWrapOn(parallax);bgHide(parallax);
    bgUpdate();
    int front_base = 0, pending_base = -1;
    unsigned pending_background_x=0;bool pending_background=false;
    unsigned displayed_background_x=0;
    bool pending_prefix=false;uint32_t prepared_transfer_ticks=0;
    top_pixels = bgGetGfxPtr(top);
    bottom_pixels = bgGetGfxPtr(bottom);
    lcdMainOnTop();
    systemCounterSetup();
    native_rng_seed((uint32_t)systemCounterGetTicks());
    menu_init();
    bool bottom_visible = false;
    bool active_world = false;
    bool showing_scores = false;
    CreditsState credits={0};
    bool scores_on_bottom = true;
    int score_game_base = -1;
    HighscoreUI score_ui;
    bool name_keyboard=false;
    UIFeedback feedback;ui_feedback_init(&feedback);
    bool simulation_running = true;
#if KF_DEBUG
    bool diagnostics_visible = false;
#endif
    bool touch_switch_pending=false;
    GameClock game_clock;
    game_clock_reset(&game_clock,systemCounterGetTicks());
    game_save_init();
    bool files_ready = nitroFSInit(NULL);
    render_menu();
    if (files_ready) { audio_init(); play_menu_music(); }
    while (1) {
        swiWaitForVBlank();
        if (pending_base >= 0) {
            uint32_t transfer_start=performance_now();
            if(gpu_mode){
                if(pending_prefix&&gpu_prefix_pending_texture_only())frame_skip_foreground_transfer();
                else {gpu_prefix_hide();frame_transfer_foreground(top_pixels,frame_pixels);}
                gpu_prefix_publish(pending_prefix);
            }
            bgSetMapBase(top,(unsigned)pending_base);
            if(pending_background){bgSetScroll(parallax,(int)pending_background_x,0);bgShow(parallax);}else bgHide(parallax);
            displayed_background_x=pending_background_x;
            bgUpdate();
            front_base = pending_base;
            pending_base = -1;
            top_pixels = bgGetGfxPtr(top);
            if(gpu_mode)performance_transfer(prepared_transfer_ticks+performance_now()-transfer_start);

        }
        if(!active_world||!scene_hardware_background_active())bgHide(parallax);
        performance_frame();
        uint32_t phase_start = performance_now();
        audio_poll();render_audio_last_tick=(uint32_t)systemCounterGetTicks();
        performance_audio(performance_now() - phase_start);
        scanKeys();
        unsigned down = keysDown();
        if(credits.active){
            touch_switch_pending=false;
            bool changed=credits_step(&credits,(down&(KEY_A|KEY_TOUCH))!=0,(down&(KEY_B|KEY_START))!=0);
            if(!credits.active)render_menu();
            else if(changed){
                if(credits_draw(frame_pixels,credits.page))transfer_surface(bottom_pixels,frame_pixels);
                else{credits.active=false;render_menu();}
            }
            game_clock_reset(&game_clock,systemCounterGetTicks());
            continue;
        }
        if(showing_scores){
            touch_switch_pending=false;
            bool changed=false;
            if(name_keyboard){
                bool input_limit=highscore_ui_input_limit(&score_ui);
                int character=keyboardUpdate();
                /* Original scan-code alphabet renders letters in uppercase. */
                if(character>='a'&&character<='z')character-='a'-'A';
                if(character=='\b'||(down&KEY_B))changed=highscore_ui_backspace(&score_ui);
                else if(character>0&&character<256&&character!='\n')changed=highscore_ui_text(&score_ui,(uint8_t)character);
                if(character=='\n'||(down&(KEY_A|KEY_START))||(input_limit&&character!='\b'&&!(down&KEY_B))){highscore_ui_activate(&score_ui);changed=true;}
            }
            if(!name_keyboard&&(down&(KEY_UP|KEY_LEFT))){highscore_ui_move(&score_ui,-1);changed=true;}
            if(!name_keyboard&&(down&(KEY_DOWN|KEY_RIGHT))){highscore_ui_move(&score_ui,1);changed=true;}
            if(!name_keyboard&&(down&KEY_A)){highscore_ui_activate(&score_ui);changed=true;}
            if(!name_keyboard&&(down&(KEY_B|KEY_START))){highscore_ui_back(&score_ui);changed=true;}
            if(scores_on_bottom&&(down&KEY_TOUCH)){touchPosition position;touchRead(&position);changed=highscore_ui_touch(&score_ui,position.px,position.py)||changed;}
            if(!name_keyboard&&files_ready)ui_feedback_tick(&feedback,true,score_ui.focus,game_save_state()->options[21],play_ui_feedback,NULL);
            if(score_ui.exit_requested&&name_keyboard){
                completion_confirm(&score_ui);
                /* Failed name validation keeps the editor open. Storage failure
                 * still retains the confirmed table in RAM. */
                if(score_ui.editing_rank<0){
                    ui_feedback_reset(&feedback,true);
                    keyboardHide();keyboardExit();name_keyboard=false;finish_bottom_keyboard();if(!hud_native_state())bgShow(bottom);
                    scores_on_bottom=true;
                    /* Name entry temporarily uses top+touch keyboard. Restore
                     * the saved complete game frame when the table moves down. */
                    if(score_game_base>=0){
                        swiWaitForVBlank();
                        if(gpu_mode)gpu_prefix_restore_frame(top_pixels);
                        else{bgSetMapBase(top,(unsigned)score_game_base);bgUpdate();front_base=score_game_base;top_pixels=bgGetGfxPtr(top);}
                        score_game_base=-1;
                    }
                }else{score_ui.exit_requested=false;score_ui.commit_requested=false;}
                changed=true;
            }
            if(score_ui.exit_requested){
                highscore_ui_close();showing_scores=false;ui_feedback_reset(&feedback,false);
                if(active_world)render_bottom_menu();else render_menu();
            }else if(changed&&highscore_ui_draw(frame_pixels,&game_save_state()->scores[score_ui.world],&score_ui)){
                transfer_surface(scores_on_bottom?bottom_pixels:top_pixels,frame_pixels);
            }
            game_clock_reset(&game_clock,systemCounterGetTicks());
            continue;
        }
        bool redraw = false;
#if KF_DEBUG
        if (down & KEY_Y) { diagnostics_visible = !diagnostics_visible; storage_profile_enable(diagnostics_visible); redraw = true; }
#endif
        if (active_world && (down & KEY_START)) { bottom_visible = !bottom_visible; redraw = true; if(bottom_visible){freeze_top_scene(parallax,displayed_background_x);ui_feedback_reset(&feedback,false);} }
        if ((!active_world || bottom_visible) && (down & (KEY_UP | KEY_LEFT))) { menu_move(-1); redraw = true; }
        if ((!active_world || bottom_visible) && (down & (KEY_DOWN | KEY_RIGHT))) { menu_move(1); redraw = true; }
        if(!active_world||bottom_visible||!simulation_running)touch_switch_pending=false;
        if ((down & KEY_TOUCH) && active_world && !bottom_visible && simulation_running) {
            touchPosition position;touchRead(&position);
            if(hud_switch_hit(position.px,position.py))touch_switch_pending=true;
        }
        if ((down & KEY_TOUCH) && (!active_world || bottom_visible)) {
            touchPosition position;
            touchRead(&position);
            int hit = menu_hit_test(position.px, position.py);
            if (hit >= 0) { menu_focus(hit); menu_activate(); redraw = true; }
        }
        if ((!active_world || bottom_visible) && (down & KEY_A)) menu_activate();
        if(files_ready&&(!active_world||bottom_visible))ui_feedback_tick(&feedback,false,menu_focus_index(),game_save_state()->options[21],play_ui_feedback,NULL);
        MenuSelection selection = menu_take_selection();
        if (selection >= MENU_SELECTION_JUNGLE && selection <= MENU_SELECTION_FACTORY && files_ready) {
            static const unsigned native_world_ids[4] = {0, 3, 1, 2};
            freeze_top_scene(parallax,displayed_background_x);
            active_world = world_open(native_world_ids[(unsigned)selection]);
            simulation_running = true;
            if (active_world) audio_play_world(native_world_ids[(unsigned)selection]);
            bottom_visible = false;
            game_clock_reset(&game_clock,systemCounterGetTicks());
            redraw = true;
        } else if(selection==MENU_SELECTION_HIGHSCORES&&files_ready){
            if(highscore_ui_open(NULL)){
                highscore_ui_init(&score_ui,0);ui_feedback_reset(&feedback,true);
                showing_scores=true;scores_on_bottom=true;score_game_base=-1;
                if(highscore_ui_draw(frame_pixels,&game_save_state()->scores[score_ui.world],&score_ui)){
                    transfer_surface(scores_on_bottom?bottom_pixels:top_pixels,frame_pixels);
                }
                continue;
            }
            redraw=true;
        } else if (selection == MENU_SELECTION_EXIT) {
            freeze_top_scene(parallax,displayed_background_x);
            world_close();active_world=false;bottom_visible=false;touch_switch_pending=false;
            credits_begin(&credits);credits.active=files_ready&&credits_draw(frame_pixels,credits.page);
            play_menu_music();
            if(credits.active)transfer_surface(bottom_pixels,frame_pixels);
            else render_menu();
            game_clock_reset(&game_clock,systemCounterGetTicks());
            continue;
        }
        if (active_world) {
            if (!bottom_visible && simulation_running) {
                unsigned held = keysHeld(), original = 0;
                if (held & KEY_UP) original |= PLAYER_UP;
                if (held & KEY_DOWN) original |= PLAYER_DOWN;
                if (held & KEY_LEFT) original |= PLAYER_LEFT;
                if (held & KEY_RIGHT) original |= PLAYER_RIGHT;
                if (held & KEY_A) original |= PLAYER_JUMP;
                if (held & KEY_B) original |= PLAYER_SHOOT;
                if ((held & KEY_X)||touch_switch_pending) original |= PLAYER_SWITCH;
                phase_start = performance_now();
                game_clock_advance(&game_clock,systemCounterGetTicks());
                enum { MAX_CATCHUP_TICKS=8 };
                game_clock_limit_backlog(&game_clock,BUS_CLOCK/64,MAX_CATCHUP_TICKS);
                unsigned updates=0;
                for(unsigned steps=0;steps<MAX_CATCHUP_TICKS&&game_clock_take_tick(&game_clock,BUS_CLOCK/64);steps++) {
                    bool tick_ok=world_tick(original);touch_switch_pending=false;
                    if(!tick_ok){simulation_running=false;break;}
                    updates++;
                    if(world_finished()||world_transition_target()>=0)break;
                }
                performance_update(performance_now() - phase_start);
                performance_game_ticks(updates);
            }
            if (bottom_visible || !simulation_running) game_clock_reset(&game_clock,systemCounterGetTicks());
            int target=world_transition_target();
            if(target>=0){
                game_save_flush_tutorials();
                freeze_top_scene(parallax,displayed_background_x);
                active_world=world_open((unsigned)target);simulation_running=active_world;
                bottom_visible=false;
                if(active_world)audio_play_world((unsigned)target);
                else {play_menu_music();render_menu();}
                game_clock_reset(&game_clock,systemCounterGetTicks());redraw=true;
            }
            if(world_finished()) {
                unsigned result_world=world_result_world();
                int32_t result_score=world_result_score();
                freeze_top_scene(parallax,displayed_background_x);
                preserve_keyboard_backdrop();
                world_close();active_world=false;bottom_visible=false;
                play_menu_music();
                if(highscore_ui_open(NULL)){
                    completion_begin(&score_ui,result_world,result_score);ui_feedback_reset(&feedback,true);
                    showing_scores=true;scores_on_bottom=score_ui.editing_rank<0;score_game_base=-1;
                    if(score_ui.editing_rank>=0){
                        score_game_base=gpu_mode?0:(front_base?0:8);
                        if(gpu_mode){gpu_prefix_save_frame(frame_pixels);gpu_prefix_hide();}
                        else transfer_surface(BG_BMP_RAM_MAIN(score_game_base),top_pixels);
                        prepare_bottom_keyboard();bgHide(bottom);
                        Keyboard *keyboard=keyboardInit(NULL,0,BgType_Text4bpp,BgSize_T_256x512,20,0,false,true);
                        keyboard->scrollSpeed=0;keyboard->OnKeyPutc=discard_keyboard_fifo;
                        keyboardShow();
                        if(keyboard_backdrop_ready){
                            /* The SDK may replace the palette; its4bpp keys
                             * use the low entries, the backdrop uses128..255. */
                            for(unsigned i=0;i<128;i++)BG_PALETTE_SUB[128+i]=keyboard_backdrop_palette[i];
                            bgSetPriority(keyboard->background,0);bgShow(hud_surface.background);bgUpdate();
                        }
                        name_keyboard=true;if(hud_native_state())hud_surface.mode=NATIVE_BOTTOM_KEYBOARD;
                    }
                    if(highscore_ui_draw(frame_pixels,&game_save_state()->scores[score_ui.world],&score_ui))transfer_surface(scores_on_bottom?bottom_pixels:top_pixels,frame_pixels);
                }else render_menu();
                game_clock_reset(&game_clock,systemCounterGetTicks());continue;
            }
            /* HUD uses the shared WRAM framebuffer before preparing the next
             * top frame, which must survive until its next VBlank transfer. */
            if(!bottom_visible&&world_render_hud(frame_pixels,redraw))publish_hud(frame_pixels);
            if(!bottom_visible){
            phase_start = performance_now();
            bool rendered=world_render(frame_pixels);
            performance_render(performance_now() - phase_start);
            phase_start=performance_now();
            if (rendered) {
                performance_rendered_frame();
                int back_base = gpu_mode?0:(front_base?0:8);
                if(gpu_mode){
                    pending_prefix=gpu_prefix_prepare(frame_pixels);
                    if(!pending_prefix)rendered=false;
                }else transfer_surface(BG_BMP_RAM_MAIN(back_base),frame_pixels);
                if(rendered){
                pending_base = back_base;
                pending_background=scene_hardware_background_active();pending_background_x=scene_hardware_background_offset();
                }
            }
            if(gpu_mode)prepared_transfer_ticks=performance_now()-phase_start;
            else performance_transfer(performance_now() - phase_start);
            }
            if (redraw) {
                if(bottom_visible)render_bottom_menu();
            }
        } else if (redraw) render_menu();
#if KF_DEBUG
        if (diagnostics_visible) draw_bottom_diagnostics( active_world ? scene_render_stats()->read_calls : 0, active_world ? world_player_state() : 0);
#endif
    }
}
