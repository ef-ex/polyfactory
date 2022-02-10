import re
import hou
from pathlib import Path
from itertools import zip_longest


def get_python_type(typ):
    types = {
        'string' : str,
        'float' : float,
        'int' : int,
        'bool' : bool
    }
    return types[typ]


def hex_to_rgb(hexString):

    if hexString[0] == '#':
        hexString = hexString[1:]

    rHex = hexString[0:2]
    gHex = hexString[2:4]
    bHex = hexString[4:6]

    return hou.Color(int(rHex, 16)/255.0, int(gHex, 16)/255.0, int(bHex, 16)/255.0)


def chunk_array(array, chunk, newArray = None):
    """Chunks input array into multiple arrays with length of chunksize

    Args:
        array (list): input array
        chunk (int): length of array chunks
        newArray (list, optional): array to write chunks to. Defaults to None.

    Returns:
        list: chunked array
    """
    if not newArray:
        newArray = []

    if len(array) <= chunk:
        newArray.append(array)

    elif len(array) > chunk:
        newArray.append(array[:chunk])
        chunk_array(array[chunk:], chunk, newArray)

    return newArray

