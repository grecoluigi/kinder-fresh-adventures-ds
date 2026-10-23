#include "completion.h"
#include "game_save.h"
int completion_begin(HighscoreUI *ui,unsigned world,int32_t score)
{
    world &= 3;
    int rank=persistence_qualify(&game_save_state()->scores[world],score);
    if(rank>=0)highscore_ui_begin_name(ui,world,rank);
    else highscore_ui_init(ui,world);
    return rank;
}
bool completion_confirm(HighscoreUI *ui)
{
    unsigned world=ui->world;
    if(!highscore_ui_commit_name(ui,&game_save_state()->scores[world]))return false;
    bool saved=game_save_flush_highscores(world);
    highscore_ui_init(ui,world);
    return saved;
}
