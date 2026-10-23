#include "ui_feedback.h"
void ui_feedback_init(UIFeedback *state){state->focus[0]=state->focus[1]=-1;state->latched[0]=state->latched[1]=0;}
void ui_feedback_reset(UIFeedback *state,bool scores){state->focus[scores?1:0]=-1;state->latched[scores?1:0]=0;}
int ui_feedback_attenuation(int percentage){
    /* Reject out-of-domain persisted values safely before the native integer
     * multiply. Normal UI values retain signed division's truncation to zero. */
    if(percentage<0)percentage=0;
    if(percentage>100)percentage=100;
    return ((percentage-100)*40)/100;
}
unsigned ui_feedback_music_volume(int percentage){
    /* Native4099bf..4099e7 derives menu music attenuation from Option.ini20.
     * Maxmod/music mixer amplitude is0..127; round the original dB curve. */
    static const uint8_t amplitudes[41]={127,113,101,90,80,71,64,57,51,45,40,36,32,28,25,23,20,18,16,14,13,11,10,9,8,7,6,6,5,5,4,4,3,3,3,2,2,2,2,1,1};
    return amplitudes[-ui_feedback_attenuation(percentage)];
}
void ui_feedback_tick(UIFeedback *state,bool scores,int focus,int percentage,UIFeedbackPlay play,void *context){
    unsigned surface=scores?1:0;int previous=state->focus[surface];state->focus[surface]=focus;
    if(previous!=focus)state->latched[surface]=0;
    if(focus<0||focus>=4)return;
    bool latched=state->latched[surface]!=0;
    /* Released viewer403263 uses !latched OR percentage<=0; the main menu
     *40473f uses !latched AND percentage>0. Preserve that explicit difference. */
    bool trigger=scores?(!latched||percentage<=0):(!latched&&percentage>0);
    static const unsigned channels[4]={1,4,2,3};
    if(trigger){state->latched[surface]=1;if(play)play(channels[focus],0x4553cc,0,ui_feedback_attenuation(percentage),context);}
}
