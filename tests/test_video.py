import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import cv2
import numpy as np

from mcns.vision import Camera, VideoFile, inspect_video
from mcns.runtime import run
from mcns.server import Controller
from mcns.__main__ import load_config
from mcns.sensors import LimbSensors, LIMB_IDS


def make_video(path, frames=5, fps=10):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), fps, (64, 48))
    if not writer.isOpened():
        raise RuntimeError('MJPG test encoder unavailable')
    for i in range(frames):
        image = np.zeros((48, 64, 3), np.uint8)
        image[:, :32] = (0, 0, 220-i*10)
        image[:, 32:] = (230-i*10, 0, 0)
        writer.write(image)
    writer.release()


class VideoTests(unittest.TestCase):
    def test_camera_flip_precedes_neural_pixels_and_probe_sampling(self):
        image = np.zeros((4, 6, 3), np.uint8)
        image[:, :3, 2] = 255
        image[:, 3:, 0] = 255
        with patch('cv2.VideoCapture') as factory:
            capture = factory.return_value
            capture.isOpened.return_value = True
            capture.read.return_value = (True, image)
            camera = Camera()
            try:
                deadline = time.monotonic()+1
                while camera.get() is None and time.monotonic()<deadline:
                    time.sleep(.005)
                seq, stamp, mirrored = camera.get()
                np.testing.assert_array_equal(mirrored, image[:, ::-1])
                probes = [dict(id=name, x=0., y=.5) for name in LIMB_IDS]
                records, _ = LimbSensors().update(mirrored, seq, 0,
                    (stamp, dict(sample_time=stamp, probes=probes)), None, stamp)
                self.assertEqual(records[0]['rgb'], [0., 0., 1.])
            finally:
                camera.close()

    def test_video_timing_loop_sequence_orientation_and_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'test.avi'
            make_video(path)
            info = inspect_video(path)
            self.assertEqual(info['frames'], 5)
            self.assertAlmostEqual(info['duration_s'], .5)
            video = VideoFile(path, loop=False)
            try:
                time.sleep(.03)
                seq, _, image = video.get()
                self.assertEqual(seq, 1)  # Not decoded to EOF immediately.
                self.assertGreater(image[20, 5, 2], image[20, 5, 0])  # Videos are not mirrored.
                self.assertTrue(video.ended.wait(1.5))
                self.assertEqual(video.get()[0], 5)
            finally:
                video.close()
            self.assertFalse(video.thread.is_alive())
            looped = VideoFile(path, loop=True)
            try:
                time.sleep(.65)
                self.assertGreater(looped.get()[0], 5)
                self.assertFalse(looped.ended.is_set())
            finally:
                looped.close()

    def test_runtime_finishes_video_and_records_source(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.avi'
            make_video(path, frames=3)
            with patch('mcns.runtime.Output') as output:
                summary = run('build/visual-v1', load_config('configs/default.json'),
                              'video', None, Path(folder)/'run', video_path=path, video_loop=False)
            self.assertEqual(summary['status'], 'completed')
            self.assertGreater(summary['frames_used'], 0)
            self.assertLess(summary['wall_seconds'], 2)
            info = json.loads((Path(folder)/'run/run.json').read_text())
            self.assertEqual(info['source'], 'video')
            self.assertFalse(info['mirror'])
            output.return_value.send.assert_any_call('/mcns/state', 'completed')

    def test_real_http_upload_validation_reuse_and_video_start(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.avi'
            make_video(path)
            controller = Controller('build/visual-v1', load_config('configs/default.json'), 'models', 0)
            base = controller.dashboard.url
            def upload(data, name='input.avi', origin=None):
                headers = {'Content-Type':'application/octet-stream'}
                if origin:
                    headers['Origin'] = origin
                return json.load(urlopen(Request(base+'/api/video?name='+name, data, headers)))
            try:
                with self.assertRaises(HTTPError) as caught:
                    upload(path.read_bytes(), origin='https://example.com')
                self.assertEqual(caught.exception.code, 403)
                with self.assertRaises(HTTPError):
                    upload(b'bad', name='file.txt')
                result = upload(path.read_bytes())
                identity = result['video']['id']
                self.assertEqual(result['video']['width'], 64)
                self.assertEqual(json.load(urlopen(base+'/api/video'))['video']['id'], identity)
                uploaded_path = controller.video_path
                with self.assertRaises(HTTPError):
                    upload(b'not a video', name='invalid.mp4')
                self.assertEqual(controller.video_meta['id'], identity)
                self.assertTrue(uploaded_path.exists())
                with self.assertRaises(ValueError):
                    controller.control(dict(action='start', source='video', video_id='invalid'))
                with patch('mcns.server.run') as runner:
                    controller.control(dict(action='start', source='video', video_id=identity, video_loop=False))
                    controller.worker.join(2)
                    self.assertEqual(runner.call_args.args[2], 'video')
                    self.assertTrue(runner.call_args.args[8])  # Detection/tracking enabled for video.
                    self.assertEqual(runner.call_args.kwargs['video_path'], uploaded_path)
                    self.assertFalse(runner.call_args.kwargs['video_loop'])
            finally:
                controller.close()
            self.assertFalse(uploaded_path.exists())


if __name__ == '__main__':
    unittest.main()
