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

# ========================== R42 Custom ======================================
from . import r42_lib
import shutil
# ========================== R42 Custom ======================================

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


def get_unique_layer_name(layers, name):
    """
        Gets all layer names and if 'name' is present in them, increases
        suffix by 1 (eg. creates unique layer name - for Loader)
    Args:
        layers (list): of strings, names only
        name (string):  checked value

    Returns:
        (string): name_00X (without version)
    """
    names = {}
    for layer in layers:
        layer_name = re.sub(r'_\d{3}$', '', layer)
        if layer_name in names.keys():
            names[layer_name] = names[layer_name] + 1
        else:
            names[layer_name] = 1
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

# ========================== R42 Custom ======================================
def save_copy():
    """ Saves a copy of the current workfile and publish it. Continue working on current workfile

    """
    stub = get_stub()

    current_workfile_path = stub.get_current_path()
    increment_workfile_path = r42_lib.increment_workfile_path()
    backup_workfile_path = r42_lib.convert_path_to_backup(increment_workfile_path)

    # Save a copy (Have to do it manually since AE API doesn't have save a copy)
    stub.save()
    shutil.copy2(current_workfile_path, backup_workfile_path)
    stub.print_msg(f"Saved a copy")

    # Register that copy to the database
    r42_lib.r42_publish_workfile(backup_workfile_path)
    stub.print_msg(f"Registered in database. Done")

def update_all_reviews():
    """ Update all containers to the latest reviews, regardless of DCC based on R42 format
    """
    stub = get_stub()
    stub.print_msg("Updating all reviews, please wait")

    # Get session data
    session_data = r42_lib.generate_session_data()


    # Get all AYON Containers in Scene
    existing_containers = stub.get_metadata()

    # Get metadata in valid bins
    count = 0
    for container_metadata in existing_containers:
        # Skip non AYON container item.
        if container_metadata["id"] != "ayon.load.container":
            continue

        # Grab the repre_entity
        rep_data = r42_lib.get_representation_by_id(session_data, container_metadata["representation"])

        # Look through all available prores and compare their times
        video_data = r42_lib.get_video_data(rep_data)
        latest_prores_data = r42_lib.compare_prores_data(video_data)
        if not latest_prores_data:
            continue

        # Update the container with the latest prores
        latest_rep_id = latest_prores_data["id"]
        latest_rep_data = r42_lib.get_representation_by_id(session_data, latest_rep_id)

        if rep_data["versionId"] == latest_rep_data["versionId"]:
            continue

        r42_lib.update_container(container_metadata, latest_rep_data, stub)
        count += 1

    stub.print_msg(f"{count} Videos have been updated")

# ========================== R42 Custom ======================================

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
