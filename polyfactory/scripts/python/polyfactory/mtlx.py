# from pxr import UsdGeom
# import os, re, hou
# from glob import glob

# node = hou.pwd()
# stage = node.editableStage()

# lib = node.node('../inputMTL')
# mats = [i.name() for i in lib.children()]
# # Add code to modify the stage.
# # Use drop down menu to select examples.

# texDir = os.path.expandvars('$HIP/KB3DTextures/4k')
# textures = glob(texDir+'/*.png')

# mapping = {
#     "base_color" : [
#         "basecolor",
#         "diffuse",
#         "diff",
#         "albedo"
#     ],
#     "displacement" : [
#         "height",
#         "displace",
#         "displacement",
#         "disp"
#     ],
#     "metalness" : [
#         "metallic",
#         "metal",
#         "metalness"
#     ],
#     "normal" : [
#         "normal",
#         "norm"
#     ],
#     "specular_roughness" : [
#         "roughness",
#         "rough"
#     ],
#     "specular" : [
#         "specular",
#         "spec",
#         "reflection",
#         "refl"
#     ],
#     "emission_color" : [
#         "emission",
#         "selfillumination",
#         "illumination",
#         "illum",
#         "emissive"
#     ],
#     "opacity" : [
#         "opacity",
#         "tranparency",
#         "cutout",
#         "trans",
#         "alpha"
#     ],
#     "transmission" : [
#         "refraction",
#         "refr",
#         "transmission"
#     ]
# }


# def get_channel_regex():
#     channels = '|'.join([channel for channels in mapping.values() for channel in channels])
#     return f".*[\\._\\- ]({channels})[\\._\\- ].*"

from pathlib import Path
import subprocess
app = 'C:/Program Files/Side Effects Software/Houdini 19.5.404/bin/imaketx.exe'
inPath = Path(r'H:\models\kitbash3d\Kitbash3D Veh Spaceships\Tex')
outPath = Path(r'H:\projects\assets\kitbash3d\spaceships\textures')

for file in inPath.glob('*'):
    if str(file).endswith('jpg'):
        txFile = outPath/file.stem
        cmd = f'"{app}" -m ocio "{file}" "{txFile}".tx'
        print(cmd)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout, stderr = process.communicate()

