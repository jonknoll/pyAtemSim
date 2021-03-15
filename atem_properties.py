# Properties of the ATEM switcher
# This should eventually be saved/restored to a file
# Currently it gets populated with sane defaults

properties_db = {
    { 'ME0' : { 'Program-Input' : 4,
                'Preview-Input' : 5,
                'NextTrSelection' : 'background'
                }
    }






}







def get_property(name:str):
    return(properties_db.get(name))

def set_property(name:str, val):
    if name in properties_db:
        properties_db[name] = val
    else:
        raise ValueError()
