"""Eight virtual image-plane probes. Pixels are read from unannotated BGR frames.

Box overlap is a semantic annotation, never a physical/tactile measurement.
Motion is that of the virtual endpoints, in image widths/heights per second.
"""
import math
import numpy as np

LIMB_IDS = ('leg-L1', 'leg-L2', 'leg-L3', 'leg-R1', 'leg-R2', 'leg-R3', 'antenna-L', 'antenna-R')


def validate_probes(body):
    probes = body.get('probes', [])
    if not isinstance(probes, list) or len(probes) not in (0, 8):
        raise ValueError('Expected eight limb probes')
    if not probes:
        return [], 0.
    stamp = body.get('sample_time')
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or stamp < 0:
        raise ValueError('Invalid probe time')
    cleaned = []
    for probe, name in zip(probes, LIMB_IDS):
        if not isinstance(probe, dict) or probe.get('id') != name:
            raise ValueError('Invalid limb identity/order')
        if any(isinstance(probe.get(k), bool) or not isinstance(probe.get(k), (int, float))
               or not math.isfinite(probe[k]) or not -1 <= probe[k] <= 2 for k in ('x', 'y')):
            raise ValueError('Invalid limb coordinates')
        cleaned.append({k: probe[k] for k in ('id', 'x', 'y')})
    return cleaned, float(stamp)


class LimbSensors:
    def __init__(self):
        self.previous = {}
        self.contacts = {}

    def update(self, frame, frame_id, frame_age_ms, widget, scene, now):
        fresh = widget is not None and 0 <= now-widget[0] < .35
        data = widget[1] if fresh else {}
        probes = {p['id']: p for p in data.get('probes', [])}
        stamp = data.get('sample_time', 0.)
        frame_valid = frame is not None and 0 <= frame_age_ms < 350
        objects = scene.get('objects', []) if scene else []
        records, events = [], []
        for name in LIMB_IDS:
            p = probes.get(name)
            valid = bool(frame_valid and p and 0 <= p['x'] <= 1 and 0 <= p['y'] <= 1)
            x, y = (p['x'], p['y']) if p else (0., 0.)
            rgb, luminance, contrast = [0., 0., 0.], 0., 0.
            obj = None
            if valid:
                h, w = frame.shape[:2]
                px, py = round(x*(w-1)), round(y*(h-1))
                patch = frame[max(0, py-1):min(h, py+2), max(0, px-1):min(w, px+2)]
                if patch.ndim == 2:
                    patch = np.repeat(patch[..., None], 3, axis=2)
                values = patch[..., ::-1].astype(float)/255
                rgb = values.mean(axis=(0, 1)).tolist()
                light = values @ np.array([.2126, .7152, .0722])
                luminance, contrast = float(light.mean()), float(light.std())
                hits = [o for o in objects if o['box'][0] <= x <= o['box'][2]
                        and o['box'][1] <= y <= o['box'][3]]
                if hits:
                    obj = min(hits, key=lambda o: ((o['box'][2]-o['box'][0])*(o['box'][3]-o['box'][1]), -o['score']))
            motion = dict(valid=False, vx=0., vy=0., ax=0., ay=0., speed=0., acceleration=0.)
            prev = self.previous.get(name)
            if valid:
                if prev and stamp == prev['stamp']:
                    motion = prev['motion'].copy()
                else:
                    delta = stamp-prev['stamp'] if prev else 0
                    if prev and .005 <= delta <= .25:
                        vx, vy = (x-prev['x'])/delta, (y-prev['y'])/delta
                        ax = (vx-prev['motion']['vx'])/delta if prev['motion']['valid'] else 0.
                        ay = (vy-prev['motion']['vy'])/delta if prev['motion']['valid'] else 0.
                        motion = dict(valid=True, vx=vx, vy=vy, ax=ax, ay=ay,
                                      speed=math.hypot(vx, vy), acceleration=math.hypot(ax, ay))
                    self.previous[name] = dict(stamp=stamp, x=x, y=y, motion=motion.copy())
            else:
                self.previous.pop(name, None)
            identity = obj['id'] if obj else None
            old = self.contacts.get(name)
            if old and old['id'] != identity:
                events.append(dict(limb=name, event='exit', object_id=old['id'], label=old['label']))
            if obj and (not old or old['id'] != identity):
                events.append(dict(limb=name, event='enter', object_id=identity, label=obj['label']))
            self.contacts[name] = obj
            records.append(dict(id=name, valid=valid, x=x, y=y, rgb=rgb, luminance=luminance,
                                contrast=contrast, frame_id=int(frame_id), frame_age_ms=float(frame_age_ms),
                                motion=motion, object=obj, semantic_valid=bool(valid and scene is not None)))
        return records, events

    @staticmethod
    def send(osc, sequence, records, events):
        for p in records:
            address = '/mcns/limb/'+p['id']
            osc.send(address+'/pixel', sequence, p['frame_id'], int(p['valid']), float(p['x']), float(p['y']),
                     *p['rgb'], p['luminance'], p['contrast'], p['frame_age_ms'])
            m = p['motion']
            osc.send(address+'/motion', sequence, int(m['valid']), *[float(m[k]) for k in ('vx','vy','ax','ay','speed','acceleration')])
            o = p['object']
            osc.send(address+'/object', sequence, int(p['semantic_valid']), int(o['id']) if o else -1,
                     o['label'] if o else '', float(o['score']) if o else 0.)
        for e in events:
            osc.send('/mcns/contact', sequence, e['limb'], e['event'], e['object_id'], e['label'])
