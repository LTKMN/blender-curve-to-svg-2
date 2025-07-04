bl_info = {
    'name': "Export 2D Curve to SVG 3.6+",
    'author': "Aryel Mota Gois x Brennan Letkeman",
    'version': (1, 0, 0),
    'blender': (3, 6, 0),
    'location': "File > Export > Curves to SVG",
    'description': "Export selected 2D Curves to SVG file",
    'category': "Import-Export"
}

import bpy
import bmesh
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty, IntProperty
from bpy.types import Operator, Panel
import os
from xml.etree import ElementTree
from xml.dom import minidom
from mathutils import Vector
from math import pi


def to_hex(ch):
    """Converts linear channel to sRGB and then to hexadecimal"""
    if ch < 0.0031308:
        srgb = 0.0 if ch < 0.0 else ch * 12.92
    else:
        srgb = ch ** (1.0 / 2.4) * 1.055 - 0.055
    return format(max(min(int(srgb * 255 + 0.5), 255), 0), '02x')


def col_to_hex(col):
    """Converts a Color object to hexadecimal"""
    return '#' + ''.join(to_hex(ch) for ch in col[:3])  # Only RGB, ignore alpha


def pretty_xml(elem):
    """Returns a pretty-printed XML string for the Element"""
    rough_string = ElementTree.tostring(elem, 'unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent='  ')


class EXPORT_OT_curve_svg(Operator, ExportHelper):
    """Export selected 2D curves to SVG"""
    bl_idname = "export_curve.svg"
    bl_label = "Export Curves to SVG"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".svg"
    filter_glob: StringProperty(default="*.svg", options={'HIDDEN'})
    
    # Export settings
    scale: FloatProperty(
        name="Scale",
        description="Scale factor for export",
        default=100.0,
        min=0.1,
        max=1000.0
    )
    
    precision: IntProperty(
        name="Precision",
        description="Decimal places for coordinates",
        default=3,
        min=0,
        max=10
    )
    
    minify: BoolProperty(
        name="Minify",
        description="Export as single line (minified)",
        default=False
    )
    
    include_fills: BoolProperty(
        name="Include Fills",
        description="Export fill colors from materials",
        default=True
    )

    def execute(self, context):
        return self.export_curves_to_svg(context, self.filepath)
    
    def export_curves_to_svg(self, context, filepath):
        # Get selected curve objects that are 2D
        curve_objects = [obj for obj in context.selected_objects 
                        if obj.type == 'CURVE' and obj.data.dimensions == '2D']
        
        if not curve_objects:
            self.report({'ERROR'}, "No 2D curve objects selected!")
            return {'CANCELLED'}
        
        # Calculate bounding box in Blender units first
        bbox_min = [float('inf'), float('inf')]
        bbox_max = [float('-inf'), float('-inf')]
        
        for obj in curve_objects:
            self.update_bbox(bbox_min, bbox_max, obj)
        
        if bbox_min[0] == float('inf'):
            self.report({'ERROR'}, "Could not calculate bounding box!")
            return {'CANCELLED'}
        
        # Calculate dimensions and ensure reasonable size
        bl_width = bbox_max[0] - bbox_min[0]
        bl_height = bbox_max[1] - bbox_min[1]
        
        # Auto-adjust scale if objects are very small or very large
        auto_scale = self.scale
        if bl_width > 0 and bl_height > 0:
            # Target size around 100-1000 pixels
            target_size = 500
            current_max = max(bl_width, bl_height) * self.scale
            if current_max < 10:
                auto_scale = target_size / max(bl_width, bl_height)
            elif current_max > 5000:
                auto_scale = target_size / max(bl_width, bl_height)
        
        # Calculate final SVG dimensions
        svg_width = bl_width * auto_scale
        svg_height = bl_height * auto_scale
        svg_x = bbox_min[0] * auto_scale
        svg_y = -bbox_max[1] * auto_scale  # Flip Y coordinate
        
        # Create SVG root element with proper metadata
        svg = ElementTree.Element('svg')
        svg.set('xmlns', "http://www.w3.org/2000/svg")
        svg.set('xmlns:xlink', "http://www.w3.org/1999/xlink")
        svg.set('version', "1.1")
        svg.set('x', "0px")
        svg.set('y', "0px")
        svg.set('width', f"{svg_width:.1f}px")
        svg.set('height', f"{svg_height:.1f}px")
        svg.set('viewBox', f"{svg_x:.1f} {svg_y:.1f} {svg_width:.1f} {svg_height:.1f}")
        svg.set('xml:space', "preserve")
        
        svg.append(ElementTree.Comment(f" Generated by Blender {bpy.app.version_string} - Curve to SVG Exporter "))
        
        # Main group container
        main_group = ElementTree.SubElement(svg, 'g')
        main_group.set('id', "blender-curves")
        
        # Process each curve object with proper scaling
        for obj in curve_objects:
            path_element = self.curve_to_svg_path(obj, auto_scale)
            if path_element is not None:
                main_group.append(path_element)
        
        # Write SVG file
        try:
            if self.minify:
                svg_string = '<?xml version="1.0" encoding="UTF-8"?>' + ElementTree.tostring(svg, 'unicode')
            else:
                svg_string = '<?xml version="1.0" encoding="UTF-8"?>\n'
                svg_string += '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
                svg_string += pretty_xml(svg).split('?>\n', 1)[1]  # Remove duplicate XML declaration
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(svg_string)
            
            self.report({'INFO'}, f"Exported {len(curve_objects)} curves to {filepath} (scale: {auto_scale:.1f})")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write SVG file: {str(e)}")
            return {'CANCELLED'}
    
    def curve_to_svg_path(self, obj, scale_factor):
        """Convert a curve object to SVG path element"""
        curve_data = obj.data
        
        # Collect all path data
        path_commands = []
        
        for spline in curve_data.splines:
            spline_commands = self.spline_to_path_commands(spline, obj, scale_factor)
            path_commands.extend(spline_commands)
        
        if not path_commands:
            return None
        
        # Create path element
        path = ElementTree.Element('path')
        path.set('id', obj.name)
        path.set('d', ' '.join(path_commands))
        
        # Styling - cleaner approach
        fill_color = "none"
        stroke_color = "#000000"
        stroke_width = max(1.0, 2.0 / scale_factor)  # Adaptive stroke width
        
        # Try to get color from material
        if self.include_fills and curve_data.materials:
            material = curve_data.materials[0]  # Use first material
            if material and hasattr(material, 'diffuse_color'):
                color_hex = col_to_hex(material.diffuse_color)
                fill_color = color_hex
                stroke_color = color_hex
        
        path.set('fill', fill_color)
        path.set('stroke', stroke_color)
        path.set('stroke-width', f"{stroke_width:.2f}")
        
        return path
    
    def spline_to_path_commands(self, spline, obj, scale_factor):
        """Convert a spline to SVG path commands"""
        commands = []
        
        # Apply object transformations to get world coordinates
        matrix = obj.matrix_world
        
        if spline.type == 'BEZIER':
            points = spline.bezier_points
            if not points:
                return commands
            
            # Move to first point
            first_world = matrix @ points[0].co
            first_svg = self.blender_to_svg_coords(first_world, scale_factor)
            commands.append(f"M {first_svg[0]},{first_svg[1]}")
            
            # Add curves for subsequent points
            for i in range(1, len(points)):
                prev_point = points[i-1]
                curr_point = points[i]
                
                # Transform to world coordinates
                h1_world = matrix @ prev_point.handle_right
                h2_world = matrix @ curr_point.handle_left
                p_world = matrix @ curr_point.co
                
                # Convert to SVG coordinates
                h1_svg = self.blender_to_svg_coords(h1_world, scale_factor)
                h2_svg = self.blender_to_svg_coords(h2_world, scale_factor)
                p_svg = self.blender_to_svg_coords(p_world, scale_factor)
                
                commands.append(f"C {h1_svg[0]},{h1_svg[1]} {h2_svg[0]},{h2_svg[1]} {p_svg[0]},{p_svg[1]}")
            
            # Close path if cyclic
            if spline.use_cyclic_u and len(points) > 2:
                # Connect last point back to first
                last_point = points[-1]
                first_point = points[0]
                
                h1_world = matrix @ last_point.handle_right
                h2_world = matrix @ first_point.handle_left
                p_world = matrix @ first_point.co
                
                h1_svg = self.blender_to_svg_coords(h1_world, scale_factor)
                h2_svg = self.blender_to_svg_coords(h2_world, scale_factor)
                p_svg = self.blender_to_svg_coords(p_world, scale_factor)
                
                commands.append(f"C {h1_svg[0]},{h1_svg[1]} {h2_svg[0]},{h2_svg[1]} {p_svg[0]},{p_svg[1]}")
                commands.append("Z")
        
        elif spline.type == 'POLY':
            points = spline.points
            if not points:
                return commands
            
            # Move to first point
            first_world = matrix @ Vector(points[0].co[:3])
            first_svg = self.blender_to_svg_coords(first_world, scale_factor)
            commands.append(f"M {first_svg[0]},{first_svg[1]}")
            
            # Line to subsequent points
            for i in range(1, len(points)):
                p_world = matrix @ Vector(points[i].co[:3])
                p_svg = self.blender_to_svg_coords(p_world, scale_factor)
                commands.append(f"L {p_svg[0]},{p_svg[1]}")
            
            # Close if cyclic
            if spline.use_cyclic_u:
                commands.append("Z")
        
        elif spline.type == 'NURBS':
            # Sample NURBS curves as line segments
            points = spline.points
            if not points:
                return commands
            
            resolution = max(len(points) * 8, 32)  # Higher resolution for smoother curves
            
            # Sample the curve using Blender's built-in evaluation if possible
            try:
                # Try to use Blender's curve evaluation
                depsgraph = bpy.context.evaluated_depsgraph_get()
                curve_eval = obj.evaluated_get(depsgraph)
                
                # Sample points along the curve
                sample_points = []
                for i in range(resolution + 1):
                    t = i / resolution
                    
                    # This is simplified - for production use, you'd want proper NURBS evaluation
                    # For now, we'll interpolate between control points
                    if len(points) >= 2:
                        if t == 0:
                            world_point = matrix @ Vector(points[0].co[:3])
                        elif t == 1:
                            world_point = matrix @ Vector(points[-1].co[:3])
                        else:
                            # Linear interpolation between points
                            idx = min(int(t * (len(points) - 1)), len(points) - 2)
                            local_t = (t * (len(points) - 1)) - idx
                            
                            p1 = Vector(points[idx].co[:3])
                            p2 = Vector(points[idx + 1].co[:3])
                            interpolated = p1.lerp(p2, local_t)
                            world_point = matrix @ interpolated
                        
                        svg_point = self.blender_to_svg_coords(world_point, scale_factor)
                        sample_points.append(svg_point)
                
                if sample_points:
                    commands.append(f"M {sample_points[0][0]},{sample_points[0][1]}")
                    for point in sample_points[1:]:
                        commands.append(f"L {point[0]},{point[1]}")
                    
                    if spline.use_cyclic_u:
                        commands.append("Z")
            
            except:
                # Fallback to simple point sampling
                if points:
                    first_world = matrix @ Vector(points[0].co[:3])
                    first_svg = self.blender_to_svg_coords(first_world, scale_factor)
                    commands.append(f"M {first_svg[0]},{first_svg[1]}")
                    
                    for point in points[1:]:
                        p_world = matrix @ Vector(point.co[:3])
                        p_svg = self.blender_to_svg_coords(p_world, scale_factor)
                        commands.append(f"L {p_svg[0]},{p_svg[1]}")
        
        return commands
    
    def blender_to_svg_coords(self, world_point, scale_factor):
        """Convert Blender world coordinates to SVG coordinates"""
        # Apply scale and flip Y axis
        x = round(world_point.x * scale_factor, self.precision)
        y = round(-world_point.y * scale_factor, self.precision)  # Flip Y
        return (x, y)
    
    def update_bbox(self, bbox_min, bbox_max, obj):
        """Update bounding box with object bounds"""
        if hasattr(obj, 'bound_box'):
            for corner in obj.bound_box:
                world_corner = obj.matrix_world @ Vector(corner)
                bbox_min[0] = min(bbox_min[0], world_corner.x)
                bbox_min[1] = min(bbox_min[1], world_corner.y)
                bbox_max[0] = max(bbox_max[0], world_corner.x)
                bbox_max[1] = max(bbox_max[1], world_corner.y)


class VIEW3D_PT_curve_svg_export(Panel):
    """Panel in 3D viewport for quick access"""
    bl_label = "Export Curves to SVG"
    bl_idname = "VIEW3D_PT_curve_svg_export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"
    
    def draw(self, context):
        layout = self.layout
        
        # Check if any 2D curves are selected
        curve_2d_selected = any(obj.type == 'CURVE' and obj.data.dimensions == '2D' 
                               for obj in context.selected_objects)
        
        if curve_2d_selected:
            layout.operator("export_curve.svg", text="Export Selected Curves")
        else:
            layout.label(text="Select 2D curves to export", icon='INFO')
            if context.selected_objects:
                for obj in context.selected_objects:
                    if obj.type == 'CURVE':
                        if obj.data.dimensions != '2D':
                            layout.label(text=f"{obj.name}: Not 2D", icon='ERROR')


def menu_func_export(self, context):
    self.layout.operator(EXPORT_OT_curve_svg.bl_idname, text="Curves to SVG")


def register():
    bpy.utils.register_class(EXPORT_OT_curve_svg)
    bpy.utils.register_class(VIEW3D_PT_curve_svg_export)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(EXPORT_OT_curve_svg)
    bpy.utils.unregister_class(VIEW3D_PT_curve_svg_export)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
