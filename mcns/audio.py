"""Audio envelope → annotated JO-A/B cells; an explicit, uncalibrated transducer.

Mono 80–1000 Hz energy drives both antennae equally. No directional hearing,
frequency-specific cell tuning, song recognition, or direct motor shortcut.
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt


class AudioTrack:
    def __init__(self, path):
        self.path = Path(path)
        rate, pcm = wavfile.read(self.path, mmap=True)
        self.duration = len(pcm)/rate
        self.hz = 20
        hop = max(1, round(rate/self.hz))
        filters = butter(2, [80, 1000], btype='bandpass', fs=rate, output='sos')
        memory = np.zeros((len(filters), 2))
        levels = []
        for start in range(0, len(pcm), hop):
            frame = pcm[start:start+hop].astype(np.float32)/32768
            if frame.ndim == 2:
                frame = frame.mean(axis=1)
            frame, memory = sosfilt(filters, frame, zi=memory)
            levels.append(float(np.sqrt(np.mean(frame*frame))))
        self.levels = np.asarray(levels, np.float32)
        del pcm

    def level(self, position):
        index = int(position*self.hz)
        return float(self.levels[index]) if 0 <= position < self.duration and index < len(self.levels) else 0.


def extract_audio(video, target):
    """Local PCM cache for compatible playback and hearing independent of mute."""
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        return None, 'Audio unavailable: ffmpeg/ffprobe is not installed'
    try:
        result = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'a:0',
            '-show_entries', 'stream=index', '-of', 'json', str(video)],
            capture_output=True, timeout=20, check=True)
        if not json.loads(result.stdout).get('streams'):
            return None, 'No audio track'
        subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-y', '-i', str(video),
            '-map', '0:a:0', '-vn', '-af', 'aresample=async=1:first_pts=0',
            '-ar', '22050', '-ac', '2', '-c:a', 'pcm_s16le', str(target)],
            capture_output=True, timeout=120, check=True)
        return AudioTrack(target), 'Audio ready'
    except (OSError, ValueError, subprocess.SubprocessError):
        Path(target).unlink(missing_ok=True)
        return None, 'Audio could not be decoded; video remains available'


class AuditoryInput:
    def __init__(self, neurons, options=None):
        self.mask = (neurons.is_auditory_input.to_numpy(dtype=bool) if 'is_auditory_input' in neurons
                     else np.zeros(len(neurons), bool))
        options = options or {}
        self.gain = options.get('current_gain', 2.2)
        self.floor = options.get('floor_dbfs', -80.)
        self.ceiling = options.get('ceiling_dbfs', -24.)
        if not np.isfinite([self.gain, self.floor, self.ceiling]).all() or self.gain < 0 or self.ceiling <= self.floor:
            raise ValueError('Invalid auditory transducer parameters')

    def current(self, rms):
        db = 20*np.log10(max(float(rms), 1e-9))
        return self.gain*float(np.clip((db-self.floor)/(self.ceiling-self.floor), 0, 1))
