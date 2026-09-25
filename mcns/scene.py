"""Local object/person instances and optical flow. No identity recognition."""
import threading
import time
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment


class Instances:
    def __init__(self):
        self.tracks={}; self.next_id=1

    def update(self, detections, stamp):
        self.tracks={k:v for k,v in self.tracks.items() if stamp-v['stamp']<.8}
        old=list(self.tracks.values()); assigned={}
        if old and detections:
            costs=np.full((len(old),len(detections)),100.)
            for i,a in enumerate(old):
                for j,b in enumerate(detections):
                    if a['label']==b['label']:
                        dt=stamp-a['stamp']; pred=np.array(a['center'])+np.array(a['velocity'])*dt
                        costs[i,j]=np.linalg.norm(pred-np.array(b['center']))
            rows,cols=linear_sum_assignment(costs)
            for i,j in zip(rows,cols):
                if costs[i,j]<.2:assigned[j]=old[i]
        result=[]
        for j,b in enumerate(detections):
            prev=assigned.get(j)
            if prev:
                identity=prev['id']; dt=stamp-prev['stamp']
                velocity=((np.array(b['center'])-prev['center'])/max(dt,.001)).tolist()
            else:
                identity=self.next_id; self.next_id+=1; velocity=[0.,0.]
            item={**b,'id':identity,'velocity':velocity,'stamp':stamp}
            self.tracks[identity]=item; result.append(item)
        return result


class SceneTracker:
    def __init__(self,camera,models,hz=8):
        self.camera=camera; self.path=Path(models)/'efficientdet_lite0.tflite'
        if not self.path.exists():raise FileNotFoundError('Run scripts/download_models.py for object detector')
        self.period=1/hz; self.stop=threading.Event();self.lock=threading.Lock()
        self.latest=None;self.error=None
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()

    def _run(self):
        try:
            import cv2
            import mediapipe as mp
            options=mp.tasks.vision.ObjectDetectorOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(self.path),delegate=mp.tasks.BaseOptions.Delegate.CPU),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,max_results=20,score_threshold=.4)
            tracks=Instances();previous=None;previous_stamp=None;last_seq=-1
            with mp.tasks.vision.ObjectDetector.create_from_options(options) as detector:
                while not self.stop.is_set():
                    begin=time.monotonic();info=self.camera.get()
                    if info is None or info[0]==last_seq:self.stop.wait(.01);continue
                    seq,stamp,frame=info;h,w=frame.shape[:2]
                    detection=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)))
                    objects=[]
                    for d in detection.detections:
                        box=d.bounding_box; category=d.categories[0]
                        x,y,x2,y2=np.clip([box.origin_x/w,box.origin_y/h,(box.origin_x+box.width)/w,(box.origin_y+box.height)/h],0,1)
                        objects.append({'label':category.category_name,'score':float(category.score),
                            'box':[float(x),float(y),float(x2),float(y2)],'center':[float((x+x2)/2),float((y+y2)/2)]})
                    objects=tracks.update(objects,stamp)
                    small=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(160,120))
                    flow=np.zeros((12,16,2),np.float32)
                    if previous is not None and 0<stamp-previous_stamp<.6:
                        dense=cv2.calcOpticalFlowFarneback(previous,small,None,.5,3,15,3,5,1.2,0)
                        dense/=np.array([160,120],np.float32)*(stamp-previous_stamp)
                        flow=cv2.resize(dense,(16,12),interpolation=cv2.INTER_AREA)
                    previous,previous_stamp=small,stamp
                    with self.lock:self.latest=(seq,stamp,{'objects':objects,'flow':flow.tolist(),'flow_shape':[16,12]})
                    last_seq=seq;self.stop.wait(max(0,self.period-(time.monotonic()-begin)))
        except Exception as exc:self.error=exc

    def get(self):
        if self.error:raise RuntimeError(f'Scene detection failed: {self.error}') from self.error
        with self.lock:return self.latest

    def close(self):
        self.stop.set();self.thread.join(timeout=5)
