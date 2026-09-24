"""Versioned OSC contract. Population ordering is exported in each run folder."""
from pythonosc.udp_client import SimpleUDPClient


class Output:
    def __init__(self, host, port):
        self.client = SimpleUDPClient(host, port)

    def send(self, address, *args):
        self.client.send_message(address, list(args))

    def hello(self, populations, sizes):
        self.send("/mcns/schema", 1)
        for i, (name, size) in enumerate(zip(populations, sizes)):
            self.send("/mcns/population", i, name, int(size))

    def activity(self, sequence, simulated, rates, normalized):
        self.send("/mcns/rates", sequence, float(simulated), *map(float, rates))
        self.send("/mcns/activity", sequence, float(simulated), *map(float, normalized))

    def close(self):
        self.client._sock.close()
