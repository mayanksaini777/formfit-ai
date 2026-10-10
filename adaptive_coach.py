"""FORMFIT Phase 5 - adaptive coaching and session timeline.
Additive only: learns repeated issues during the current session, detects
improvement/decline across completed reps, and creates concise timeline events.
It never changes pose_engine thresholds or rep counting.
"""
import time
from collections import Counter, deque

class AdaptiveCoach:
    def __init__(self, max_events=120, max_sessions=10):
        self.max_events=max(30,int(max_events)); self.max_sessions=max(3,int(max_sessions)); self.reset()
    def reset(self):
        self.exercise=None; self.started_at=time.time(); self.events=deque(maxlen=self.max_events)
        self.issue_counts=Counter(); self.issue_streak=Counter(); self.rep_scores=[]; self.rep_labels=[]
        self.last_rep_count=0; self.last_avg=None; self.session_number=1
    def start(self, exercise, session_number=1):
        self.reset(); self.exercise=exercise; self.session_number=int(session_number)
        self._event('SESSION_START', 'Session started', 'Build a steady, controlled first rep.', 'info')
    def update(self, exercise, result, movement, coaching, rep_quality):
        if exercise!=self.exercise: self.start(exercise, self.session_number)
        primary=(coaching or {}).get('primary_issue') or {}
        code=primary.get('code')
        if code:
            self.issue_counts[code]+=1; self.issue_streak[code]+=1
            for k in list(self.issue_streak):
                if k!=code: self.issue_streak[k]=0
            if self.issue_streak[code] in (3,8):
                self._event('REPEATED_ISSUE', primary.get('title','Repeated issue'), primary.get('cue',''), 'warning', code)
        last=(rep_quality or {}).get('last_rep')
        if last and int(last.get('rep',0))>self.last_rep_count:
            self.last_rep_count=int(last['rep']); score=int(last.get('quality_score',0)); self.rep_scores.append(score); self.rep_labels.append(last.get('label'))
            trend=self._trend()
            if trend=='UP': self._event('REP_IMPROVING', f"Rep {self.last_rep_count} improved", 'Keep the same controlled technique.', 'success')
            elif trend=='DOWN': self._event('REP_DROPPING', f"Rep {self.last_rep_count} dropped", self._best_correction(), 'warning')
        avg=(rep_quality or {}).get('average_quality')
        self.last_avg=avg if avg is not None else self.last_avg
        return self.snapshot(rep_quality)
    def _trend(self):
        if len(self.rep_scores)<3: return 'STABLE'
        a=sum(self.rep_scores[-3:-1])/2; b=self.rep_scores[-1]
        if b>=a+5:return 'UP'
        if b<=a-5:return 'DOWN'
        return 'STABLE'
    def _best_correction(self):
        if not self.issue_counts:return 'Slow down and focus on the highlighted target.'
        code,_=self.issue_counts.most_common(1)[0]
        cues={'LOW_ROM':'Use a comfortable full range.','TOO_FAST':'Slow the rep and control both directions.','KNEE_ALIGNMENT':'Keep the knee tracking with the foot.','ELBOW_ALIGNMENT':'Keep the elbow controlled.','BACK_POSITION':'Keep your torso stable.','SHOULDER_POSITION':'Keep the shoulder relaxed and controlled.','FORM_LOW':'Reset your position and follow the highlighted correction.'}
        return cues.get(code,'Focus on the most frequent highlighted correction.')
    def _event(self,kind,title,message,severity,code=None):
        self.events.append({'type':kind,'title':title,'message':message,'severity':severity,'code':code,'timestamp':int(time.time())})
    def snapshot(self, rep_quality=None):
        scores=self.rep_scores
        first=round(sum(scores[:min(3,len(scores))])/max(1,min(3,len(scores)))) if scores else None
        recent=round(sum(scores[-3:])/max(1,min(3,len(scores)))) if scores else None
        improvement=None if first is None or recent is None else recent-first
        return {'exercise':self.exercise,'session_number':self.session_number,'duration_s':round(max(0,time.time()-self.started_at),1),'rep_scores':scores[-20:],'trend':self._trend(),'improvement_points':improvement,'repeated_issues':[{'code':c,'count':n} for c,n in self.issue_counts.most_common(5)],'events':list(self.events),'adaptive_cue':self._best_correction() if self.issue_counts else 'Keep the same controlled technique.','rep_quality':rep_quality or {}}
