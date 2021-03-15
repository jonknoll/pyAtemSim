# ATEM server:
# takes in a packet object
# processes the commands received


import socket
import argparse
import sys
import select

from client_manager import ClientManager
from atem_packet import Packet



def main():
    # Parse the input aruments
    ap = argparse.ArgumentParser()

    ap.add_argument("--address", required=False, default="0.0.0.0", help="listening IP address, default=\"0.0.0.0\"")
    ap.add_argument("--port", required=False, default=9910, help="listening UDP Port, default=9910")
    ap.add_argument("--debug", required=False, default="INFO", help="debug level (in quotes): NONE, INFO (default), WARNING, DEBUG")

    args = ap.parse_args()
    host = args.address
    port = args.port

    print("ATEM Server Starting...")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((host, port))

    client_mgr = ClientManager()

    print("ATEM Server Running...Hit ctrl-c to exit")

    while True:
        try:
            # Process incoming packets but timeout after a while so the clients
            # can perform cleanup and resend unresponded packets.
            readers, writers, errors = select.select([s], [], [], 1.0)
            if len(readers) > 0:
                try:
                    bytes, addr = s.recvfrom(2048)
                    packet = Packet(addr, bytes)
                    packet.parse_packet()
                    client = client_mgr.get_client(packet.ip_and_port, packet.session_id)
                    client.process_inbound_packet(packet)
                except ConnectionResetError:
                    print("connection reset!")
                    s.close()
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.bind((host, port))
                    continue
                except KeyboardInterrupt:
                    raise
            
            # Perform regularly regardless of incoming packets
            client_mgr.run_clients(s)
        except KeyboardInterrupt:
            # quit
            sys.exit()




# take next packet out of the UDP queue
# parse packet
# get the client object based on the packet contents
# - if client doesn't exist then check whether it is an init packet and create a new client otherwise discard
# send packet object to the client to process
# clientObj: if the packet has a response with response packet id then remove the corresponding packet from the packet queue
# clientObj sends to packet processor: packet processor reads commands, updates ATEM db and gets back list of command(s) in response, or none if nothing to return
# clientObj then sends the response commands if any to the other clients if any, based on whether it is a multicast update or not
# clientObj then builds a response packet and puts it in the packet queue
# run through the client objects and see if there is anything to send out (or delete client object if timeouts have occurred)





    # Event Loop:

    ####################
    # packet parser
    ####################
    # take in packet and parse it into a python dictionary or object, including client info

    ####################
    # process packet
    ####################
    # -if init for a new client (or maybe it's a re-init?)
    #   -check client list for an exact match (IP and socket) and reinit that client
    #   -if not in client list then create new client

    # -if ack for a packet then remove the packet off the client's outbound queue
    #   -remove any packets off the outbound queue that are older than the ack just received
    #   -this ack packet may also contain new commmands, keep for next part

    # -if a new command then process the command (or array of commands)
    #     -the result is a tuple of 2 things -- Maybe 1 and 2 are the same??
    #       1. response packet for the client that sent the command(s)
    #       2. update packet for the other clients (add to a broadcast queue)

    ################################
    # manage broadcast command list
    ################################
    # distribute the update commands to all the clients if any

    ##############################
    # iterate through each client
    ##############################
    # -check packet state: if still in the init state and > 3 seconds has elapsed since last_receive then silently drop client
    
    # -run packet builder to take command objects and turn them into packets that can go onto the outbound queue
    #   -the packet builder has to exist because one blob of commands may need to span multiple packets
    #   -each packet gets assigned a sequential packet id by the packet builder (packet counter maintained in client object)

    # -if anything in the outbound queue:
    #   -check the last time the client packet was sent
    #   -if never sent (send time = 0) then send packet
    #   -if more than 1 second has elapsed (now - last_send_time > 1sec), retransmit
    #   -if last_response > 3 seconds then send init packet and drop client
    # -if nothing in outbound queue:
    #   -if more than 0.5 second has elapsed (now - last_receive > 0.5sec) then send ping command




if __name__ == "__main__":
    main()
