"""Local JPEG preview, drawing detections on the exact inference frame."""
import cv2
import numpy as np

HAND_EDGES = [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
              (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),
              (13,17),(0,17),(17,18),(18,19),(19,20)]


def encode_preview(frame, hands=None, face=None):
    image = frame.copy()
    h,w = image.shape[:2]
    if hands is not None:
        for landmarks, labels in zip(hands.hand_landmarks, hands.handedness):
            xy = [(int(p.x*w), int(p.y*h)) for p in landmarks]
            for a,b in HAND_EDGES:
                cv2.line(image, xy[a], xy[b], (110,240,170), 2, cv2.LINE_AA)
            for point in xy:
                cv2.circle(image, point, 3, (240,255,240), -1)
            cv2.putText(image, labels[0].category_name, xy[0], cv2.FONT_HERSHEY_SIMPLEX,
                        .5, (110,240,170), 1, cv2.LINE_AA)
    if face is not None:
        for landmarks in face.face_landmarks:
            xy = np.array([(int(p.x*w), int(p.y*h)) for p in landmarks])
            for x,y in xy:
                cv2.circle(image, (x,y), 1, (230,190,100), -1)
            low,high = xy.min(axis=0),xy.max(axis=0)
            cv2.rectangle(image, tuple(low), tuple(high), (230,190,100), 1)
    ok, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 75])
    if not ok:
        raise RuntimeError("Preview JPEG encoding failed")
    return jpeg.tobytes()
