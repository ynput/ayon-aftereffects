import pyblish.api

from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
    RepairAction,
    ValidateContentsOrder,
)


class ValidateInstanceInContext(pyblish.api.InstancePlugin,
                                OptionalPyblishPluginMixin):
    """Validate the instance folder is the current selected context folder.

    As it might happen that multiple worfiles are opened at same time,
    switching between them would mess with selected context. (From Launcher
    or Ftrack).

    In that case outputs might be output under wrong folder.

    Repair action will use Context folder value (from Workfiles or Launcher)
    Closing and reopening with Workfiles will refresh Context value.
    """

    label = "Validate Instance in Context"
    hosts = ["aftereffects"]
    actions = [RepairAction]
    order = ValidateContentsOrder
    optional = True
    optional_tooltip = (
        "Validate the instance context matches the current folder and task."
    )

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        folder_path = instance.data.get("folderPath")
        task = instance.data.get("task")
        context = self.get_context(instance)
        if (folder_path, task) != context:
            context_label = "{} > {}".format(*context)
            instance_label = "{} > {}".format(folder_path, task)
            raise PublishValidationError(
                message=(
                    "Instance '{}' publishes to different context than current"
                    " context: {}. Current context: {}".format(
                        instance.name, instance_label, context_label
                    )
                ),
                description=(
                    "## Publishing to a different context data\n"
                    "There are publish instances present which are publishing "
                    "into a different folder than your current context.\n\n"
                    "Usually this is not what you want but there can be cases "
                    "where you might want to publish into another folder or "
                    "shot. If that's the case you can disable the validation "
                    "on the instance to ignore it."
                ),
                detail=(
                    "This may happen if you reuse a workfile and open it in"
                    " a different context. For example, you created product"
                    " name 'renderCompositingDefault' from folder 'Robot' in"
                    " 'your_project_Robot_compositing.aep', now you opened"
                    " this workfile in a context 'Sloth' but existing product"
                    " for 'Robot' folder remained in the workfile."
                )
            )

    @classmethod
    def repair(cls, instance):
        context_folder_path, context_task = cls.get_context(
            instance)

        create_context = instance.context.data["create_context"]
        instance_id = instance.data["instance_id"]
        created_instance = create_context.get_instance_by_id(
            instance_id
        )
        created_instance["folderPath"] = context_folder_path
        created_instance["task"] = context_task
        create_context.save_changes()

    @staticmethod
    def get_context(instance):
        """Return asset, task from publishing context data"""
        context = instance.context
        return context.data["folderPath"], context.data["task"]
