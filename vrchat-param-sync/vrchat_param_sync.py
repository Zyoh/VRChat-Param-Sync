from pythonosc import udp_client, dispatcher, osc_server
import threading
import logging
import time


class VRChatParamSyncReceiver:
	def __init__(self, receive_port: int, address_map: dict) -> None:		
		self.receive_port = receive_port
		self.address_map = address_map

		# Client (sends to VRChat)
		self.vrc_client = udp_client.SimpleUDPClient("127.0.0.1", 9000)

		# Server (gets from friend)
		d = dispatcher.Dispatcher()
		for addr_sync, addr_vrc in self.address_map.items():
			d.map(addr_sync, self.get_value_remote)
		self.server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", self.receive_port), d)

	def get_value_remote(self, address, value = None):
		logging.info(f"Got {address} with value of {value}")
		if value is not None:
			self.vrc_client.send_message(self.address_map[address], value)

	def run(self, asynchronous: bool = False):
		try:
			if asynchronous:
				threading.Thread(target=self._run, daemon=True).start()
			else:
				self._run()
		except KeyboardInterrupt:
			pass

	def _run(self):
		logging.info(f"Starting remote listener on port {self.receive_port}")
		self.server.serve_forever()


class VRChatParamSyncSender:
	def __init__(self, send_ip: str, send_port: int, address_map: dict) -> None:		
		self.send_ip = send_ip
		self.send_port = send_port
		self.address_map = address_map
	
		self.values = {}
		self._allow_requests = True
		self._last_attempt_data = None

		# Client (sends to friend)
		self.client = udp_client.SimpleUDPClient(self.send_ip, self.send_port)

		# Server (gets from VRChat)
		d = dispatcher.Dispatcher()
		for addr_vrc, addr_sync in self.address_map.items():
			d.map(addr_vrc, self.set_value)
		self.vrc_server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 9001), d)

	def set_value(self, address, value, force: bool = False):
		if not force:
			logging.debug(f"Read {address} with value of {value}")
		else:
			logging.debug(f"Forced | Read {address} with value of {value}")

		if self.values.get(address) != value or force:
			self.values[address] = value
			addr_sync = self.address_map[address]

			if self._allow_requests or force:
				if force:
					logging.info(f"Forced | Sending {addr_sync} value of {value}")
				else:
					logging.info(f"Sending {addr_sync} value of {value}")

				self.client.send_message(addr_sync, value)
				if not force:
					self._pause_requests(0.2)
			else:
				self._last_attempt_data = (address, value)

	def _pause_requests(self, duration: float):
		self._allow_requests = False
		time.sleep(duration)

		# Push most recent request asap
		if self._last_attempt_data is not None:
			self.set_value(*self._last_attempt_data, force=True)
			self._last_attempt_data = None

		self._allow_requests = True

	def run(self, asynchronous: bool = False):
		try:
			if asynchronous:
				threading.Thread(target=self._run, daemon=True).start()
			else:
				self._run()
		except KeyboardInterrupt:
			pass

	def _run(self):
		logging.info(f"Will send to {self.send_ip}:{self.send_port}")
		self.vrc_server.serve_forever()
	

def main():
	logging.basicConfig(format="%(asctime)s - %(levelname)s: %(message)s", datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

	# Default config syncs microphone and gesture states between both users.
	CONFIG = {
		"sender": {
			"target": {
				# If using sender, this must be the IP address of the receiver (the other user).
				"address": None,
				"port": 27134
			},
			"addresses": {
				# Sender converts VRChat OSC path to custom path (to allow syncing different parameters)
				"/avatar/parameters/MuteSelf": "/input/Voice",
				"/avatar/parameters/GestureLeft": "/gesturesLeft",
				"/avatar/parameters/GestureRight": "/gesturesRight"
			}
		},
		"receiver": {
			"port": 27134,
			"addresses": {
				# Receiver converts custom path to the parameter used in VRChat
				"/input/Voice": "/input/Voice", # Note this doesn't convert back to the same path
				"/gesturesLeft": "/avatar/parameters/GestureLeft",
				"/gesturesRight": "/avatar/parameters/GestureRight"
			}
		}
	}

	send_ip = CONFIG["sender"]["target"]["address"]
	send_port = CONFIG["sender"]["target"]["port"]
	send_address_map = CONFIG["sender"]["addresses"]

	receive_port = CONFIG["receiver"]["port"]
	receive_address_map = CONFIG["receiver"]["addresses"]

	sender = VRChatParamSyncSender(
		send_ip,
		send_port,
		send_address_map
	)
	receiver = VRChatParamSyncReceiver(
		receive_port,
		receive_address_map
	)

	# Both can run together (for sending your params as well as receiving)
	sender.run(asynchronous=True)
	receiver.run(asynchronous=True)

	# Hold
	try:
		while 1:
			time.sleep(1e6)
	except KeyboardInterrupt:
		print("Byebye")


if __name__ == "__main__":
	main()
