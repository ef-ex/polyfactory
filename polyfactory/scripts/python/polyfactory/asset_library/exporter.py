"""
Asset Exporter - Builds node network and exports geometry
"""

import hou
import os
from typing import Dict, Optional, List
from datetime import datetime


class AssetExporter:
    """Handles the export process for asset library"""
    
    def __init__(self):
        self.export_network = None
        self.temp_nodes = []
    
    def export_asset(self, export_data: Dict) -> bool:
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
                - turntable_frames: Number of frames for turntable
                - selection_node: Source node
                - selected_prims: List of selected primitives
                
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get export paths
            library_path = os.environ.get('PF_ASSET_LIBRARY', '')
            if not library_path:
                print("Error: PF_ASSET_LIBRARY environment variable not set")
                return False
            
            # Sanitize names for filesystem
            safe_name = self._sanitize_filename(export_data['name'])
            safe_category = self._sanitize_filename(export_data['category'])
            
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
                import hou
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
                try:
                    with AssetDatabase(db_path) as db:
                        # Find and delete old entry by file path
                        old_assets = db.search_assets(category=export_data['category'])
                        for asset in old_assets:
                            if asset['file_path'] == asset_file:
                                db.delete_asset(asset['id'])
                                print(f"Deleted old database entry for asset ID: {asset['id']}")
                                break
                except Exception as e:
                    print(f"Warning: Could not delete old database entry: {e}")
            
            print(f"Exporting to: {asset_file}")
            
            # Build the export network
            export_node = self._build_export_network(
                export_data['selection_node'],
                export_data['selected_prims'],
                export_data
            )
            
            if not export_node:
                print("Error: Failed to build export network")
                return False
            
            # Export geometry
            if not self._export_geometry(export_node, asset_file):
                print("Error: Failed to export geometry")
                return False
            
            # Get geometry stats
            geo_stats = self._get_geometry_stats(export_node)
            
            # Render turntable
            render_success = False
            try:
                from polyfactory.asset_library.render import TurntableRenderer
                renderer = TurntableRenderer()
                render_success = renderer.render_turntable(
                    export_node,
                    thumbnails_dir,
                    export_data['turntable_frames'],
                    asset_usd_path=asset_file  # Pass USD file path
                )
            except ImportError:
                print("TurntableRenderer not yet implemented, skipping render")
            except Exception as e:
                print(f"Warning: Turntable render failed: {e}")
                import traceback
                traceback.print_exc()
            
            # Save to database
            from polyfactory.asset_library.database import AssetDatabase
            db_path = os.environ.get('PF_ASSET_DB', '')
            
            with AssetDatabase(db_path) as db:
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
                print(f"Asset saved to database with ID: {asset_id}")
            
            # Cleanup temporary nodes
            self._cleanup()
            
            return True
            
        except Exception as e:
            import traceback
            print(f"Error during export: {e}")
            traceback.print_exc()
            self._cleanup()
            return False
    
    def _build_export_network(self, source_node: hou.SopNode, 
                             selected_prims: List, 
                             export_data: Dict) -> Optional[hou.SopNode]:
        """Build the export node network
        
        Args:
            source_node: Source geometry node
            selected_prims: Selected primitives
            export_data: Export configuration
            
        Returns:
            Final output node or None on error
        """
        try:
            # Get parent network
            parent = source_node.parent()
            
            # Create blast node to extract selection
            blast = parent.createNode('blast')
            blast.setInput(0, source_node)
            blast.parm('group').set(self._prims_to_group_string(selected_prims))
            blast.parm('negate').set(1)  # Keep selected
            self.temp_nodes.append(blast)
            
            current_node = blast
            
            # Optionally add prepare mesh
            if export_data.get('use_prepare_mesh', True):
                prepare = parent.createNode('pf::prepare_mesh::1.0')
                prepare.setInput(0, current_node)
                self.temp_nodes.append(prepare)
                
                # Configure prepare mesh parameters to match UI values exactly
                
                # scale_to: 0=None, 1=To One, 2=Normalize
                prepare.parm('scale_to').set(export_data.get('scale_to', 1))
                
                # up: 0=X, 1=Y, 2=Z
                prepare.parm('up').set(export_data.get('up', 1))
                
                # y_z: swap Y and Z axes
                prepare.parm('y_z').set(export_data.get('y_z', False))
                
                # align_x/y/z: 0=None, 1=max, 2=center, 3=min
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
    
    def _prims_to_group_string(self, prims: List) -> str:
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
    
    def _export_geometry(self, node: hou.SopNode, file_path: str) -> bool:
        """Export geometry to USD file
        
        Args:
            node: Node to export from
            file_path: Destination USD file path
            
        Returns:
            True if successful
        """
        try:
            # Create LOP network for USD export
            stage = hou.node("/stage")
            if not stage:
                stage = hou.node("/obj").createNode("lopnet", "usd_export_temp")
                self.temp_nodes.append(stage)
            else:
                stage = hou.node("/obj").createNode("lopnet", "usd_export_temp")
                self.temp_nodes.append(stage)
            
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
            
            print(f"USD exported: {file_path}")
            return True
            
        except Exception as e:
            print(f"Error exporting USD: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_geometry_stats(self, node: hou.SopNode) -> Dict:
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
            print(f"Error getting geometry stats: {e}")
            return {
                'poly_count': 0,
                'bbox_min': (0, 0, 0),
                'bbox_max': (0, 0, 0)
            }
    
    def _sanitize_filename(self, name: str) -> str:
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
    
    def _cleanup(self):
        """Remove temporary nodes"""
        for node in self.temp_nodes:
            try:
                node.destroy()
            except:
                pass
        self.temp_nodes = []
