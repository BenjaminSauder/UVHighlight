import bpy
import mathutils
import bmesh

from . import main
from . import render

MOUSE_UPDATE = False

area_id = 0


class UpdateOperator(bpy.types.Operator):
    """ This operator grabs the mouse location
    """
    bl_idname = "wm.uv_mouse_position"
    bl_label = "UV Mouse location"
    bl_options = {"REGISTER", "INTERNAL"}

    def modal(self, context, event):

        # UV_MOUSE = None
        # UV_TO_VIEW = None
        main.UV_MOUSE = None
        if event.type == 'MOUSEMOVE':
            # print(event.type, time.time())
            for area in context.screen.areas:

                if area.type == "IMAGE_EDITOR":
                    # area is somehow wrong, as it includes the header
                    for region in area.regions:
                        if region.type == "WINDOW":
                            width = region.width
                            height = region.height
                            region_x = region.x
                            region_y = region.y

                            region_to_view = region.view2d.region_to_view
                            UV_TO_VIEW = region.view2d.view_to_region

                    mouse_region_x = event.mouse_x - region_x
                    mouse_region_y = event.mouse_y - region_y

                    self.mousepos = (mouse_region_x, mouse_region_y)
                    # print(self.mousepos)

                    # clamp to area
                    if (mouse_region_x > 0 and mouse_region_y > 0 and
                                mouse_region_x < region_x + width and
                                mouse_region_y < region_y + height):
                        main.UV_MOUSE = mathutils.Vector(region_to_view(mouse_region_x, mouse_region_y))
                    # else:
                    #    main.UV_MOUSE = None

                    # print(main.UV_MOUSE)

                    if area not in render.IMAGE_EDITORS.keys():
                        global area_id
                        handle = area.spaces[0].draw_handler_add(render.draw_callback_viewUV,
                                                                 (area, UV_TO_VIEW, area_id),
                                                                 'WINDOW', 'POST_PIXEL')

                        area_id = area_id + 1
                        render.IMAGE_EDITORS[area] = handle

        main.update(do_update_preselection=True)
        main.tag_redraw_all_views()

        #handle auto uv mode convertion
        if bpy.context.scene.uv_highlight.auto_convert_uvmode:
            mode = bpy.context.scene.tool_settings.use_uv_select_sync
            if mode != self.uvmode:
                if mode:
                    bpy.ops.wm.uv_to_selection('INVOKE_DEFAULT')
                else:
                    bpy.ops.wm.selection_to_uv('INVOKE_DEFAULT')

                self.uvmode = mode

       
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global MOUSE_UPDATE
        if MOUSE_UPDATE:
            return {"FINISHED"}
        MOUSE_UPDATE = True

        #print(context.area.type)

        self.uvmode = bpy.context.scene.tool_settings.use_uv_select_sync

        self.mousepos = (0, 0)
        print("UV Highlight: running")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class UVToSelection(bpy.types.Operator):
    """ Sets the selection base on the uv selection
    """
    bl_idname = "wm.uv_to_selection"
    bl_label = "UV to selection"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        mesh = context.active_object.data
        bm = bmesh.from_edit_mesh(mesh)

        mode = bpy.context.scene.tool_settings.uv_select_mode

        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()

        verts = set()

        for f in bm.faces:
            selected = True
            for l in f.loops:
                uv = l[uv_layer]
                if uv.select:
                    verts.add(l.vert)
                else:
                    selected = False

            if mode == "FACE" or mode == "ISLAND":
                f.select_set(selected)
            else:
                f.select_set(False)

        if mode == "FACE" or mode == "ISLAND":
            bm.select_mode = {'FACE'}
        elif mode == "EDGE":
            for e in bm.edges:
                e.select_set(e.verts[0] in verts and e.verts[1] in verts)
            bm.select_mode = {'EDGE'}
        else:
            for v in bm.verts:
                v.select_set(v in verts)
            bm.select_mode = {'VERT'}

        bm.select_flush_mode()
        bmesh.update_edit_mesh(mesh)

        context.scene.tool_settings.mesh_select_mode = (
        mode == "VERTEX", mode == "EDGE", mode == "FACE" or mode == "ISLAND")

        bpy.context.scene.tool_settings.use_uv_select_sync = True

        return {"FINISHED"}

class SelectionToUV(bpy.types.Operator):
    """ Sets the selection base on the uv selection
    """
    bl_idname = "wm.selection_to_uv"
    bl_label = "Selection to UV"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        mesh = context.active_object.data
        bm = bmesh.from_edit_mesh(mesh)

        vert_selection, edge_selection, face_selection = context.scene.tool_settings.mesh_select_mode

        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()

        for f in bm.faces:
            for l in f.loops:
                #if l.vert.select:
                 l[uv_layer].select = l.vert.select

        bpy.context.scene.tool_settings.use_uv_select_sync = False
        bpy.ops.mesh.select_all(action='SELECT')

        if vert_selection:
            bpy.context.scene.tool_settings.uv_select_mode = "VERTEX"
        elif edge_selection:
            bpy.context.scene.tool_settings.uv_select_mode = "EDGE"
        elif face_selection:
            bpy.context.scene.tool_settings.uv_select_mode = "FACE"

        return {"FINISHED"}


class PinUnpinnedIslands(bpy.types.Operator):
    """ Pins uv islands which have not set any pins. Locking them into place basically
      """
    bl_idname = "wm.nt"
    bl_label = "UV to selection"
    bl_options = {"REGISTER"}