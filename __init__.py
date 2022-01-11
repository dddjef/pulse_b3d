bl_info = {
    "name": "Pulse",
    "author": "Jean-Francois Sarazin",
    "version": (0, 5, 0),
    "blender": (3, 0, 0),
    "location": "Main Menu > Pulse",
    "description": "Blender 3D Pulse Addon",
    "warning": "",
    "doc_url": ""
}

import bpy
import sys
import importlib
import os
import pulse.api as pulse
import pulse.uri_standards as uri_std
import pulse.exception as pulse_exception


def collect_filepath(datablocks, path_list):
    for obj in datablocks:
        if not hasattr(obj, "filepath"):
            continue
        if obj.filepath is not None:
            path_list.add(os.path.realpath(bpy.path.abspath(obj.filepath)))

# TODO : packed texture are detected as regular
def list_blend_input_files():
    input_files = set()
    collect_filepath(bpy.data.images, input_files)
    collect_filepath(bpy.data.libraries, input_files)
    for scene in bpy.data.scenes:
        if not scene.sequence_editor:
            continue
        collect_filepath(scene.sequence_editor.sequences_all, input_files)

    return input_files


def draw_inputs(layout, input_status, input_list, icon='NONE'):
    if not input_list:
        return
    layout.separator()
    layout.label(text=input_status, icon=icon)
    box = layout.box()
    for uri in input_list:
        box.label(text=uri)


class PulseCommit(bpy.types.Operator):
    """Send the current work area to Pulse"""
    bl_idname = "pulse.commit"
    bl_label = "Pulse Commit"
    comment: bpy.props.StringProperty(name="comment", default="")
    work = None
    changes = None
    external_files = []
    registered_inputs = []
    unregistered_inputs = []
    work_inputs = []
    obsolete_inputs = []

    def invoke(self, context, event):

        self.external_files = []
        self.registered_inputs = []
        self.unregistered_inputs = []
        self.work_inputs = []
        self.obsolete_inputs = []

        if bpy.data.is_dirty:
            self.report({'ERROR'}, "Current file should be saved before commit")
            return {'FINISHED'}

        # this reload could be removed dev purpose only
        importlib.reload(pulse)

        wm = context.window_manager
        try:
            prj = pulse.get_project_from_path(bpy.data.filepath)
            uri = uri_std.convert_to_dict(uri_std.path_to_uri(bpy.data.filepath))
            resource = prj.get_resource(uri['entity'], uri['resource_type'])
            self.work = resource.get_work()
        except pulse_exception.PulseError:
            self.report({'ERROR'}, "Current blend file not in a pulse project")
            return {'FINISHED'}
        self.changes = self.work.status()

        # try to convert all blend file inputs as pulse product
        scene_pulse_inputs = []
        for filepath in list_blend_input_files():

            # collect external files, (path can't tbe converted as uri)
            try:
                uri = uri_std.path_to_uri(filepath)
            except pulse.PulseError:
                self.external_files.append(filepath)
                continue

            # collect work products
            try:
                product = prj.get_work_product(uri)
                scene_pulse_inputs.append(product)
                continue
            except pulse.PulseError:
                pass

            # collect commit products
            try:
                product = prj.get_commit_product(uri)
                scene_pulse_inputs.append(product)
            except (pulse.PulseError, pulse.PulseDatabaseMissingObject):
                pass

        work_inputs_uri = [self.work.get_input_product(input_name).uri for input_name in self.work.get_inputs()]
        for product in scene_pulse_inputs:
            # discriminate products between work, and registered and unregistered product
            if isinstance(product, pulse.WorkProduct):
                self.work_inputs.append(product.uri)
            elif product.uri in work_inputs_uri:
                self.registered_inputs.append(product.uri)
                work_inputs_uri.remove(product.uri)
            else:
                self.unregistered_inputs.append(product.uri)

        # collect current work inputs which aren't used anymore by the current blend file
        self.obsolete_inputs = work_inputs_uri

        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        if not self.changes:
            layout.label(text="No change to commit")
            return
        layout.prop(self, "comment")

        # changes UI
        layout.separator()
        layout.label(text="changes:")
        box = layout.box()
        for k in self.changes:
            box.label(text=(self.changes[k] + " : " + k))

        # inputs UI
        draw_inputs(layout, "Registered Inputs", self.registered_inputs)
        draw_inputs(layout, "Unregistered Inputs", self.unregistered_inputs, "QUESTION")
        draw_inputs(layout, "Work inputs", self.work_inputs, "ERROR")
        draw_inputs(layout, "External Files", self.external_files, "QUESTION")
        draw_inputs(layout, "Obsolete Inputs", self.obsolete_inputs, "QUESTION")

    def execute(self, context):
        if not self.changes:
            return {'FINISHED'}
        try:
            commit = self.work.commit(comment=self.comment)
        except pulse.PulseError as e:
            self.report({'ERROR'}, "Pulse Error : " + str(e))
            return {'FINISHED'}
        self.report({'INFO'}, "Commit version " + str(commit.version))
        return {'FINISHED'}


class TOPBAR_MT_pulse_menu(bpy.types.Menu):
    bl_label = "Pulse"

    def draw(self, context):
        layout = self.layout
        layout.operator("pulse.commit")

    def menu_draw(self, context):
        self.layout.menu("TOPBAR_MT_pulse_menu")


classes = (PulseCommit, TOPBAR_MT_pulse_menu)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_editor_menus.append(TOPBAR_MT_pulse_menu.menu_draw)


def unregister():
    bpy.types.TOPBAR_MT_editor_menus.remove(TOPBAR_MT_pulse_menu.menu_draw)
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
