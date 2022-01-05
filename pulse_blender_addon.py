bl_info = {
    "name": "Pulse Commit",
    "author": "Jean-Francois Sarazin",
    "version": (1, 0),
    "blender": (3, 00, 0),
    "location": "Menu > Pulse",
    "description": "Run Pulse Commit Window",
    "warning": "",
    "doc_url": ""
}

import bpy
import sys
import importlib
import os
sys.path.append(r"C:\Users\dddje\PycharmProjects\pulse\python")
import pulse.api as pulse
import pulse.uri_standards as uri_std
import pulse.exception as pulse_exception

    
class PulseCommit(bpy.types.Operator):
    """Send the current work area to Pulse"""
    bl_idname = "pulse.commit"
    bl_label = "Pulse Commit"
    comment : bpy.props.StringProperty(name="comment", default="")
    work = None
    changes = None

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
        return wm.invoke_props_dialog(self)

    def draw(self,context):
        layout = self.layout
        if not self.changes:
            layout.label(text="No change to commit")
            return
        layout.prop(self, "comment")
        layout.separator()
        layout.label(text="changes:")
        box = layout.box()
        for k in self.changes:        
            box.label(text=(self.changes[k] + " : " + k))

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
