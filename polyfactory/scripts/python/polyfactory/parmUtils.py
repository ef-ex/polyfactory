import hou

VALUETYPES = [
    'Int',
    'Float',
    'String',
    'Toggle',
    'Menu'
    ]


def get_multiparm(multi):
    """Get parms of multiparm parameter

    Args:
        multi (hou.Parm): multiparmater

    Returns:
        generator: generator with hou.Parm objects for each parm in multiparmindex
    """
    return zip(*[iter(multi.multiParmInstances())]*multi.multiParmInstancesPerItem())


def get_multiparm_dict(multi):
    """Get parms of multiparm as dictionary

    Args:
        multi (hou.Parm): multiparmater

    Returns:
        list: list of dictionaries, each dict has _index key for parm index, index number is removed from parm name dict key
    """
    offset = multi.parmTemplate().tags().get('multistartoffset', 1)
    parameters = []
    for index, params in enumerate(get_multiparm(multi)):
        parameters.append({parm.name()[:-len(str(index+1))] : parm for parm in params})
        _dict = parameters[-1]
        _dict['_index'] = index+int(offset)
    return parameters


def get_type(parm):
    if isinstance(parm, hou.Parm):
        return parm.parmTemplate().type().name()
    return None


def get_menu_value(parm, label=False):
    index = parm.eval()
    return parm.menuLabels()[index] if label else parm.menuItems()[index]


