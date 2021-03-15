# Packet stuff

import struct
import time
import atem_commands


PACKET_HEADER_SIZE = 12

class ATEMFlags:
    COMMAND = 0x01
    INIT = 0x2
    RETRANSMITION = 0x4
    UNKNOWN = 0x8
    ACK = 0x10

class Packet(object):
    def __init__(self, ip_and_port=('', 0), raw_packet=b''):
        # raw packet data
        self.ip_and_port = ip_and_port
        self.bytes = bytearray(raw_packet)

        # parsed packet data
        self.flags = 0x00
        self.packet_length = 0
        self.session_id = 0
        self.ACKed_packet_id = 0x0000
        self.packet_id = 0x0000
        self.commands = []

        # extra stuff
        self.timestamp = time.monotonic()
        self.last_send_timestamp = 0
        self.raw_cmd_data = None    # if this is not None then use this instead of commands. Used mainly for init packets.
        
    def parse_packet(self):
        flags_and_size = struct.unpack_from('!H', self.bytes, 0)[0]
        self.flags = (flags_and_size >> 11) & 0x001F
        self.packet_length = flags_and_size & 0x007F
        self.session_id, self.ACKed_packet_id, self.packet_id = struct.unpack_from('!2H 4x H', self.bytes, 2)
        if self.packet_length > PACKET_HEADER_SIZE:
            # deal with commands
            bytes_remaining = self.packet_length - PACKET_HEADER_SIZE
            packet_offset = PACKET_HEADER_SIZE
            if self.flags & ATEMFlags.INIT:
                # for INIT packets, just put the command data into raw_cmd_data
                self.raw_cmd_data = self.bytes[PACKET_HEADER_SIZE:]
            else:
                while bytes_remaining > 0:
                    cmd_length, cmd_raw_name = struct.unpack_from('!H 2x 4s', self.bytes, packet_offset)
                    cmd_name = cmd_raw_name.decode('utf-8')
                    cmd_bytes = self.bytes[packet_offset:(packet_offset + cmd_length)]
                    cmd_obj = atem_commands.get_command_object(cmd_bytes, cmd_name)
                    cmd_obj.parse_cmd()
                    self.commands.append(cmd_obj)
                    packet_offset += cmd_length
                    bytes_remaining -= cmd_length

    def to_bytes(self):
        #temp = self.bytes
        self.bytes = bytearray()
        if type(self.commands) != list:
            self.commands = [self.commands]
        if len(self.commands) > 0:
            self.flags |= ATEMFlags.COMMAND
        flags = ((self.flags & 0x001F) << 11)
        self.bytes += struct.pack('!H', flags)
        self.bytes += struct.pack('!2H 4x H', self.session_id, self.ACKed_packet_id, self.packet_id)
        self.packet_length = PACKET_HEADER_SIZE
        if self.raw_cmd_data != None:
            self.bytes += self.raw_cmd_data
            self.packet_length += len(self.raw_cmd_data)
        else:
            for cmd in self.commands:
                cmd.to_bytes()
                self.bytes += cmd.bytes
                self.packet_length += cmd.length
        # now add length of packet
        flags_and_size = struct.unpack_from('!H', self.bytes, 0)[0]
        flags_and_size |= (self.packet_length & 0x07FF)
        struct.pack_into('!H', self.bytes, 0, flags_and_size)
        #print(f"b1 = {temp}")
        #print(f"b2 = {self.bytes}")
        assert(self.packet_length == len(self.bytes))



class OutboundPacketContainer(object):
    def __init__(self):
        self.last_sent_time = 0
        self.retransmit_count = 0
        self.packet = None


if __name__ == "__main__":
    # Quick test
    b1 = b'\x10\x14Z\xce\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00'
    p = Packet(('192.168.1.50', 9910), b1)
    p.parse_packet()
    p.to_bytes()
    b2 = p.bytes
    assert(b1 == b2)
