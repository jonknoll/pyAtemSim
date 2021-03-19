# ATEM commands

import struct
import raw_commands
from typing import List
import atem_config
from atem_config import DEVICE_VIDEO_SOURCES
import datetime


class ATEMCommand(object):
    def __init__(self, bytes=b''):
        self.bytes = bytes
        self.length = None
        self.code = type(self).__name__[-4:]
        self.full = ""
        self.time_to_send = 0
    
    def parse_cmd(self):
        """
        Parse the command into useful variables
        """
        pass

    def update_state(self):
        """
        Updated the internal state of the switcher
        """
        pass

    def to_bytes(self):
        """
        Build the command into a byte stream
        """
        pass

    def _build(self, content):
        """
        Boilerplate bytes stream build stuff for commands
        """
        if self.length != None:
            cmd_length = self.length
        else:
            cmd_length = len(content) + 8
            self.length = cmd_length
        cmd = struct.pack('!H 2x 4s', cmd_length, self.code.encode())
        return cmd + content



class Cmd__ver(ATEMCommand):
    def __init__(self, bytes=b''):
        super().__init__(bytes=bytes)
        self.full = "ProtocolVersion"
        self.major = 2
        self.minor = 30
    
    def to_bytes(self):
        content = struct.pack('!HH', self.major, self.minor)
        self.bytes = self._build(content)


class Cmd__pin(ATEMCommand):
    def __init__(self, bytes=b''):
        super().__init__(bytes=bytes)
        self.full = "ProductId"
        self.product_name = "ATEM Television Studio HD"
    
    def to_bytes(self):
        content = struct.pack('!44s', self.product_name.encode())
        self.bytes = self._build(content)


class Cmd_InCm(ATEMCommand):
    def __init__(self, bytes=b''):
        super().__init__(bytes=bytes)
        self.length = 12
        self.raw_hex = b'\x01\x00\x00\x00'

    def to_bytes(self):
        self.bytes = self._build(self.raw_hex)

        

# Program Input from client (See also PrgI)
class Cmd_CPgI(ATEMCommand):
    def __init__(self, bytes=b''):
        super().__init__(bytes=bytes)
        self.length = 12
        self.me = None
        self.video_source = None

    def parse_cmd(self):
        self.length = len(self.bytes)
        self.me, self.video_source = struct.unpack('!B x H', self.bytes[8:12])

    def update_state(self):
        atem_config.conf_db['MixEffectBlocks'][self.me]['Program']['input'] = str(self.video_source)
        #print(f"me{self.me}={atem_config.conf_db['MixEffectBlocks'][self.me]}")

# Preview Input from client, almost identical to Cmd_CPgI (See also PrvI)
class Cmd_CPvI(ATEMCommand):
    def __init__(self, bytes=b''):
        super().__init__(bytes=bytes)
        self.length = 12
        self.me = None
        self.video_source = None

    def parse_cmd(self):
        self.length = len(self.bytes)
        self.me, self.video_source = struct.unpack('!B x H', self.bytes[8:12])

    def update_state(self):
        atem_config.conf_db['MixEffectBlocks'][self.me]['Preview']['input'] = str(self.video_source)
        #print(f"me{self.me}={atem_config.conf_db['MixEffectBlocks'][self.me]}")


# Time
class Cmd_Time(ATEMCommand):
    def __init__(self, bytes=b''):
        super().__init__(bytes=bytes)
        self.length = 16

    def to_bytes(self):
        video_mode = atem_config.conf_db['VideoMode']['videoMode']
        if "5994" in video_mode:
            frame_rate = 59.94
        elif "2997" in video_mode:
            frame_rate = 29.97
        elif "2398" in video_mode:
            frame_rate = 23.98
        elif "50" in video_mode:
            frame_rate = 50
        elif "25" in video_mode:
            frame_rate = 25
        elif "24" in video_mode:
            frame_rate = 24
        t = datetime.datetime.now()
        frame = int(t.microsecond / 1000000 * frame_rate)
        content = struct.pack('!4B 4x', t.hour, t.minute, t.second, frame)
        self.bytes = self._build(content)


# Tally By Index
class Cmd_TlIn(ATEMCommand):
    def __init__(self, me=0):
        super().__init__(b'')
        self.me = me

    def to_bytes(self):
        program_source = int(atem_config.conf_db['MixEffectBlocks'][self.me]['Program']['input'])
        preview_source = int(atem_config.conf_db['MixEffectBlocks'][self.me]['Preview']['input'])
        num_inputs = len(atem_config.conf_db['Settings']['Inputs'])
        # Build content
        content = struct.pack('!H', num_inputs)
        for i in range(num_inputs):
            input_byte = 0x00
            if program_source <= num_inputs and program_source == i + 1:
                input_byte |= 0x01
            if preview_source <= num_inputs and preview_source == i + 1:
                input_byte |= 0x02
            content += struct.pack('!B', input_byte)
        # add the 2 unknown bytes
        content += struct.pack('!2x')
        self.bytes = self._build(content)


# Tally By Source
class Cmd_TlSr(ATEMCommand):
    def __init__(self, me=0):
        super().__init__(bytes=bytes)
        self.length = 84
        self.me = me

    def to_bytes(self):
        program_source = int(atem_config.conf_db['MixEffectBlocks'][self.me]['Program']['input'])
        preview_source = int(atem_config.conf_db['MixEffectBlocks'][self.me]['Preview']['input'])
        product = atem_config.conf_db['product']
        video_sources = DEVICE_VIDEO_SOURCES[product]
        num_sources = len(video_sources)
        # Build content
        content = struct.pack('!H', num_sources)
        for i in range(num_sources):
            source_byte = 0x00
            if program_source == video_sources[i]:
                source_byte |= 0x01
            if preview_source == video_sources[i]:
                source_byte |= 0x02
            content += struct.pack('!HB', video_sources[i], source_byte)
        # add the 2 unknown bytes
        content += struct.pack('!2x')
        self.bytes = self._build(content)


# Program Input to client (see also CPgI)
class Cmd_PrgI(ATEMCommand):
    def __init__(self, me=0):
        super().__init__(bytes=bytes)
        self.me = me

    def to_bytes(self):
        program_source = int(atem_config.conf_db['MixEffectBlocks'][self.me]['Program']['input'])
        content = struct.pack('!B x H', self.me, program_source)
        self.bytes = self._build(content)

# Preview Input to client, almost identical to Cmd_PrgI (see also CPvI)
class Cmd_PrvI(ATEMCommand):
    def __init__(self, me=0):
        super().__init__(bytes=bytes)
        self.me = me

    def to_bytes(self):
        program_source = int(atem_config.conf_db['MixEffectBlocks'][self.me]['Preview']['input'])
        content = struct.pack('!B x H 4x', self.me, program_source)
        self.bytes = self._build(content)






class Cmd_Unknown(ATEMCommand):
    def __init__(self, bytes, name=""):
        super().__init__(bytes=bytes)
        if name:
            self.code = name
        else:
            self.code = "UNKN"

    def parse_cmd(self):
        pass

    def to_bytes(self):
        self.length = len(self.bytes)


class Cmd_Raw(ATEMCommand):
    def __init__(self, bytes):
        super().__init__(bytes=bytes)

    def to_bytes(self):
        self.length = len(self.bytes)


class CommandCarrier(object):
    def __init__(self):
        # array of commands to be sent in a packet
        self.commands = []
        # Can set to a future time (relative to monotonic clock)
        # if it's a transition command where multiple commands
        # have to be sent to update the state of the transition.
        # Leave as 0 to be sent right away (default).
        self.send_time = 0
        # Set if the client object who receives the response,
        # needs to send it to the client manager so it can be
        # sent out to the other clients as well. Normally this
        # is the case. There are just a few commands that are
        # for the requesting client only.
        self.multicast = True
        # Packet id to ack when this response command(s) is sent back.
        # This is more for the client to manage in the outbound_packet_list.
        self.ack_packet_id = 0


def build_setup_commands_list():
    raw_setup_commands = [
        raw_commands.commands1,
        raw_commands.commands2,
        raw_commands.commands3,
        raw_commands.commands4,
        raw_commands.commands5,
        raw_commands.commands6,
        #raw_commands.commands7,
        #raw_commands.commands8,
        ]
    commands_list = []
    for rsc in raw_setup_commands:
        cmd_bytes = raw_commands.getByteStream(rsc)
        cmd = Cmd_Raw(cmd_bytes)
        commands_list.append(cmd)
    return commands_list




# get commands list by piecing together the name of the class from the command you want
# and use:
# classname = "Cmd" + command_name.decode()
# if hasattr(atem_commands, classname):
#   TheClass = getattr(atem_commands, classname)
#OR instance = getattr(atem_commands, classname)(class_params)
#
# This would be the manual way...
commands_list = {'_ver' : Cmd__ver,
                '_pin' : Cmd__pin,
                'InCm' : Cmd_InCm,
                'CPgI' : Cmd_CPgI,
                'CPvI' : Cmd_CPvI,
                }

def build_current_state_command_list():
    return_list = []

    cmd = Cmd__ver()
    return_list.append(cmd)

    cmd = Cmd__pin()
    return_list.append(cmd)

    #...etc.
    return return_list

def build_command_list_from_names(command_names: list):
    return_list = []
    for cmd_name in commands_list:
        new_cmd = get_command_object(cmd_name)
        if new_cmd != None:
            return_list.append(new_cmd)
    return return_list


def get_command_object(bytes=b'', cmd_name=""):
    cmd_class = commands_list.get(cmd_name)
    if cmd_class is not None:
        cmd_obj = cmd_class(bytes)
    else:
        cmd_obj = Cmd_Unknown(bytes, cmd_name)
    return cmd_obj


def get_response(cmd_list:List[ATEMCommand]):
    """
    Get the response command(s) for a list of commands
    from a client packet. Typically a client sends only one
    command at a time.
    
    Returns a list of CommandCarrier objects.
    The CommandCarrier object contains one or more response
    commands as well as metadata for the command.
    Typically there is only one CommandCarrier object returned,
    containing one set of response commands to send
    to the client(s). However, there may be more than one
    CommandCarrier object if the response requires more
    than one packet be sent a result of the command
    (eg. a transition like fade to black).
    If it is an unknown command then it returns an empty list.
    """
    response_list = []
    for cmd in cmd_list:
        if isinstance(cmd, Cmd_CPgI):
            cmd.update_state()
            print(f"ME: {cmd.me}, Program Source: {cmd.video_source}")
            cc = CommandCarrier()
            # Time
            cc.commands.append(Cmd_Time())
            # Tally by Index
            cc.commands.append(Cmd_TlIn(cmd.me))
            # Tally by Source
            cc.commands.append(Cmd_TlSr(cmd.me))
            # Program Input (PrgI)
            cc.commands.append(Cmd_PrgI(cmd.me))
            response_list.append(cc)
        elif isinstance(cmd, Cmd_CPvI):
            cmd.update_state()
            print(f"ME: {cmd.me}, Preview Source: {cmd.video_source}")
            cc = CommandCarrier()
            # Time
            cc.commands.append(Cmd_Time())
            # Tally by Index
            cc.commands.append(Cmd_TlIn(cmd.me))
            # Tally by Source
            cc.commands.append(Cmd_TlSr(cmd.me))
            # Program Input (PrvI)
            cc.commands.append(Cmd_PrvI(cmd.me))
            response_list.append(cc)
        else:
            pass
    return response_list

if __name__ == "__main__":
    # Quick test
    for cmd_name in commands_list:
        cmd_class = commands_list[cmd_name]
        cmd_obj = cmd_class(bytes)

