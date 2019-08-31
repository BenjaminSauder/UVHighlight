import bpy

def toggle_preselection(self, context):
    from .main import updater
    updater.handle_toggle_preselection_state()

class UVHighlightSettings(bpy.types.PropertyGroup):
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'TOOLS'

    show_in_viewport : bpy.props.BoolProperty(default=True)
    show_preselection : bpy.props.BoolProperty(default=True, update=toggle_preselection)
    # show_udim_indices = bpy.props.BoolProperty(default=False)



