"""
Asset Exporter - Builds node network and exports geometry
"""

import hou
import os
from typing import Dict, Optional, List
from datetime import datetime


def export_asset(export_data: Dict, debug: bool = False) -> bool:
    """Export asset with the given configuration
    
    Args:
        export_data: Dictionary containing:
            - name: Asset name
            - category: Category
            - tags: List of tags
            - notes: Notes text
            - use_prepare_mesh: Whether to use pf_prepare_mesh
            - center_to_origin: Center geometry
            - scale_to_unit: Scale to unit size
            - orient: Orient option (0=keep, 1=Y up, 2=Z up)
            - selection_node: Source node
            - selected_prims: List of selected primitives
        debug: Enable debug print statements
            
    Returns:
        True if successful, False otherwise
    """
    temp_nodes = []
    original_display_node = None
    original_network_path = None
    
    try:
        # Store current display node and network editor path to restore later
        source_node = export_data['selection_node']
        parent = source_node.parent()
        for node in parent.children():
            if node.isDisplayFlagSet():
                original_display_node = node
                break
        
        # Store current network editor path
        desktop = hou.ui.curDesktop()
        network_editor = desktop.paneTabOfType(hou.paneTabType.NetworkEditor)
        if network_editor:
            original_network_path = network_editor.pwd()
        
        if debug:
            print(f"Original display node: {original_display_node.path() if original_display_node else 'None'}")
            print(f"Original network path: {original_network_path.path() if original_network_path else 'None'}")
        
        # Get export paths
        library_path = os.environ.get('PF_ASSET_LIBRARY', '')
        if not library_path:
            print("Error: PF_ASSET_LIBRARY environment variable not set")
            return False
        
        # Sanitize names for filesystem
        safe_name = _sanitize_filename(export_data['name'])
        safe_category = _sanitize_filename(export_data['category'])
        
        # Create category directory
        category_dir = os.path.join(library_path, safe_category)
        os.makedirs(category_dir, exist_ok=True)
        
        # Create thumbnails directory
        thumbnails_dir = os.path.join(category_dir, '.thumbnails', safe_name)
        os.makedirs(thumbnails_dir, exist_ok=True)
        
        # Build file paths
        asset_file = os.path.join(category_dir, f"{safe_name}.usd")
        thumbnail_static = os.path.join(thumbnails_dir, "thumb.png")
        thumbnail_turntable = thumbnails_dir
        
        # Check if asset already exists
        if os.path.exists(asset_file):
            result = hou.ui.displayMessage(
                f"Asset '{export_data['name']}' already exists.\n\nDo you want to overwrite it?",
                buttons=("Overwrite", "Cancel"),
                severity=hou.severityType.Warning,
                default_choice=1,
                close_choice=1,
                title="Asset Exists"
            )
            
            if result == 1:  # Cancel
                print("Export cancelled by user")
                return False
            
            # If overwriting, delete old database entry
            from polyfactory.asset_library.database import AssetDatabase
            db_path = os.environ.get('PF_ASSET_DB', '')
            if not db_path:
                db_path = os.path.join(library_path, 'asset_library.db')
            elif not db_path.endswith('.db'):
                # If PF_ASSET_DB is set to a directory, append the filename
                db_path = os.path.join(db_path, 'asset_library.db')
            if debug:
                print(f"Checking database for existing asset: {db_path}")
            try:
                with AssetDatabase(db_path, debug=debug) as db:
                    # Find and delete old entry by file path
                    old_assets = db.search_assets(category=export_data['category'])
                    for asset in old_assets:
                        if asset['file_path'] == asset_file:
                            db.delete_asset(asset['id'])
                            if debug:
                                print(f"Deleted old database entry for asset ID: {asset['id']}")
                            break
            except Exception as e:
                print(f"Warning: Could not delete old database entry: {e}")
        
        if debug:
            print(f"Exporting to: {asset_file}")
        
        # Build the export network
        export_node = _build_export_network(
            export_data['selection_node'],
            export_data['selected_prims'],
            export_data,
            temp_nodes,
            debug=debug
        )
        
        if not export_node:
            if debug:
                print("Error: Failed to build export network")
            return False
        
        # Export geometry
        if not _export_geometry(export_node, asset_file, temp_nodes):
            print("Error: Failed to export geometry")
            return False
        
        # Get geometry stats
        geo_stats = _get_geometry_stats(export_node)
        
        # Render turntable
        render_success = False
        try:
            from polyfactory.asset_library.render import render_turntable
            render_success = render_turntable(
                export_node,
                thumbnails_dir,
                36,  # Frame count hardcoded in lighting template USD
                asset_usd_path=asset_file,
                debug=debug
            )
        except ImportError:
            if debug:
                print("render_turntable not yet implemented, skipping render")
        except Exception as e:
            print(f"Warning: Turntable render failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Save to database
        from polyfactory.asset_library.database import AssetDatabase
        db_path = os.environ.get('PF_ASSET_DB', '')
        if not db_path:
            db_path = os.path.join(library_path, 'asset_library.db')
        elif not db_path.endswith('.db'):
            # If PF_ASSET_DB is set to a directory, append the filename
            db_path = os.path.join(db_path, 'asset_library.db')
        
        if debug:
            print(f"Database path: {db_path}")
            print(f"Database directory: {os.path.dirname(db_path)}")
            print(f"Directory exists: {os.path.exists(os.path.dirname(db_path))}")
        
        with AssetDatabase(db_path, debug=debug) as db:
            asset_id = db.add_asset(
                name=export_data['name'],
                category=export_data['category'],
                file_path=asset_file,
                thumbnail_static=thumbnail_static if render_success else None,
                thumbnail_turntable=thumbnail_turntable if render_success else None,
                poly_count=geo_stats['poly_count'],
                bbox_min=geo_stats['bbox_min'],
                bbox_max=geo_stats['bbox_max'],
                notes=export_data['notes'],
                tags=export_data['tags']
            )
            if debug:
                print(f"Asset saved to database with ID: {asset_id}")
        
        # Cleanup temporary nodes
        _cleanup(temp_nodes, original_display_node, original_network_path, debug=debug)
        
        return True
        
    except Exception as e:
        import traceback
        print(f"Error during export: {e}")
        traceback.print_exc()
        _cleanup(temp_nodes, original_display_node, original_network_path, debug=debug)
        return False


def _build_export_network(source_node: hou.SopNode, 
                         selected_prims: List, 
                         export_data: Dict,
                         temp_nodes: List,
                         debug: bool = False) -> Optional[hou.SopNode]:
    """Build the export node network
    
    Args:
        source_node: Source geometry node
        selected_prims: Selected primitives
        export_data: Export configuration
        temp_nodes: List to track temporary nodes
        debug: Enable debug print statements
        
    Returns:
        Final output node or None on error
    """
    try:
        # Get parent network
        parent = source_node.parent()
        
        # Create blast node to extract selection
        blast = parent.createNode('blast')
        blast.setInput(0, source_node)
        blast.parm('group').set(_prims_to_group_string(selected_prims))
        blast.parm('negate').set(1)  # Keep selected
        temp_nodes.append(blast)
        
        current_node = blast
        
        # Optionally add prepare mesh
        if export_data.get('use_prepare_mesh', True):
            prepare = parent.createNode('pf::prepare_mesh::1.0')
            prepare.setInput(0, current_node)
            temp_nodes.append(prepare)
            
            # Configure prepare mesh parameters
            prepare.parm('scale_to').set(export_data.get('scale_to', 1))
            prepare.parm('up').set(export_data.get('up', 1))
            prepare.parm('y_z').set(export_data.get('y_z', False))
            prepare.parm('align_x').set(export_data.get('align_x', 2))
            prepare.parm('align_y').set(export_data.get('align_y', 2))
            prepare.parm('align_z').set(export_data.get('align_z', 2))
            
            current_node = prepare
        
        # Position nodes nicely
        current_node.moveToGoodPosition()
        
        return current_node
        
    except Exception as e:
        print(f"Error building export network: {e}")
        import traceback
        traceback.print_exc()
        return None


def _prims_to_group_string(prims: List) -> str:
    """Convert list of primitives to group string
    
    Args:
        prims: List of hou.Prim objects
        
    Returns:
        Group string like "0 5-10 15"
    """
    if not prims:
        return ""
    
    # Get primitive numbers and sort
    prim_nums = sorted([p.number() for p in prims])
    
    # Build range string
    ranges = []
    start = prim_nums[0]
    end = start
    
    for num in prim_nums[1:]:
        if num == end + 1:
            end = num
        else:
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = num
            end = num
    
    # Add final range
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")
    
    return " ".join(ranges)


def _export_geometry(node: hou.SopNode, file_path: str, temp_nodes: List, debug: bool = False) -> bool:
    """Export geometry to USD file
    
    Args:
        node: Node to export from
        file_path: Destination USD file path
        temp_nodes: List to track temporary nodes
        debug: Enable debug print statements
        
    Returns:
        True if successful
    """
    try:
        # Create LOP network for USD export
        stage = hou.node("/obj").createNode("lopnet", "usd_export_temp")
        temp_nodes.append(stage)
        
        # Import SOP geometry
        sop_import = stage.createNode("sopimport", "import_geo")
        sop_import.parm("soppath").set(node.path())
        sop_import.parm("pathprefix").set("/asset")
        
        # Create USD ROP
        usd_rop = stage.createNode("usd_rop", "export_usd")
        usd_rop.setInput(0, sop_import)
        usd_rop.parm("lopoutput").set(file_path)
        usd_rop.parm("trange").set(0)  # Current frame only
        
        # Execute export
        usd_rop.parm("execute").pressButton()
        
        if debug:
            print(f"USD exported: {file_path}")
        return True
        
    except Exception as e:
        print(f"Error exporting USD: {e}")
        import traceback
        traceback.print_exc()
        return False


def _get_geometry_stats(node: hou.SopNode) -> Dict:
    """Get geometry statistics
    
    Args:
        node: Node to analyze
        
    Returns:
        Dictionary with poly_count, bbox_min, bbox_max
    """
    try:
        geo = node.geometry()
        bbox = geo.boundingBox()
        
        return {
            'poly_count': len(list(geo.prims())),
            'bbox_min': (bbox.minvec()[0], bbox.minvec()[1], bbox.minvec()[2]),
            'bbox_max': (bbox.maxvec()[0], bbox.maxvec()[1], bbox.maxvec()[2])
        }
    except Exception as e:
        # Note: Can't use debug param here as this is called without debug context
        # Keep minimal error reporting
        return {
            'poly_count': 0,
            'bbox_min': (0, 0, 0),
            'bbox_max': (0, 0, 0)
        }


def _sanitize_filename(name: str) -> str:
    """Sanitize string for use as filename
    
    Args:
        name: Original name
        
    Returns:
        Safe filename string
    """
    # Remove invalid characters
    safe = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-'))
    # Replace spaces with underscores
    safe = safe.replace(' ', '_')
    # Remove leading/trailing underscores
    safe = safe.strip('_')
    return safe


def _cleanup(temp_nodes: List, original_display_node: Optional[hou.Node], 
             original_network_path: Optional[hou.Node], debug: bool = False):
    """Remove temporary nodes and restore display flag and network path
    
    Args:
        temp_nodes: List of nodes to destroy
        original_display_node: Node to restore display flag to
        original_network_path: Network path to restore in network editor
        debug: Enable debug print statements
    """
    # Restore original display flag BEFORE destroying nodes
    # This prevents Houdini from auto-assigning the flag to another node
    if original_display_node:
        try:
            if debug:
                print(f"Restoring display flag to: {original_display_node.path()}")
            original_display_node.setDisplayFlag(True)
            original_display_node.setRenderFlag(True)
        except Exception as e:
            print(f"Warning: Could not restore display flag: {e}")
    
    # Now destroy temp nodes
    for node in temp_nodes:
        try:
            node.destroy()
        except:
            pass
    
    # Restore network editor path
    if original_network_path:
        try:
            desktop = hou.ui.curDesktop()
            network_editor = desktop.paneTabOfType(hou.paneTabType.NetworkEditor)
            if network_editor:
                if debug:
                    print(f"Restoring network path to: {original_network_path.path()}")
                network_editor.setPwd(original_network_path)
        except Exception as e:
            print(f"Warning: Could not restore network path: {e}")
