import hou
import os

cmds = '{}/vex/wrapper'.format(os.getenv('POLYFACTORY'))

def ocio_transform(spacein = 'Utility - sRGB - Texture', spaceout = 'ACES - ACEScg', colorin = hou.Vector3(0.5,0.5,0.5)):
    vex = f'{cmds}/to_colorspace.vfl'
    result = hou.runVex(vex, {'from':spacein, 'to':spaceout, 'colorin':[colorin]})
    return hou.Color(result['colorout'])