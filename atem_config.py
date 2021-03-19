# Properties of the ATEM switcher
# This should eventually be saved/restored to a file
# Currently it gets populated with sane defaults

import xml.etree.ElementTree as ET
from collections import defaultdict
from pprint import pprint

conf_db = {}

video_sources = {
    0 : "Black",
    1 : "Input 1",
    2 : "Input 2",
    3 : "Input 3",
    4 : "Input 4",
    5 : "Input 5",
    6 : "Input 6",
    7 : "Input 7",
    8 : "Input 8",
    9 : "Input 9",
    10 : "Input 10",
    11 : "Input 11",
    12 : "Input 12",
    13 : "Input 13",
    14 : "Input 14",
    15 : "Input 15",
    16 : "Input 16",
    17 : "Input 17",
    18 : "Input 18",
    19 : "Input 19",
    20 : "Input 20",
    1000 : "Color Bars",
    2001 : "Color 1",
    2002 : "Color 2",
    3010 : "Media Player 1",
    3011 : "Media Player 1 Key",
    3020 : "Media Player 2",
    3021 : "Media Player 2 Key",
    4010 : "Key 1 Mask",
    4020 : "Key 2 Mask",
    4030 : "Key 3 Mask",
    4040 : "Key 4 Mask",
    5010 : "DSK 1 Mask",
    5020 : "DSK 2 Mask",
    6000 : "Super Source",
    7001 : "Clean Feed 1",
    7002 : "Clean Feed 2",
    8001 : "Auxilary 1",
    8002 : "Auxilary 2",
    8003 : "Auxilary 3",
    8004 : "Auxilary 4",
    8005 : "Auxilary 5",
    8006 : "Auxilary 6",
    10010 : "ME 1 Prog",
    10011 : "ME 1 Prev",
    10020 : "ME 2 Prog",
    10021 : "ME 2 Prev",
}

# Specific device sources (can't really be determined from the config file)
# Match by config file <Profile product=xxxxxx>
DEVICE_VIDEO_SOURCES = {
    "ATEM Television Studio HD" : [0,1,2,3,4,5,6,7,8,1000,2001,2002,3010,3011,3020,3021,4010,5010,5020,10010,10011,7001,7002,8001]
    }

audio_sources = {
    1 : "Input 1",
    2 : "Input 2",
    3 : "Input 3",
    4 : "Input 4",
    5 : "Input 5",
    6 : "Input 6",
    7 : "Input 7",
    8 : "Input 8",
    9 : "Input 9",
    10 : "Input 10",
    11 : "Input 11",
    12 : "Input 12",
    13 : "Input 13",
    14 : "Input 14",
    15 : "Input 15",
    16 : "Input 16",
    17 : "Input 17",
    18 : "Input 18",
    19 : "Input 19",
    20 : "Input 20",
    1001 : "XLR",
    1101 : "AES/EBU",
    1201 : "RCA",
    2001 : "MP1",
    2002 : "MP2",
}





def config_init(config_file):
    global conf_db
    root = ET.parse(config_file).getroot()
    conf_db = etree_to_dict(root)
    conf_db = manipulate_sections(conf_db)
    return conf_db



# Borrowed this nifty algorithm from here:
# https://stackoverflow.com/questions/7684333/converting-xml-to-dictionary-using-elementtree

def etree_to_dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)

    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k: v[0] if len(v) == 1 else v
                     for k, v in dd.items()}}

    if t.attrib:
        d[t.tag].update((k, v)
                        for k, v in t.attrib.items())
    
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
              d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d

# push subnode keys up one level and list dictionaries by index
def push_up_and_index(tree, node, subnode, index_name):
    node_list = tree[node][subnode]
    if type(node_list) != list:
        node_list = [node_list]
    new_node_list = {}
    for nn in node_list:
        new_node_list[int(nn[index_name])] = nn
    tree[node] = new_node_list
    return tree

# make it easier to find commonly used things
def manipulate_sections(conf_db):
    # Take out top level "Profile"
    new_db = conf_db['Profile']

    # push mix effect blocks up one level and list dictionaries by index
    new_db = push_up_and_index(new_db, "MixEffectBlocks", "MixEffectBlock", "index")
    # me_list = new_db['MixEffectBlocks']['MixEffectBlock']
    # if type(me_list) != list:
    #     me_list = [me_list]
    # new_me_list = {}
    # for me in me_list:
    #     new_me_list[int(me['index'])] = me
    # new_db['MixEffectBlocks'] = new_me_list

    # push downstream keys up one level and list dictionaries by index
    new_db = push_up_and_index(new_db, "DownstreamKeys", "DownstreamKey", "index")
    # dsk_list = new_db['DownstreamKeys']['DownstreamKey']
    # if type(dsk_list) != list:
    #     dsk_list = [dsk_list]
    # new_dsk_list = {}
    # for dsk in dsk_list:
    #     new_dsk_list[int(dsk['index'])] = dsk
    # new_db['DownstreamKeys'] = new_dsk_list

    # push downstream keys up one level and list dictionaries by index
    new_db = push_up_and_index(new_db, "ColorGenerators", "ColorGenerator", "index")

    # push inputs keys up one level and list dictionaries by id
    new_db['Settings'] = push_up_and_index(new_db['Settings'], "Inputs", "Input", "id")

    return new_db


def get_config(name:str):
    return(conf_db.get(name))

def set_config(name:str, val):
    if name in conf_db:
        conf_db[name] = val
    else:
        raise ValueError()




if __name__ == "__main__":
    db = config_init("default_config.xml")
    pprint(db)

