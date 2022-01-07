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


def list_blend_input_files():
    rval = set()
    for img in bpy.data.images:
        if img.filepath is not None:
            rval.add(os.path.realpath(bpy.path.abspath(img.filepath)))
    return rval


class PulseCommit(bpy.types.Operator):
    """Send the current work area to Pulse"""
    bl_idname = "pulse.commit"
    bl_label = "Pulse Commit"
    comment: bpy.props.StringProperty(name="comment", default="")
    work = None
    changes = None
    blend_inputs = []
    unknown_inputs = []

    def invoke(self, context, event):
        if bpy.data.is_dirty:
            self.report({'ERROR'}, "Current file should be saved before commit")
            return {'FINISHED'}

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
        for filepath in list_blend_input_files():
            try:
                uri = uri_std.path_to_uri(filepath)
                product = prj.get_commit_product(uri)
                self.blend_inputs.append(uri)
            except pulse_exception.PulseError:
                self.unknown_inputs.append(filepath)

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
        layout.separator()
        layout.label(text="inputs:")
        box = layout.box()
        work_inputs = [self.work.get_input_product(input_name) for input_name in self.work.get_inputs()]
        for uri in self.blend_inputs:
            if uri not in work_inputs:
                box.label(text=uri, icon='ERROR')
            else:
                box.label(text=uri)

        # unknow_inputs UI
        layout.separator()
        layout.label(text="unknown inputs:")
        box = layout.box()
        for fp in self.unknown_inputs:
            box.label(text=fp)

    def execute(self, context):
        if not self.changes:
            return {'FINISHED'}
        commit = self.work.commit(comment=self.comment)
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
