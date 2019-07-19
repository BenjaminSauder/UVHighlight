
import math
import time
from collections import defaultdict

import bpy
import bmesh
import numpy as np

import mathutils

from . import util


class StoredSelections():
    pass


class Data():
    '''
    This class fetches all the necessary data from one mesh to render it's selected uv's, uv edges uv faces etc.
    To update this is pretty expensive on high density meshes, as there are sadly no foreach_get methods on bmesh,
    and to my knowledge its also not possible to get the loop data from the mesh.foreach calls in edit mode. So for
    now I just keep using bmesh, and try not to do unnecessary things.
    '''

    def __init__(self):
        self.last_update = 0
        self.is_updating = False
        self.reset()

        prefs = bpy.context.preferences.addons[__package__].preferences
        self.max_verts = prefs.max_verts

    def reset(self):
        self.target = None
        self.matrix = None

        # geometry buffers
        self.uv_vertex_selected = np.empty(0)
        self.uv_coords = np.empty(0)
        self.uv_face_selected = np.empty(0)
        self.uv_edge_selected = np.empty(0)
        self.vert_selected = np.empty(0)
        self.uv_hidden_edges = np.empty(0)

        # lookups
        self.face_to_vert = None
        self.faces_to_uvs = defaultdict(set)
        self.uvs_to_faces = defaultdict(set)
        self.uv_to_vert = {}

        # render buffers
        self.vert_buffer = []
        self.edge_buffer = ((), ())
        self.hidden_edge_buffer = ((), ())
        self.face_buffer = ((), ())

        self.preselection_verts = (), ()
        self.preselection_edges = [], ()

    def update(self, obj, update_selection_only):
        if self.is_updating:
            return False

        if not obj:
            return False

        mesh = obj.data
        if not mesh.is_editmode:
            self.reset()
            return True

        self.target = obj.name
        self.matrix = obj.matrix_world.copy()

        if len(mesh.vertices) > self.max_verts:
            return False

        self.bm = bmesh.from_edit_mesh(mesh)
        self.uv_layer = self.bm.loops.layers.uv.verify()

        # update geometry buffers
        selection_updated = False
        if update_selection_only:
            data = self.fetch_selection_data(self.bm, self.uv_layer)
            if self.has_selection_changed(data):
                self.update_stored_selections(data)
                selection_updated = True
            else:
                return False

        self.is_updating = True

        if not selection_updated:
            result = self.fetch_selection_data(self.bm, self.uv_layer)
            self.update_stored_selections(result)

        if not update_selection_only or not self.face_to_vert:
            self.fetch_mesh_data(self.bm, self.uv_layer)

        # update render buffers
        self.bm.verts.ensure_lookup_table()
        self.bm.edges.ensure_lookup_table()

        self.create_vert_buffer(self.bm)
        self.create_edge_buffer(self.bm)
        self.create_hidden_edge_buffer(self.bm)
        self.create_face_buffer(self.bm)

        self.last_update = time.perf_counter()
        self.is_updating = False

        return True

    def get_closest_uv_distance(self, mouse_pos):

        if self.vert_selected.size < 4:
            return math.inf, None

        closest_uv, index, distance = self.kd_tree.find(mouse_pos)

        return distance, closest_uv

    # make sure that get_closest_uv_distance is called before
    def update_preselection(self, mode, uv, mouse_position):

        mouse_pos = mouse_position.copy()
        mouse_pos.resize_2d()

        closest_uv = uv.copy()
        closest_uv.resize_2d()
        closest_uv = closest_uv.to_tuple()

        if closest_uv in self.uv_to_vert:
            index = self.uv_to_vert[closest_uv]
            closest_vert = self.bm.verts[index]
        else:
            return False

        if mode == 'VERTEX':
            self.preselection_verts = (
                closest_vert.co.to_tuple()), (closest_uv)
            return True

        elif mode == 'EDGE':
            self.preselection_edges = self.preselect_edges(
                closest_vert, mouse_pos)
            if self.preselection_edges:
                return True

        return False

    def fetch_selection_data(self, bm, uv_layer):
        vert_selected = []
        uv_vertex_selected = []
        uv_face_selected = []
        uv_edge_selected = []

        uv_coords = []

        for f in bm.faces:
            face_selected = True
            for l in f.loops:
                uv = l[uv_layer]
                uv_next = l.link_loop_next[uv_layer]

                if uv.select and l.vert.select:
                    uv_vertex_selected.append(l.vert.index)

                if l.vert.select:
                    vert_selected.append(l.vert.index)
                    uv_coords.append(uv.uv)

                if uv.select and uv_next.select and l.edge.select:
                    uv_edge_selected.append(l.edge.index)

                if face_selected and not uv.select:
                    face_selected = False

            if face_selected and l.face.select:
                uv_face_selected.append(l.face.index)

        result = StoredSelections()
        result.vert_selected = np.array(vert_selected)
        result.uv_vertex_selected = np.array(uv_vertex_selected)
        result.uv_edge_selected = np.array(uv_edge_selected)
        result.uv_face_selected = np.array(uv_face_selected)

        self.create_kd_tree(uv_coords)

        return result

    def update_stored_selections(self, stored_selections):
        self.vert_selected = stored_selections.vert_selected
        self.uv_vertex_selected = stored_selections.uv_vertex_selected
        self.uv_edge_selected = stored_selections.uv_edge_selected
        self.uv_face_selected = stored_selections.uv_face_selected

    def has_selection_changed(self, new_selections):
        if (np.array_equal(self.vert_selected, new_selections.vert_selected) and
                np.array_equal(self.uv_vertex_selected, new_selections.uv_vertex_selected)):
            return False

        return True

    def fetch_mesh_data(self, bm, uv_layer):
        looptris = bm.calc_loop_triangles()

        faces_to_uvs = defaultdict(set)
        uvs_to_faces = defaultdict(set)
        uv_to_vert = {}

        current = looptris[0][0].face.index
        face_to_vert = {}
        face_to_vert[current] = []

        uv_coords = []

        uv_hidden_edges = []

        for loops in looptris:

            for l in loops:
                index = l.face.index
                if index != current:
                    current = index
                    face_to_vert[current] = []

                face_to_vert[current].append(l.vert.index)

                uv = l[uv_layer]
                uv_next = l.link_loop_next[uv_layer]

                uv_co = uv.uv.to_tuple()
                uv_coords.extend(uv_co)

                if l.face.select:
                    id = uv_co, l.vert.index
                    faces_to_uvs[l.face.index].add(id)
                    uvs_to_faces[id].add(l.face.index)

                    uv_to_vert[uv_co] = l.vert.index

                # this collects the hidden edges - it's a bit complicated as I dont want to draw over currently shown uv borders
                # hence this tests if the other polygon is selected and if it is, checks the uvs if those are split.
                # one could ignore all of this - but the overdrawing looks ugly..
                else:
                    other = l.link_loop_radial_next
                    do_append = not other.face.select
                    if not do_append:
                        other_uv = other[uv_layer]
                        other_uv_next = other.link_loop_next[uv_layer]
                        do_append = uv.uv != other_uv_next.uv or uv_next.uv != other_uv.uv

                    if do_append:
                        uv_hidden_edges.append(
                            (uv.uv.to_tuple(), uv_next.uv.to_tuple()))

        self.uv_coords = np.array(uv_coords)
        self.uv_hidden_edges = np.array(uv_hidden_edges)
        self.face_to_vert = face_to_vert

        self.faces_to_uvs = faces_to_uvs
        self.uvs_to_faces = uvs_to_faces
        self.uv_to_vert = uv_to_vert

    def create_kd_tree(self, uv_coords):

        size = len(uv_coords)

        kd = mathutils.kdtree.KDTree(size)
        insert = kd.insert

        for index, co in enumerate(uv_coords):
            insert((co[0], co[1], 0), index)

        kd.balance()

        self.kd_tree = kd

    # PRESELECTION
    def preselect_edges(self, closest_vert, mouse_pos):
        uv_layer = self.uv_layer

        closest_edge = None
        closest_edge_uv = ()
        other_edge = None
        other_edge_uv = ()
        edge_distance = math.inf

        # find closest edge
        for edge in closest_vert.link_edges:
            if not edge.select:
                continue

            for l in edge.link_loops:
                uv = l[uv_layer].uv.copy()
                next_uv = l.link_loop_next[uv_layer].uv.copy()

                d = util.distance_line_point(uv, next_uv, mouse_pos)
                
                if d < edge_distance:
                    edge_distance = d
                    closest_edge = edge
                    closest_edge_uv = uv, next_uv

                # happens when the closest vert is at a corner, and both edges share that corner vert
                elif d == edge_distance:
                    min_uv, min_next_uv = closest_edge_uv
                   
                    if (min_uv - mouse_pos).length == d:
                        current = (min_next_uv - mouse_pos).to_tuple()
                    else:
                        current = (min_uv - mouse_pos).to_tuple()
                    
                    if (uv - mouse_pos).length == d:
                        candiate = (next_uv - mouse_pos).to_tuple()
                    else:
                        candiate = (uv - mouse_pos).to_tuple()
                  
                    candiate_min = min(candiate)
                    current_min = min(current)

                    if candiate_min < current_min:
                        closest_edge = edge
                        closest_edge_uv = uv, next_uv


        if not closest_edge:
            return False

        # find other uv edge
        for l in closest_edge.link_loops:
            if not l.edge.select:
                continue

            other_uv = l[uv_layer].uv
            other_next_uv = l.link_loop_next[uv_layer].uv

            uv, next_uv = closest_edge_uv

            a = uv == other_uv
            b = uv == other_next_uv
            c = next_uv == other_next_uv
            d = next_uv == other_uv

            # this little funky term makes sure to only count for split uv edges
            if not ((a or b) and (c or d)):
                other_edge = l.edge
                other_edge_uv = other_uv, other_next_uv
                break

        # create render buffers
        verts = []
        verts.append(closest_edge.verts[0].co)
        verts.append(closest_edge.verts[1].co)

        uvs = closest_edge_uv
        uvs_other = ()
        if other_edge:
            uvs_other = other_edge_uv

        return verts, (uvs, uvs_other)

    # RENDER BUFFERS

    def create_vert_buffer(self, bm):
        verts = np.unique(self.uv_vertex_selected)
        coords = [bm.verts[index].co.to_tuple() for index in verts]
        self.vert_buffer = coords

    def create_edge_buffer(self, bm):
        unique_edges = np.unique(self.uv_edge_selected)
        vert_indices = [(bm.edges[index].verts[0].index,
                         bm.edges[index].verts[1].index) for index in unique_edges]
        vert_indices = np.array(vert_indices)

        verts, indices = np.unique(vert_indices, return_inverse=True)
        coords = [bm.verts[index].co.to_tuple() for index in verts]
        indices = indices.astype(int)

        self.edge_buffer = (coords, indices)

    def create_hidden_edge_buffer(self, bm):
        if self.uv_hidden_edges.size == 0:
            self.hidden_edge_buffer = ((), ())
            return

        edges = self.uv_hidden_edges.reshape(-1, 2)

        uv, indices = np.unique(edges, return_inverse=True, axis=0)
        uv = uv.tolist()

        indices = indices.reshape(-1, 2)
        indices = indices.astype(int).tolist()

        self.hidden_edge_buffer = (uv, indices)

    def create_face_buffer(self, bm):
        loop_tris = []
        for f in self.uv_face_selected:
            loop_tris.extend(self.face_to_vert[f])

        vert_indices = np.array(loop_tris).reshape(-1, 3)
        verts, indices = np.unique(vert_indices, return_inverse=True)
        coords = [bm.verts[index].co.to_tuple() for index in verts]
        indices = indices.astype(int)

        self.face_buffer = (coords, indices)
