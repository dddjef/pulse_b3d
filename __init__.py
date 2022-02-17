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


def collect_filepath(datablocks, path_list, packable=True):
    # the packable argument should be removed as soon there's a way to detect if movieclips or sequencer clip is packed
    for obj in datablocks:
        if not hasattr(obj, "filepath"):
            continue
        if obj.filepath:
            if packable:
                if obj.packed_file:
                    continue
            path_list.add(os.path.realpath(bpy.path.abspath(obj.filepath)))


def list_blend_input_files():
    input_files = set()
    collect_filepath(bpy.data.images, input_files)
    collect_filepath(bpy.data.libraries, input_files)
    collect_filepath(bpy.data.movieclips, input_files, packable=False)
    for scene in bpy.data.scenes:
        if not scene.sequence_editor:
            continue
        collect_filepath(scene.sequence_editor.sequences_all, input_files, packable=False)

    return input_files


def draw_expandable_list(addon, layout, title, items, expanded_attr):
    if not items:
        return
    layout.separator()
    row = layout.row()
    expanded = getattr(addon, expanded_attr)
    row.prop(addon, expanded_attr,
             icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
             icon_only=True, emboss=False
             )
    row.label(text=title + "  (" + str(len(items)) + ")")
    if expanded:
        box = layout.box()
        for item in items:
            box.label(text=item)


class PulseAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    registered_inputs_expanded: bpy.props.BoolProperty(
        name="Expanded interface",
        default=False,
    )


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
    changes_expanded: bpy.props.BoolProperty(default=True)
    registered_inputs_expanded: bpy.props.BoolProperty(default=False)
    unregistered_inputs_expanded: bpy.props.BoolProperty(default=False)
    external_files_expanded: bpy.props.BoolProperty(default=False)
    obsolete_inputs_expanded: bpy.props.BoolProperty(default=False)
    work_inputs_expanded: bpy.props.BoolProperty(default=False)

    def invoke(self, context, event):

        self.external_files = []
        self.registered_inputs = []
        self.unregistered_inputs = []
        self.work_inputs = []
        self.obsolete_inputs = []

        if bpy.data.is_dirty:
            self.report({'ERROR'}, "Current file should be saved before commit")
            return {'FINISHED'}

        # enable this if you need to edit pulse library
        # importlib.reload(pulse)

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
        draw_expandable_list(self, layout, "Changes", self.changes, "changes_expanded")

        # inputs UI
        draw_expandable_list(self, layout, "Registered Inputs", self.registered_inputs, "registered_inputs_expanded")
        draw_expandable_list(self, layout, "Unregistered Inputs", self.unregistered_inputs, "unregistered_inputs_expanded")
        draw_expandable_list(self, layout, "Work inputs", self.work_inputs, "work_inputs_expanded")
        draw_expandable_list(self, layout, "External Files", self.external_files, "external_files_expanded")
        draw_expandable_list(self, layout, "Obsolete Inputs", self.obsolete_inputs, "obsolete_inputs_expanded")

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


classes = (PulseCommit, TOPBAR_MT_pulse_menu, PulseAddonPreferences)


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
