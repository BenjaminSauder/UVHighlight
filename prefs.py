import bpy

debug = True


class Addon(bpy.types.AddonPreferences):
    bl_idname = __package__

    max_verts = bpy.props.IntProperty("Max Verts", default=50000)

    view3d_selection_verts_edges = bpy.props.FloatVectorProperty(name="view3d_selection_verts_edges",
                                                                 subtype="COLOR",
                                                                 default=(
                                                                     0, 1.0, 1.0, 1.0),
                                                                 size=4)

    view3d_selection_faces = bpy.props.FloatVectorProperty(name="view3d_selection_faces",
                                                           subtype="COLOR",
                                                           default=(
                                                               0, 1.0, 1.0, 0.4),
                                                           size=4)

    view3d_preselection_verts_edges = bpy.props.FloatVectorProperty(name="view3d_preselection_verts_edges ",
                                                                    subtype="COLOR",
                                                                    default=(
                                                                        1.0, 0.0, 0.0, 1.0),
                                                                    size=4)

    view3d_preselection_faces = bpy.props.FloatVectorProperty(name="view3d_preselection_faces",
                                                              subtype="COLOR",
                                                              default=(
                                                                  0.15, 0.15, 0.15, 1.0),
                                                              size=4)

    uv_preselection_verts_edges = bpy.props.FloatVectorProperty(name="uv_preselection_verts_edges",
                                                                subtype="COLOR",
                                                                default=(
                                                                    1.0, 1.0, 1.0, 1.0),
                                                                size=4)

    uv_preselection_faces = bpy.props.FloatVectorProperty(name="uv_preselection_faces",
                                                          subtype="COLOR",
                                                          default=(
                                                              0.15, 0.15, 0.15, 1.0),
                                                          size=4)

    uv_hidden_faces = bpy.props.FloatVectorProperty(name="uv_hidden_faces",
                                                    subtype="COLOR",
                                                    default=(
                                                        0.15, 0.15, 0.15, 1.0),
                                                    size=4)

    # udim_markers = bpy.props.FloatVectorProperty(name="udim_markers",
    #                                              subtype="COLOR",
    #                                              default=(1.0, 1.0, 1.0, 0.25),
    #                                              size=4)

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        col = row.column()

        col.prop(self, "max_verts", text="Maximum verts")
        col.separator()
        col.separator()

        col.prop(self, "view3d_selection_verts_edges",
                 text="3D View uv verts/edges selection")
        col.prop(self, "view3d_preselection_verts_edges",
                 text="3D View uv verts/edges pre-selection")
        col.prop(self, "view3d_selection_faces",
                 text="3D View uv faces selection")
        col.prop(self, "view3d_preselection_faces",
                 text="3D View uv faces pre-selection")
        col.prop(self, "uv_preselection_verts_edges",
                 text="Image Editor verts/edges pre-selection")
        col.prop(self, "uv_preselection_faces",
                 text="Image Editor faces/islands pre-selection")
        col.prop(self, "uv_hidden_faces",
                 text="Image Editor non selected faces")
        # col.prop(self, "udim_markers", text="Image Editor UDIM tiles and label")
