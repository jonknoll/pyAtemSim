# ATEM commands

import struct
import raw_commands


class ATEMCommand(object):
    def __init__(self, bytes=b''):
        self.bytes = bytes
        self.length = None
        self.code = type(self).__name__[-4:]
        self.full = ""
    
    def parse_cmd(self):
        raise NotImplementedError

    def to_bytes(self):
        raise NotImplementedError

    def _build(self, content):
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


def build_setup_commands_list():
    raw_setup_commands = [
        raw_commands.packet1,
        raw_commands.packet2,
        raw_commands.packet3,
        raw_commands.packet4,
        raw_commands.packet5,
        raw_commands.packet6,
        raw_commands.packet7,
        raw_commands.packet8,
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
                'InCm' : Cmd_InCm}

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



if __name__ == "__main__":
    # Quick test
    for cmd_name in commands_list:
        cmd_class = commands_list[cmd_name]
        cmd_obj = cmd_class(bytes)

