import hou


def get_drop_context():
    """get the context where the drop happened

    Returns:
        hou.NetowrkEditor: paneTab where drop happened
        hou.Node: node in which drop happened
        hou.NodeTypeCategory: nodetype context of drop
        hou.Vector2: position of mouse cursor at drop in paneTab
        tuple: array of selected nodes
    """
    pane = [tab for tab in hou.ui.paneTabs() if isinstance(tab, hou.NetworkEditor) and tab.isCurrentTab()][-1]
    pos = pane.cursorPosition()
    node = pane.pwd()
    type = node.type().childTypeCategory()
    sel = hou.selectedNodes()
    return pane, node, type, pos, sel


def dropAccept(files):
    pane, node, typ, pos, sel = get_drop_context()
    print(pane)
    print(node)
    print(typ)
    print(pos)
    print(sel)
    print('Custom drop')
    print(files)
    return True