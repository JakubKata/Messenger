# protocol.py

class Packet:
	def __init__(self, command, *args):
		self.command = command
		self.args = [str(arg) for arg in args]

	def encode(self) -> bytes:
		payload = "|".join([self.command] + self.args)
		return f"{payload}\n".encode()

	@staticmethod
	def decode(raw_data: str):
		parts = raw_data.strip().split("|")
		return Packet(parts[0], *parts[1:])

CMD_MSG = "MSG"
CMD_CLIENTS = "CLIENTS"

CMD_ACK = "ACK"
CMD_NACK = "NACK"
CMD_SAVE = "SAVE"

CMD_EXISTING = "EXISTING"
CMD_NEW = "NEW"
CMD_BUSY = "BUSY" 
CMD_ACTIVE = "ACTIVE"
CMD_ALL = "ALL"

CMD_KEY = "KEY"
CMD_PUBKEY = "PUBKEY"
CMD_GETKEY = "GETKEY"
