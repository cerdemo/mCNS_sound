import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

import numpy as np
import pandas as pd
from scipy import sparse

from mcns.audio import AudioTrack, AuditoryInput, extract_audio
from mcns.model import LIF
from mcns.readout import DescendingReadout
from mcns.server import Controller
from mcns.__main__ import load_config
from mcns.runtime import run


class AudioTests(unittest.TestCase):
    def test_real_auditory_graph_requires_synapses_for_downstream_activity(self):
        n = pd.read_feather('build/audiovisual-v1/neurons.feather')
        config = load_config('configs/audiovisual.json')
        weights = sparse.load_npz('build/audiovisual-v1/weights.npz')
        auditory = AuditoryInput(n, config['auditory'])
        self.assertEqual(int(auditory.mask.sum()), 102)
        self.assertTrue((n[auditory.mask].subclass == 'auditory').all())
        self.assertTrue(n[auditory.mask].rootSide.isin(['L','R']).all())
        self.assertEqual(auditory.current(0), 0)
        self.assertLess(auditory.current(.001), auditory.current(.1))
        readout = DescendingReadout(n)
        for _ in range(20):
            motor = readout.update(np.where(auditory.mask, 100, 0), .05)
        self.assertEqual(motor['locomotion_drive'], 0)
        for coupled in (True, False):
            engine = LIF(weights if coupled else sparse.csr_matrix(weights.shape), config['model'])
            current = np.zeros(len(n), np.float32)
            current[auditory.mask] = auditory.current(.03)
            counts = np.zeros(len(n))
            for _ in range(1000):
                counts += engine.step(current)
            self.assertGreater(counts[auditory.mask].sum(), 0)
            if coupled:
                self.assertGreater(counts[~auditory.mask].sum(), 0)
            else:
                self.assertEqual(counts[~auditory.mask].sum(), 0)

    def test_audio_import_range_playback_runtime_and_microphone_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'tone.mp4'
            subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=black:s=64x48:r=10:d=1',
                '-f','lavfi','-i','sine=frequency=250:duration=1','-c:v','libx264','-c:a','aac','-shortest',str(path)], check=True)
            config = load_config('configs/audiovisual.json')
            controller = Controller('build/audiovisual-v1', config, 'models', 0)
            base = controller.dashboard.url
            try:
                with path.open('rb') as stream:
                    video = controller.import_video(stream, path.stat().st_size, 'tone.mp4')['video']
                self.assertTrue(video['has_audio'])
                track = controller.audio_track
                self.assertGreater(track.level(.5), .03)
                self.assertEqual(track.level(2), 0)
                endpoint = base+'/api/video-audio/'+video['id']+'.wav'
                with urlopen(Request(endpoint, headers={'Range':'bytes=0-43'})) as response:
                    self.assertEqual(response.status, 206)
                    data = response.read()
                    self.assertEqual(len(data), 44)
                    self.assertEqual(data[:4], b'RIFF')
                with urlopen(Request(endpoint, headers={'Range':'bytes=-8'})) as response:
                    self.assertEqual(len(response.read()), 8)
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(endpoint, headers={'Range':'bytes=999999999-'}))
                self.assertEqual(error.exception.code, 416)
                with self.assertRaises(HTTPError):
                    urlopen(base+'/api/video-audio/wrong.wav')
                # Audio perception runs without any browser player or unmute action.
                with patch('mcns.runtime.Output') as output:
                    run('build/audiovisual-v1', config, 'video', .5, Path(directory)/'run',
                        video_path=controller.video_path, audio_track=track,
                        dashboard_instance=controller.dashboard)
                state = controller.dashboard.state
                self.assertTrue(state['auditory']['valid'])
                self.assertGreater(state['auditory']['current'], 1)
                self.assertGreater(state['video_position_s'], 0)
                output.return_value.send.assert_any_call('/mcns/auditory', state['sequence']+1, 0, 0., 0., 0.)
                controller.dashboard.update(status='running', source='camera', run_id='mic')
                def post(body):
                    return urlopen(Request(base+'/api/audio', json.dumps(body).encode(), {'Content-Type':'application/json'}))
                for value in (-1, 2, float('nan'), True):
                    with self.assertRaises(HTTPError):
                        post(dict(run_id='mic', rms=value))
                with self.assertRaises(HTTPError):
                    post(dict(run_id='old', rms=.1))
                with post(dict(run_id='mic', rms=.1)) as response:
                    self.assertEqual(response.status, 200)
                self.assertEqual(controller.dashboard.get_audio()[1], .1)
                controller.dashboard.reset()
                self.assertIsNone(controller.dashboard.get_audio())
            finally:
                controller.close()
            self.assertFalse(track.path.exists())

if __name__ == '__main__':
    unittest.main()
