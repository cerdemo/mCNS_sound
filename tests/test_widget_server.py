import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

from pythonosc.osc_packet import OscPacket
from mcns.__main__ import load_config
from mcns.server import Controller
from mcns.runtime import run


class WidgetServerTests(unittest.TestCase):
    def test_browser_lifecycle_recurrence_and_widget_udp(self):
        config = load_config('configs/default.json')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver, tempfile.TemporaryDirectory() as folder:
            receiver.bind(('127.0.0.1', 0))
            receiver.settimeout(.2)
            config['runtime']['port'] = receiver.getsockname()[1]
            def temporary_run(*args, **kwargs):
                args = list(args)
                args[4] = str(Path(folder)/Path(args[4]).name)
                return run(*args, **kwargs)
            with patch('mcns.server.run', side_effect=temporary_run):
                controller = Controller('build/visual-v1', config, 'models', 0)
                base = controller.dashboard.url
                def post(path, body, origin=None):
                    headers={'Content-Type':'application/json'}
                    if origin: headers['Origin']=origin
                    return json.load(urlopen(Request(base+path, json.dumps(body).encode(), headers)))
                def wait_state(predicate):
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        state=json.load(urlopen(base+'/api/state'))
                        if predicate(state):return state
                        time.sleep(.05)
                    self.fail('Timed out waiting for state: '+str(state.get('status')))
                try:
                    with self.assertRaises(HTTPError) as error:
                        post('/api/control', {'action':'start'}, 'https://example.com')
                    self.assertEqual(error.exception.code,403)
                    post('/api/control', {'action':'start','source':'white'})
                    on=wait_state(lambda s:s.get('other_mean_hz',0)>1)
                    post('/api/widget', dict(run_id=on['run_id'],mode='flying',x=.2,y=.3,
                        vx=.1,vy=0,gain=.7,wing_hz=230,speed=.1,activity=.4))
                    deadline=time.monotonic()+2
                    found=False
                    while time.monotonic()<deadline:
                        packet=OscPacket(receiver.recv(65536))
                        for item in packet.messages:
                            if item.message.address=='/mcns/widget/flight' and item.message.params[1]=='flying':
                                self.assertAlmostEqual(item.message.params[2],.7,places=5)
                                self.assertAlmostEqual(item.message.params[5],.2,places=5)
                                found=True
                        if found:break
                    self.assertTrue(found)
                    post('/api/control', {'action':'recurrence','enabled':False})
                    off=wait_state(lambda s:s.get('recurrent_enabled') is False and s.get('other_mean_hz')==0)
                    self.assertGreater(off['input_mean_hz'],0)
                    post('/api/control', {'action':'recurrence','enabled':True})
                    wait_state(lambda s:s.get('recurrent_enabled') and s.get('other_mean_hz',0)>1)
                    post('/api/control', {'action':'stop'})
                    wait_state(lambda s:s.get('status')=='stopped')
                    controller.worker.join(2)
                    post('/api/control', {'action':'start','source':'black'})
                    restarted=wait_state(lambda s:s.get('status')=='running')
                    self.assertNotEqual(restarted['run_id'],on['run_id'])
                finally:
                    controller.close()
            logs=list(Path(folder).glob('*/widget.jsonl'))
            self.assertEqual(len(logs),2)
            self.assertTrue(any(json.loads(line)['recurrent_enabled_next_window'] is False
                for line in logs[0].read_text().splitlines()+logs[1].read_text().splitlines()))

if __name__=='__main__':unittest.main()
