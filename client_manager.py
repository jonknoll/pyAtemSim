# The client manager:
# Keeps a list of connected clients
# Keeps track of the last time there was communication with that client
# and ping the client regularly to ensure it is still there.

import time
import random
from atem_packet import Packet, ATEMFlags
import atem_commands
from atem_commands import CommandCarrier
import socket
import struct
from typing import List
import copy

CLIENT_ACTIVITY_TIMEOUT = 1.0   # seconds
CLIENT_DROPOUT_TIMEOUT = 3.0    # seconds
PACKET_RESEND_INTERVAL = 0.5    # seconds

class ATEMClientState:
    UNINITIALIZED = 0
    INITIALIZE = 1
    WAIT_FOR_INIT_RESPONSE = 2
    ESTABLISHED = 3
    FINISHED = 4


class ATEMClient(object):
    def __init__(self, ip_and_port=(), client_id=0, session_id=0, client_manager=None):
        self.ip_and_port = ip_and_port
        # There is a weird issue in Windows
        # where if the destination port is closed then the socket dies and
        # a subsequent recvfrom() will also not work. This is bad for a UDP
        # server, so it's safest if each client has it's own socket to
        # reply with.
        # https://bobobobo.wordpress.com/2009/05/17/udp-an-existing-connection-was-forcibly-closed-by-the-remote-host/
        #self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_id = client_id
        self.session_id = session_id
        self.current_packet_id = 0

        # State variables and other client maintenance
        # this is the last time the client sent a packet
        self.last_activity_time = 0
        self.last_ACKed_packet_id = 0
        self.client_state = ATEMClientState.UNINITIALIZED
        self.outbound_commands_list: List[CommandCarrier] = []
        self.outbound_packet_list: List[Packet] = []
        self.client_manager: ClientManager = client_manager

        # When an inbount packet has a command, store the packet id so
        # the ack can be sent on the next outgoing packet
        self.packet_id_needs_ack = None

    def get_next_packet_id(self):
        self.current_packet_id += 1
        return(self.current_packet_id)
    
    def add_to_outbound_commands_list(self, outbound_obj):
        self.outbound_commands_list.append(outbound_obj)

    def process_inbound_packet(self, in_packet: Packet):
        # timestamp the most recent activity from the client
        self.last_activity_time = time.monotonic()

        # if init packet then initialize this object and send a response
        if in_packet.flags & ATEMFlags.INIT and (
                # first connection
                in_packet.raw_cmd_data == b'\x01\x00\x00\x00\x00\x00\x00\x00'
                # disconnect
                or in_packet.raw_cmd_data == b'\x04\x00\x00\x00\x00\x00\x00\x00'):
            # This is an init packet. (re)Initialize client
            if self.client_state != ATEMClientState.UNINITIALIZED:
                self.__init__(self.ip_and_port, self.client_id, self.session_id)
                self.last_activity_time = time.monotonic()
            # Create response packet
            init_response_packet = Packet(self.ip_and_port)
            init_response_packet.flags |= ATEMFlags.INIT
            init_response_packet.session_id = self.session_id
            # client ID must be baked into the session ID when the connection
            # is successful. Bytes 3..4 of the init response packet are the
            # client ID. The session ID formula appears to be:
            # 0x8000 + client_id
            init_response_packet.raw_cmd_data = struct.pack('!2H 4x', 0x0200, self.client_id)
            #init_response_packet.raw_cmd_data = b'\x02\x00\x00\x1a\x00\x00\x00\x00'
            init_response_packet.to_bytes()
            self.outbound_packet_list.append(init_response_packet)
            self.client_state = ATEMClientState.WAIT_FOR_INIT_RESPONSE
            return

        # if response packet then remove the matching outbound packet off the
        # outbound packet list, plus any older packets
        if in_packet.flags & ATEMFlags.ACK:
            if self.client_state == ATEMClientState.WAIT_FOR_INIT_RESPONSE and in_packet.ACKed_packet_id == self.current_packet_id:
                # Connected to client!
                # Expected client session id = 0x8000 + client_id
                self.session_id = 0x8000 + self.client_id
                self.client_state = ATEMClientState.ESTABLISHED
                print(f"Connected client={self.ip_and_port}, session=0x{self.session_id:x}")
                # Special case: response packet for the init (part of the handshake)
                setup_commands_list = atem_commands.build_setup_commands_list()
                # still need to add the session ID, packet_id and run to_bytes() on each packet
                for cmds in setup_commands_list:
                    setup_packet = Packet(self.ip_and_port)
                    setup_packet.session_id = self.session_id
                    setup_packet.flags |= ATEMFlags.COMMAND
                    setup_packet.packet_id = self.get_next_packet_id()
                    setup_packet.commands = cmds
                    setup_packet.to_bytes()
                    self.outbound_packet_list.append(setup_packet)
                
                last_packet = Packet(self.ip_and_port)
                last_packet.session_id = self.session_id
                last_packet.flags |= ATEMFlags.COMMAND
                last_packet.packet_id = self.get_next_packet_id()
                last_packet.commands = atem_commands.Cmd_InCm()
                last_packet.to_bytes()
                self.outbound_packet_list.append(last_packet)

            else:
                packets_to_keep = []
                while self.outbound_packet_list:
                    p = self.outbound_packet_list.pop(0)
                    # discard if this packet is older than the packet being acked
                    if p.packet_id <= in_packet.ACKed_packet_id and p.packet_id != 0:
                        pass # discard packet
                    else:
                        packets_to_keep.append(p)
                # Put the packets to keep back into the outbout_packet_list
                self.outbound_packet_list = packets_to_keep
        
        
        if in_packet.flags & ATEMFlags.COMMAND:
            # This packet has commands
            # It will have to process the command(s) and return an ACK packet
            # which may include response commands.
            # Also, it will likely need to update all the other clients with
            # the new information.

            # Get the response command(s). The result is one or more
            # commands, contained in a list of CommandCarrier objects. The
            # object contains metadata for the command(s). There
            # may be more than one CommandCarrier object if more
            # than one packet needs to be sent as a result of the
            # command (eg. a transition).
            # If it returns an empty list then it is an unknown command,
            # so just send an ack packet to keep the client happy.
            cmds_carrier_list = atem_commands.get_response(in_packet.commands)
            if len(cmds_carrier_list) == 0:
                # unknown command, just ack
                ack_packet = Packet(self.ip_and_port)
                ack_packet.flags |= ATEMFlags.ACK
                ack_packet.ACKed_packet_id = in_packet.packet_id
                ack_packet.session_id = self.session_id
                ack_packet.to_bytes()
                self.last_ACKed_packet_id = in_packet.packet_id
                self.outbound_packet_list.append(ack_packet)
            else:
                # iterate through the commands sent back
                sent_ack = False
                for cc in cmds_carrier_list:
                    if cc.multicast == True:
                        self.client_manager.send_to_other_clients(self, cc)
                    if sent_ack == False:
                        cc.ack_packet_id = in_packet.packet_id
                        self.last_ACKed_packet_id = in_packet.packet_id
                        sent_ack = True
                    self.outbound_commands_list.append(cc)







    def update(self, sock: socket.socket):
        now = time.monotonic()

        # Perform regular client update activities. This mainly involves creating packets
        # and sending, or retransmitting packets if they haven't been ACK'd.
        # 1. iterate through the outbound objects
        #   generate one or more packets (split into multiple packets based on MTU=1500)
        #   add to the outbound packet list
        # TODO: if one command object has too many commands in it, then split
        # across multiple packets
        carriers_to_keep = []
        for cmd_carrier in self.outbound_commands_list:
            if cmd_carrier.send_time > now:
                # not time to send this packet yet
                carriers_to_keep.append(cmd_carrier)
            else:
                out_packet = Packet(self.ip_and_port)
                out_packet.flags |= ATEMFlags.COMMAND
                if cmd_carrier.ack_packet_id > 0:
                    # this is an ack packet
                    out_packet.flags |= ATEMFlags.ACK
                    out_packet.ACKed_packet_id = cmd_carrier.ack_packet_id
                out_packet.packet_id = self.get_next_packet_id()
                out_packet.session_id = self.session_id
                out_packet.commands = cmd_carrier.commands
                out_packet.to_bytes()
                self.outbound_packet_list.append(out_packet)
        self.outbound_commands_list = carriers_to_keep
        

        # 2. check the inactivity time (based on the last time the client communicated to the server)
        #   If > client inactivity timeout (say 1 sec) then generate an "are you there?" packet
        #   If > client dropout timeout (say 3 sec) then generate a "goodbye" init packet
        if self.client_state == ATEMClientState.ESTABLISHED:
            if now - self.last_activity_time > CLIENT_ACTIVITY_TIMEOUT:
                ping_packet = Packet(self.ip_and_port)
                ping_packet.flags |= ATEMFlags.COMMAND | ATEMFlags.ACK
                ping_packet.packet_id = self.get_next_packet_id()
                ping_packet.session_id = self.session_id
                ping_packet.ACKed_packet_id = self.last_ACKed_packet_id
                ping_packet.to_bytes()
                self.outbound_packet_list.append(ping_packet)
            
            if now - self.last_activity_time > CLIENT_DROPOUT_TIMEOUT:
                goodbye_packet = Packet(self.ip_and_port)
                goodbye_packet.flags |= ATEMFlags.INIT
                goodbye_packet.session_id = self.session_id
                goodbye_packet.to_bytes()
                self.outbound_packet_list.append(goodbye_packet)

        # 3. iterate through the outbound packets
        #   if it's an init packet, send and delete
        #   if it's a response packet only with no command data then send and delete
        #   if it's a packet with command data and send timestamp is 0 then send and keep
        #   if it's a packet with command data and send timestamp is >0 then 
        #       wait until the response timeout has elapsed (say 1 sec) and send again
        packets_to_keep = []
        while self.outbound_packet_list:
            pkt = self.outbound_packet_list.pop(0)
            if pkt.flags & ATEMFlags.INIT:
                sock.sendto(pkt.bytes, pkt.ip_and_port)
                # init response, discard packet after sending
            elif (pkt.flags & ATEMFlags.ACK) and ((pkt.flags & ATEMFlags.COMMAND) == 0):
                sock.sendto(pkt.bytes, pkt.ip_and_port)
                # ping response, discard packet after sending
            elif (pkt.flags & ATEMFlags.COMMAND) and pkt.last_send_timestamp == 0:
                sock.sendto(pkt.bytes, pkt.ip_and_port)
                pkt.last_send_timestamp = now
                # command packet, keep until an ack has been received
                packets_to_keep.append(pkt)
            elif (pkt.flags & ATEMFlags.COMMAND) and pkt.last_send_timestamp > 0:
                if now - pkt.last_send_timestamp > PACKET_RESEND_INTERVAL:
                    pkt.flags |= ATEMFlags.RETRANSMITION
                    sock.sendto(pkt.bytes, pkt.ip_and_port)
                    pkt.last_send_timestamp = now
                # command packet (resending), keep until an ack has been received
                packets_to_keep.append(pkt)
        # Put the packets to keep back into the outbout_packet_list
        self.outbound_packet_list = packets_to_keep

        # 4. If client dropout timeout (say >3 sec) then delete client
        if now - self.last_activity_time > CLIENT_DROPOUT_TIMEOUT:
            self.client_state = ATEMClientState.FINISHED




class ClientManager(object):
    def __init__(self):
        self.clients = []
        # every client needs a unique id, which gets baked into the session ID
        self.client_counter = 0

    # Get the client based on the packet info or create a new client
    def get_client(self, ip_and_port, session_id) -> ATEMClient:
        for client in self.clients:
            if client.ip_and_port == ip_and_port and client.session_id == session_id:
                return client
        client_id = self.get_next_client_id()
        new_client = ATEMClient(ip_and_port, client_id, session_id, self)
        print(f"Create client={new_client.ip_and_port}, session=0x{new_client.session_id:x}")
        self.clients.append(new_client)
        print(f"client count={len(self.clients)}")
        return new_client

    def run_clients(self, sock: socket.socket):
        clients_to_keep = []
        drop = False
        while self.clients:
            client = self.clients.pop(0)
            client.update(sock)
            if client.client_state == ATEMClientState.FINISHED:
                print(f"Dropping client={client.ip_and_port}, session=0x{client.session_id:x}")
                drop = True
            else:
                clients_to_keep.append(client)
        self.clients = clients_to_keep
        if drop == True:
            print(f"client count={len(self.clients)}")

    def send_to_other_clients(self, sending_client, outbound_obj):
        for client in self.clients:
            if client.ip_and_port == sending_client.ip_and_port and client.session_id == sending_client.session_id:
                # this is the sending client, so don't send to itself
                pass
            else:
                # Give each client a shallow copy of the commands carrier so the ack_packet_id
                # can be different for each client.
                client.outbound_commands_list.append(copy.copy(outbound_obj))

    def get_next_client_id(self):
        self.client_counter += 1
        return self.client_counter
