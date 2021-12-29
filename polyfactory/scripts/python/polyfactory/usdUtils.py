from pxr import Sdf

def get_sdf_type(typ):
    """
    get Sdf Value Type

    Args:
        typ (str) : requested usd type
    Returns:
        Sdf.ValueTypeName
    """
    sdfTypes = {
        'bool': Sdf.ValueTypeNames.Bool,
        'bool[]': Sdf.ValueTypeNames.BoolArray,
        'string': Sdf.ValueTypeNames.String,
        'string[]': Sdf.ValueTypeNames.StringArray, 
        'token': Sdf.ValueTypeNames.Token,
        'token[]': Sdf.ValueTypeNames.TokenArray,
        'asset': Sdf.ValueTypeNames.Asset,
        'asset[]': Sdf.ValueTypeNames.AssetArray,

        'int': Sdf.ValueTypeNames.Int,
        'int[]': Sdf.ValueTypeNames.IntArray,
        'half': Sdf.ValueTypeNames.Half,
        'half[]': Sdf.ValueTypeNames.HalfArray,
        'int64': Sdf.ValueTypeNames.Int64,
        'int64[]': Sdf.ValueTypeNames.Int64Array,
        'float': Sdf.ValueTypeNames.Float,
        'float[]': Sdf.ValueTypeNames.FloatArray,
        'double': Sdf.ValueTypeNames.Double,
        'double[]': Sdf.ValueTypeNames.DoubleArray,

        'int2': Sdf.ValueTypeNames.Int2,
        'int2[]': Sdf.ValueTypeNames.Int2Array, 
        'half2': Sdf.ValueTypeNames.Half2,
        'half2[]': Sdf.ValueTypeNames.Half2Array, 
        'float2': Sdf.ValueTypeNames.Float2,
        'float2[]': Sdf.ValueTypeNames.Float2Array,
        'double2': Sdf.ValueTypeNames.Double2,
        'double2[]': Sdf.ValueTypeNames.Double2Array,

        'int3': Sdf.ValueTypeNames.Int3,
        'int3[]': Sdf.ValueTypeNames.Int3Array, 
        'half3': Sdf.ValueTypeNames.Half3,
        'half3[]': Sdf.ValueTypeNames.Half3Array, 
        'float3': Sdf.ValueTypeNames.Float3,
        'float3[]': Sdf.ValueTypeNames.Float3Array,
        'double3': Sdf.ValueTypeNames.Double3,
        'double3[]': Sdf.ValueTypeNames.Double3Array, 

        'int4': Sdf.ValueTypeNames.Int4,
        'int4[]': Sdf.ValueTypeNames.Int4Array,
        'half4': Sdf.ValueTypeNames.Half4,
        'half4[]': Sdf.ValueTypeNames.Half4Array,
        'float4': Sdf.ValueTypeNames.Float4,
        'float4[]': Sdf.ValueTypeNames.Float4Array,
        'double4': Sdf.ValueTypeNames.Double4,
        'double4[]': Sdf.ValueTypeNames.Double4Array, 

        'point3f': Sdf.ValueTypeNames.Point3f,
        'point3f[]': Sdf.ValueTypeNames.Point3fArray,
        'point3d': Sdf.ValueTypeNames.Point3d,
        'point3d[]': Sdf.ValueTypeNames.Point3dArray,

        'vector3f': Sdf.ValueTypeNames.Vector3f,
        'vector3f[]': Sdf.ValueTypeNames.Vector3fArray,
        'vector3d': Sdf.ValueTypeNames.Vector3d,
        'vector3d[]': Sdf.ValueTypeNames.Vector3dArray,

        'normal3f': Sdf.ValueTypeNames.Normal3f,
        'normal3f[]':Sdf.ValueTypeNames.Normal3fArray,
        'normal3d': Sdf.ValueTypeNames.Normal3f,
        'normal3d[]':Sdf.ValueTypeNames.Normal3dArray,

        'color3f': Sdf.ValueTypeNames.Color3f,
        'color3f[]': Sdf.ValueTypeNames.Color3fArray,
        'color3d': Sdf.ValueTypeNames.Color3d,
        'color3d[]': Sdf.ValueTypeNames.Color3dArray,
        'color3h': Sdf.ValueTypeNames.Color3h,
        'color3h[]': Sdf.ValueTypeNames.Color3hArray,

        'color4f': Sdf.ValueTypeNames.Color4f,
        'color4f[]': Sdf.ValueTypeNames.Color4fArray,
        'color4d': Sdf.ValueTypeNames.Color4d,
        'color4d[]': Sdf.ValueTypeNames.Color4dArray,
        'color4h': Sdf.ValueTypeNames.Color4h,
        'color4h[]': Sdf.ValueTypeNames.Color4hArray,

        'quath': Sdf.ValueTypeNames.Quath,
        'quath[]': Sdf.ValueTypeNames.QuathArray,
        'quatf': Sdf.ValueTypeNames.Quatf,
        'quatf[]': Sdf.ValueTypeNames.QuatfArray,
        'quatd': Sdf.ValueTypeNames.Quatd,
        'quatd[]': Sdf.ValueTypeNames.QuatdArray,

        'matrix2d': Sdf.ValueTypeNames.Matrix2d, 
        'matrix3d': Sdf.ValueTypeNames.Matrix3d, 
        'matrix4d': Sdf.ValueTypeNames.Matrix4d,
    }
    return sdfTypes[typ]


def get_prims_at_path(stage, path, primType):
    """
    generator which returns all prims of type
    which are child of given path
        
    stage (pxr.Usd.Stage): stage from which to read from
    path (str): usd path where to search for prims
    primType (str): usd primtype to search for

    Return:
        primpath, primname
    """
    settings = stage.GetPrimAtPath(path)
    settingsarray = []
    for i in settings.GetChildren():
        if i.GetTypeName() == primType:
            yield i.GetPath().pathString
            yield i.GetName()
