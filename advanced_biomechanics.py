"""Advanced, explainable biomechanics checks for FormFit.

Designed for a single RGB camera + MediaPipe landmarks.  It deliberately
checks only quantities that can be observed reasonably from those landmarks.
Each issue includes an anatomical scope so the UI can color only the faulty
segment instead of turning the whole skeleton red.
"""
from __future__ import annotations
import math

L_SH,R_SH,L_EL,R_EL,L_WR,R_WR = 11,12,13,14,15,16
L_HIP,R_HIP,L_KNEE,R_KNEE,L_ANK,R_ANK = 23,24,25,26,27,28


def _xy(lm,i):
    try: return float(lm[i].x), float(lm[i].y)
    except Exception: return None

def _vis(lm,i,t=.45):
    try: return float(getattr(lm[i],'visibility',0)) >= t
    except Exception: return False

def _angle(lm,a,b,c):
    p,q,r=_xy(lm,a),_xy(lm,b),_xy(lm,c)
    if not all((p,q,r)): return None
    v=(p[0]-q[0],p[1]-q[1]); w=(r[0]-q[0],r[1]-q[1])
    den=math.hypot(*v)*math.hypot(*w)
    if den < 1e-8: return None
    z=max(-1,min(1,(v[0]*w[0]+v[1]*w[1])/den))
    return math.degrees(math.acos(z))

def _dist(lm,a,b):
    p,q=_xy(lm,a),_xy(lm,b)
    return math.hypot(p[0]-q[0],p[1]-q[1]) if p and q else None

def _lean(lm,s,h):
    p,q=_xy(lm,s),_xy(lm,h)
    if not p or not q: return None
    return math.degrees(math.atan2(abs(p[0]-q[0]),max(abs(p[1]-q[1]),1e-6)))

def issue(code,title,detail,segments,priority='high',recommendation=''):
    return {'code':code,'title':title,'detail':detail,'segments':list(segments),
            'priority':priority,'recommendation':recommendation}

def _arms(lm):
    out=[]
    for side,s,e,w,h in [('left',L_SH,L_EL,L_WR,L_HIP),('right',R_SH,R_EL,R_WR,R_HIP)]:
        if not all(_vis(lm,i) for i in (s,e,w,h)): continue
        torso=max(_dist(lm,s,h) or .05,.05)
        ep,sp,wp=_xy(lm,e),_xy(lm,s),_xy(lm,w)
        out.append((side,s,e,w,torso,ep,sp,wp,_angle(lm,s,e,w)))
    return out

def analyze(ex,lm):
    """Return (issues, rep_blocked, scope) for an exercise.
    scope is 'full' only when the exercise setup itself is globally invalid.
    """
    ex=str(ex or '').lower()
    issues=[]; block=False; scope='segment'
    arms=_arms(lm)
    def add(*args, **kwargs): issues.append(issue(*args, **kwargs))

    # ---- CURLS: elbow must remain below shoulder and upper arm controlled ----
    if ex in {'bicep_curls','hammer_curl'}:
        usable=0
        for side,s,e,w,torso,ep,sp,wp,ea in arms:
            usable += 1
            if ep[1] < sp[1]-0.10*torso:
                add(f'advanced_curl_elbow_high_{side}','ELBOW TOO HIGH',
                    f'{side.title()} elbow is above the shoulder line for a curl.',
                    [f'{side}_upper_arm',f'{side}_forearm'],'high',
                    'Keep the upper arm down and curl without lifting the elbow.')
                block=True
            if wp[1] < sp[1]-0.20*torso:
                add(f'advanced_curl_hand_high_{side}','HAND TOO HIGH',
                    f'{side.title()} hand has moved above the shoulder beyond a curl range.',
                    [f'{side}_forearm'],'high',
                    'Lower the hand; the curl should finish near the shoulder, not overhead.')
            drift=abs(ep[0]-sp[0])/torso
            if drift > .60:
                add(f'advanced_curl_elbow_drift_{side}','ELBOW DRIFT',
                    f'{side.title()} upper arm is leaving the intended curl path.',
                    [f'{side}_upper_arm',f'{side}_forearm'],'high',
                    'Keep the elbow close to the torso and move mainly at the elbow.')
        if usable==0:
            block=True

    # ---- PUSH-UP: global setup + local elbow/body line faults ----
    elif ex in {'push_up','push_up_wide_grip','push_up_diamond','incline_push_up','decline_push_up'}:
        if all(_vis(lm,i) for i in (L_SH,L_HIP,L_ANK,L_WR)):
            s,h,a=_xy(lm,L_SH),_xy(lm,L_HIP),_xy(lm,L_ANK)
            torso=math.hypot(h[0]-s[0],h[1]-s[1])
            if torso>0 and abs(h[1]-s[1])/torso>.78:
                add('advanced_pushup_standing','WRONG EXERCISE POSITION',
                    'Body is upright instead of the required push-up setup.',
                    ['full'],'high','Get into a horizontal push-up position.')
                block=True; scope='full'
        # Side-view elbow flare is observable; front view is treated as unknown.
        for side,s,e,w,torso,ep,sp,wp,ea in arms:
            if ea is None: continue
            if ea < 55 or ea > 150:
                add(f'advanced_pushup_elbow_{side}','CONTROL ELBOW ANGLE',
                    f'{side.title()} elbow angle is outside the selected push-up movement range.',
                    [f'{side}_upper_arm',f'{side}_forearm'],'medium',
                    'Use a controlled elbow path and keep the shoulder stable.')
        if all(_vis(lm,i) for i in (L_SH,L_HIP,L_ANK)):
            body=_angle(lm,L_SH,L_HIP,L_ANK)
            if body is not None and body < 155:
                add('advanced_pushup_body_line','KEEP BODY STRAIGHT',
                    'Hips are sagging or piking relative to the shoulders and ankles.',
                    ['torso','left_upper_leg','right_upper_leg'],'high',
                    'Brace the core and keep shoulders, hips and ankles aligned.')
                block=True

    # ---- SQUAT / LUNGE: knee tracking + torso + bilateral symmetry ----
    elif ex in {'squat','lunges','reverse_lunge','step_up'}:
        visible_knees=0
        for side,h,k,a,s in [('left',L_HIP,L_KNEE,L_ANK,L_SH),('right',R_HIP,R_KNEE,R_ANK,R_SH)]:
            if not all(_vis(lm,i) for i in (h,k,a,s)): continue
            visible_knees += 1
            kp,ap=_xy(lm,k),_xy(lm,a)
            if abs(kp[0]-ap[0])>.13:
                add(f'advanced_knee_track_{side}','KNEE TRACKING',
                    f'{side.title()} knee is drifting away from the foot.',
                    [f'{side}_upper_leg',f'{side}_lower_leg'],'high',
                    'Track the knee over the middle of the foot.')
                block=True
            lean=_lean(lm,s,h)
            if lean is not None and lean>48:
                add(f'advanced_torso_lean_{side}','EXCESSIVE TORSO LEAN',
                    f'{side.title()} side shows excessive torso folding.',
                    ['torso',f'{side}_upper_leg'],'high',
                    'Brace the core and keep a controlled torso angle.')
        if visible_knees==0: block=True

    # ---- SHOULDER PRESS / RAISE: independent arm checks + torso stability ----
    elif ex in {'shoulder_press','lateral_shoulder_raises','front_raise'}:
        for side,s,e,w,torso,ep,sp,wp,ea in arms:
            # Shoulder raises: elbow/wrist should not become a curl-like folded arm.
            if ex in {'lateral_shoulder_raises','front_raise'} and ea is not None and ea<115:
                add(f'advanced_raise_bent_{side}','KEEP ARM CONTROLLED',
                    f'{side.title()} arm is excessively bent during the raise.',
                    [f'{side}_upper_arm',f'{side}_forearm'],'medium',
                    'Maintain the intended raise path with a controlled elbow.')
                block=True
            if ex=='shoulder_press' and ep[1] < sp[1]-0.12*torso and wp[1] < sp[1]-0.20*torso:
                # This is not an error at the top of a press; it is valid only
                # after the movement has reached the press phase. Mark as a cue,
                # not a hard rep block, to avoid punishing legitimate lockout.
                add(f'advanced_press_overhead_{side}','CHECK PRESS PATH',
                    f'{side.title()} hand is overhead; verify a vertical press path.',
                    [f'{side}_upper_arm',f'{side}_forearm'],'low',
                    'Keep wrist stacked over the elbow and avoid drifting sideways.','')
        if ex=='shoulder_press':
            leans=[x for x in (_lean(lm,L_SH,L_HIP),_lean(lm,R_SH,R_HIP)) if x is not None]
            if leans and max(leans)>28:
                add('advanced_press_lean','DO NOT LEAN BACK',
                    'Torso is leaning excessively during the press.',
                    ['torso'],'high','Brace the core and keep ribs stacked over the hips.')
                block=True

    # ---- DEADLIFT / ROW: hinge and spine proxies ----
    elif ex in {'deadlift','dumbbell_row'}:
        leans=[x for x in (_lean(lm,L_SH,L_HIP),_lean(lm,R_SH,R_HIP)) if x is not None]
        if ex=='dumbbell_row' and leans and max(leans)<18:
            add('advanced_row_hinge','INSUFFICIENT HIP HINGE',
                'Torso is too upright for a supported row pattern.',
                ['torso','upper_legs'],'high','Hinge at the hips and keep the spine neutral.')
            block=True
        if ex=='deadlift' and leans and max(leans)<8:
            # Standing is valid only as the start/end; do not block the rep here.
            pass
        # Knee alignment remains local.
        for side,h,k,a in [('left',L_HIP,L_KNEE,L_ANK),('right',R_HIP,R_KNEE,R_ANK)]:
            if all(_vis(lm,i) for i in (h,k,a)):
                kp,ap=_xy(lm,k),_xy(lm,a)
                if abs(kp[0]-ap[0])>.15:
                    add(f'advanced_deadlift_knee_{side}','KNEE TRACKING',
                        f'{side.title()} knee is drifting away from the foot.',
                        [f'{side}_upper_leg',f'{side}_lower_leg'],'high','Keep the knee tracking with the foot.')
                    block=True

    return issues, block, scope
