import hou
import numpy as np
import json, re, os

from pathlib import Path
from copy import deepcopy
from itertools import zip_longest
from polyfactory import utils as pfutils

FILES = {}


def add_point(pos, geo, m):
    point = geo.createPoint()
    point.setPosition(pos*m)
    return point


def draw_poly(coords, geo, is_closed=True, m=None, meta=None):
    rev = False

    # check if counterclockwise winding
    if meta['cw'] and meta.get('invert') or not meta['cw'] and not meta.get('invert'):
        rev = True

    # check if current winding need to be inverted
    if meta.get('invertnext'):
        rev = False if rev else True

    # check if matrix will generate flipped normals and compensate with reversing winding
    if m.determinant() < 0:
        rev = False if rev else True

    if rev:
        coords.reverse()

    poly = geo.createPolygon(is_closed=is_closed)

    for pos in coords:
        poly.addVertex(add_point(pos, geo, m))

    if not is_closed:
        poly.setAttribValue("edge", 1)
    return poly


def get_matrix(coords):
    """convert LDraw matrix into hou.Matrix4
    """
    c = np.array_split([float(i) for i in coords], 4)
    return hou.Matrix4(((c[1][0], c[2][0], c[3][0], 0), (c[1][1], c[2][1], c[3][1], 0), (c[1][2], c[2][2], c[3][2], 0), (*c[0], 1)))


def get_vectors(coords):
    """convert LDraw vector into hou.Vector3
    """
    c = np.array_split([float(i) for i in coords], len(coords)/3)
    v = [hou.Vector3(*i) for i in c]
    return v


def parse_dat(f, geo, m=None, meta={'cw':True}, yUp=False):

    ignoreLines = ['\n', '5']
    includeMeta = ['BFC', '!Category']
    draw = ['2', '3', '4']
    global FILES
    if not m:
        if yUp:
            m = hou.Matrix4(((1,0,0,0),(0,-1,0,0),(0,0,1,0),(0,0,0,1)))
        else:
            m = hou.Matrix4()
            m.setToIdentity()
    if not meta.get('pieceName'):
        meta['pieceName'] = 'root'
    # deepcopy metadata to avoid overwriting from other recursions
    meta = deepcopy(meta)
    if meta.get('invertnext'):
        meta['invertnext'] = False
        meta['invert'] = True

    with open(f) as dat:

        for line in dat:

            if any(line.startswith(i) for i in ignoreLines):
                continue

            cLine = line.strip()
            cmd = re.split(r'\s+', cLine)

            if cmd[0] == '0' and len(cmd) > 1 and cmd[1] in includeMeta:

                if cmd[1] == 'BFC':

                    if cmd[2] == 'INVERTNEXT':
                        meta['invertnext'] = True

                    elif 'CCW' in cmd:
                        meta['cw'] = False

            elif cmd[0] == '1':
                
                newFile = cmd[-1].replace('\\','/').lower()
                newM = get_matrix(cmd[2:-1])
                meta['pieceName'] = cmd[-1]

                parse_dat(FILES[newFile], geo, newM * m, meta)
                if meta.get('invertnext'):
                    meta['invertnext'] = False

            elif cmd[0] in draw:

                vec = get_vectors(cmd[2:])
                poly = draw_poly(vec, geo, False if cmd[0] == '2' else True, m, meta)
                poly.setAttribValue("pieceName", meta['pieceName'])
                if meta.get('invertnext'):
                    meta['invertnext'] = False


def get_files(paths):
    global FILES
    for path, prefix in paths.items():
        for p in path.glob('*.dat'):
            part = prefix +'/'+ p.name.lower() if prefix else p.name.lower()
            if not FILES.get(part):
                FILES[str(part)] = p

        for p in path.glob('*.DAT'):
            part = prefix +'/'+ p.name.lower() if prefix else p.name.lower()
            if not FILES.get(part):
                FILES[str(part)] = p


def get_lib(lDrawLib):
    
    paths = {}
    lib = Path(lDrawLib)

    partlib = lib / 'parts'
    paths[partlib] = ''
    for p in list(partlib.glob('**'))[1:]:
        paths[p] = p.stem

    partlib = lib / 'p'
    paths[partlib] = ''
    for p in list(partlib.glob('**'))[1:]:
        paths[p] = p.stem

    partlib = lib / 'UnOfficial/parts'
    paths[partlib] = ''
    for p in list(partlib.glob('**'))[1:]:
        paths[p] = p.stem

    partlib = lib / 'UnOfficial/p'
    paths[partlib] = ''
    for p in list(partlib.glob('**'))[1:]:
        paths[p] = p.stem

    get_files(paths)


def import_dat(lDrawFile, lDrawLib, geo, brand='lego', yUp = False):
    """this method is intendet to import .dat files from the LDraw part library
    do not try to import finished models in ldr format with this method
    """
    global FILES
    p = Path(lDrawFile)
    get_lib(lDrawLib)

    with open(p) as f:

        # convert brickname into conform namings
        # example: 0 Plate  1 x  2 -> plate__1_x__2
        brickName = f.readline().split(' ',1)[-1].strip().replace(' ','_').lower()
        
    parse_dat(p, geo, yUp=yUp)

    # geo.addAttrib(hou.attribType.Prim, "brickID", "")
    # geo.addAttrib(hou.attribType.Prim, "brickName", "")
    for prim in geo.prims():
        prim.setAttribValue("brickID", '{}_{}'.format(brand, p.stem))
        prim.setAttribValue("brickName", brickName)


def get_brick(brickID, houLib):
    hLib = Path(houLib) / 'library/{}.bgeo.sc'.format(brickID)
    hImport = Path(houLib) / 'import/{}.bgeo.sc'.format(brickID)

    if hLib.exists():
        return hLib

    elif hImport.exists():
        return hImport

    return None


def get_brick_save(brickID, houLib):
    brick  = get_brick(brickID, houLib)
    return brick or os.getenv('POLYFACTORY')+'/geo/unknown_brick.bgeo.sc'


def setup_ldr(lDrawFile, lDrawLib, houLib, brand='lego', yUp = False):
    """This method will prepare parts for the given ldr file
    the method does not expect geometry to be written directly in this file
    but expects only references to other .dat files
    """
    importDatNode = 'node'

    ldr = Path(lDrawFile)
    hLib = Path(houLib) / 'library'
    hImport = Path(houLib) / 'import'


    bricks = set()
    importDat = []

    with open(ldr) as f:
        for line in f:
            cLine = line.strip()
            cmd = re.split(r'\s+', cLine)
            if not cmd[0] == '1':
                continue

            # remove \\ and / to get the default mesh
            fileName = cmd[-1].split('\\')[-1].split('/')[-1].lower()
            bricks.add(fileName)

    for brick in bricks:
        brickID = '{}_{}'.format(brand, brick.split('.')[0])
        brickCheck = get_brick(brickID, houLib)
        if not brickCheck:
            importDat.append(brickID)
            
    return importDat


def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i + lv // 3], 16)/255.0 for i in range(0, lv, lv // 3))



def import_ldr(lDrawFile, lDrawLib, houLib, geo, brand='lego', yUp = False):

    ldr = Path(lDrawFile)
    colors = get_colors(lDrawLib)

    if yUp:
        globalM = hou.Matrix4(((1,0,0,0),(0,-1,0,0),(0,0,1,0),(0,0,0,1)))
    else:
        globalM = hou.Matrix4()
        globalM.setToIdentity()

    bricks = set()

    with open(ldr) as f:
        for line in f:
            cLine = line.strip()
            cmd = re.split(r'\s+', cLine)
            if not cmd[0] == '1':
                continue
            fileName = cmd[-1].split('\\')[-1].split('/')[-1].lower()
            brickID = "{}_{}".format(brand, fileName.split('.')[0])
            bricks.add(brickID)
            brickPath = get_brick(brickID, houLib)
            coords = cmd[2:14]
            m = get_matrix(coords) * globalM
            pt = add_point(hou.Vector3(0,0,0), geo, m)
            up = hou.Vector3(0,1,0) * m.extractRotationMatrix3()
            n = hou.Vector3(0,0,1) * m.extractRotationMatrix3()
            colorID = cmd[1]
            if int(colorID) >= 0 and colors.get(colorID):
                # basecolor = hou.Vector3(*hex_to_rgb(colors[colorID]['VALUE']))
                pt.setAttribValue('Cd', colors[colorID]['sRGB'].rgb())
                pt.setAttribValue('basecolor', colors[colorID]['ACEScg'].rgb())
            pt.setAttribValue('colorID', int(colorID))
            pt.setAttribValue('up', up)
            pt.setAttribValue('N', n)
            pt.setAttribValue('brickID', brickID)

    return bricks


def get_colors(LDrawLib):
    config = Path(LDrawLib) / 'LDConfig.ldr'
    colors = {}
    
    with open(config) as conf:

        for line in conf:

            cLine = line.strip()
            cmd = re.split(r'\s+', cLine)
            if len(cmd)>1 and cmd[1] == '!COLOUR':

                matIdx = 'MATERIAL' in cmd and cmd.index('MATERIAL') or len(cmd)
                c = dict(zip_longest(cmd[3:matIdx:2],cmd[4:matIdx:2], fillvalue='material'))
                matName = next((k for k, v in c.items() if v == 'material'), None)
                if not matName:
                    matName = 'PLASTIC'
                else:
                    c.pop(matName)
                c['MATERIAL'] = matName

                colors[c['CODE']] = c
                c['NAME'] = cmd[2]
                mat = dict(zip_longest(cmd[matIdx::2], cmd[matIdx+1::2]))
                if mat:
                    c['ADDMAT'] = mat
                c['sRGB'] = pfutils.hex_to_rgb(c['VALUE'])
                c['ACEScg'] = c['sRGB'].ocio_transform('Utility - sRGB - Texture', 'ACES - ACEScg', '')
                c['linear sRGB'] = c['sRGB'].ocio_transform('Utility - sRGB - Texture', 'Utility - Linear - sRGB', '')


    return colors
