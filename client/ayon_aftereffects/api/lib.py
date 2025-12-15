from __future__ import annotations
import os
import re
import json
import contextlib
import logging
import pyblish
from typing import Union

from ayon_core.pipeline.context_tools import get_current_task_entity

from .ws_stub import get_stub

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


@contextlib.contextmanager
def maintained_selection():
    """Maintain selection during context."""
    selection = get_stub().get_selected_items(True, False, False)
    try:
        yield selection
    finally:
        pass


def get_extension_manifest_path():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "extension",
        "CSXS",
        "manifest.xml"
    )


def get_unique_item_name(items, name):
    """Creates unique name for 'item'.

    Gets all item names (compositions|containers) and if 'name' is
    present in them, increases suffix by 1 (eg. creates unique item name
      - for Loader)

    Args:
        items (list): of strings, names only
        name (string):  checked value

    Returns:
        (string): name_00X (without version)
    """
    names = {}
    index_regex = re.compile(r"_\d{3}$")
    for item in items:
        item_name = index_regex.sub("", item)
        names.setdefault(item_name, 0)
        names[item_name] += 1
    occurrences = names.get(name, 0)

    return "{}_{:0>3d}".format(name, occurrences + 1)


def get_background_layers(file_url):
    """
        Pulls file name from background json file, enrich with folder url for
        AE to be able import files.

        Order is important, follows order in json.

        Args:
            file_url (str): abs url of background json

        Returns:
            (list): of abs paths to images
    """
    with open(file_url) as json_file:
        data = json.load(json_file)

    layers = list()
    bg_folder = os.path.dirname(file_url)
    for child in data['children']:
        if child.get("filename"):
            layers.append(os.path.join(bg_folder, child.get("filename")).
                          replace("\\", "/"))
        else:
            for layer in child['children']:
                if layer.get("filename"):
                    layers.append(os.path.join(bg_folder,
                                               layer.get("filename")).
                                  replace("\\", "/"))
    return layers


def get_entity_attributes(entity: dict) -> dict[str, Union[float, int]]:
    """Get attributes of folder or task entity.

    Returns:
        dict: Scene data.

    """
    attrib: dict = entity["attrib"]
    fps = attrib.get("fps", 0)
    frame_start = attrib.get("frameStart", 0)
    frame_end = attrib.get("frameEnd", 0)
    handle_start = attrib.get("handleStart", 0)
    handle_end = attrib.get("handleEnd", 0)
    resolution_width = attrib.get("resolutionWidth", 0)
    resolution_height = attrib.get("resolutionHeight", 0)
    duration = (frame_end - frame_start + 1) + handle_start + handle_end

    return {
        "fps": fps,
        "frameStart": frame_start,
        "frameEnd": frame_end,
        "handleStart": handle_start,
        "handleEnd": handle_end,
        "resolutionWidth": resolution_width,
        "resolutionHeight": resolution_height,
        "duration": duration
    }


def set_settings(
        frames, resolution, comp_ids=None, print_msg=True, entity=None):
    """Sets number of frames and resolution to selected comps.

    Args:
        frames (bool): True if set frame info
        resolution (bool): True if set resolution
        comp_ids (list[int]): specific composition ids, if empty
            it tries to look for currently selected
        print_msg (bool): True throw JS alert with msg
        entity (Optional[dict]): Entity to use attributes from to define the
            frame range, fps and resolution from. If not provided, current
            task entity is used.
    """
    frame_start = frames_duration = fps = width = height = None

    if entity is None:
        entity = get_current_task_entity()
    settings = get_entity_attributes(entity)

    msg = ''
    if frames:
        frame_start = settings["frameStart"] - settings["handleStart"]
        frames_duration = settings["duration"]
        fps = settings["fps"]
        msg += f"frame start:{frame_start}, duration:{frames_duration}, "\
               f"fps:{fps}"
    if resolution:
        width = settings["resolutionWidth"]
        height = settings["resolutionHeight"]
        msg += f"width:{width} and height:{height}"

    stub = get_stub()
    if not comp_ids:
        comps = stub.get_selected_items(True, False, False)
        comp_ids = [comp.id for comp in comps]
    if not comp_ids:
        stub.print_msg("Select at least one composition to apply settings.")
        return

    for comp_id in comp_ids:
        msg = f"Setting for comp {comp_id} " + msg
        log.debug(msg)
        stub.set_comp_properties(comp_id, frame_start, frames_duration,
                                 fps, width, height)
        if print_msg:
            stub.print_msg(msg)


def find_close_plugin(close_plugin_name, log):
    if close_plugin_name:
        plugins = pyblish.api.discover()
        for plugin in plugins:
            if plugin.__name__ == close_plugin_name:
                return plugin

    log.debug("Close plugin not found, app might not close.")


def publish_in_test(log, close_plugin_name=None):
    """Loops through all plugins, logs to console. Used for tests.

    Args:
        log (Logger)
        close_plugin_name (Optional[str]): Name of plugin with responsibility
            to close application.
    """

    # Error exit as soon as any error occurs.
    error_format = "Failed {plugin.__name__}: {error} -- {error.traceback}"
    close_plugin = find_close_plugin(close_plugin_name, log)

    for result in pyblish.util.publish_iter():
        for record in result["records"]:
            # Why do we log again? pyblish logger is logging to stdout...
            log.info("{}: {}".format(result["plugin"].label, record.msg))

        if not result["error"]:
            continue

        # QUESTION We don't break on error?
        error_message = error_format.format(**result)
        log.error(error_message)
        if close_plugin:  # close host app explicitly after error
            context = pyblish.api.Context()
            try:
                close_plugin().process(context)
            except Exception as exp:
                print(exp)