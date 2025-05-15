from ayon_core.pipeline import context_tools, anatomy, get_representation_path
import ayon_api
from ayon_api import operations as op
from ayon_core.lib import (
    ayon_info,
    dateutils,
    get_ayon_username,
    path_tools,
)
import os
import uuid
import copy
import re
from datetime import datetime

''' ------------------
SIMPLE LOGGING
------------------ '''
import logging

def log_text_to_file(log_file, text, mode):
    logger = logging.getLogger("R42_Debug_Adobe")
    logger.setLevel(logging.DEBUG)

    handler = logging.FileHandler(log_file, mode, 'utf-8')
    formatter = logging.Formatter("%(levelname)s:%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.debug(text)

''' ------------------
LIB FUNCTIONS TO AVOID CYCLIC IMPORTS
------------------ '''
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

''' ------------------
GENERAL GETTER FUNCTIONS
------------------ '''
def generate_session_data():
    """
    Generates the current session data.
    Is useful for every other operation when in context

    CHANGES
    asset_name => folder_path
    :return:
        data (dict): The session data.
    """
    context_data = context_tools.get_current_context()
    template_data = context_tools.get_current_context_template_data()
    workstation_data = ayon_info.get_workstation_info()
    timestamp = dateutils.get_formatted_current_time()
    date_time_data = dateutils.get_datetime_data()
    try:
        folder_info = ayon_api.get_folder_by_path(context_data["project_name"], context_data["asset_name"])
        asset_name = context_data["asset_name"]
    except KeyError:
        folder_info = ayon_api.get_folder_by_path(context_data["project_name"], context_data["folder_path"])
        asset_name = context_data["folder_path"]

    anatomy_data = {**template_data, **date_time_data, "username": workstation_data["username"]}

    data = {
        "project_name": context_data["project_name"],
        "project_code": template_data["project"]["code"],
        "asset_name": asset_name,
        "asset_id": folder_info["id"],
        "anatomy_data": anatomy_data,
        "task_name": template_data["task"]["name"],
        "task_type": template_data["task"]["type"],
        "host_name": template_data["app"],
        "time": timestamp,
        "user": template_data["user"],
        "machine": workstation_data["hostname"],
        "fps": folder_info['attrib']['fps']
    }
    return data

def get_current_username():
    return get_ayon_username()

def get_rootless_path(session_data, filepath):
    project_anatomy = anatomy.Anatomy(session_data["project_name"])

    workdir, filename = os.path.split(filepath)
    success, rootless_dir = project_anatomy.find_root_template_from_path(workdir)
    return "/".join([
        os.path.normpath(rootless_dir).replace("\\", "/"),
        filename
    ])

def get_unfilled_anatomy(session_data, anatomy_template_name, anatomy_type="path"):
    """
    Get the unfilled anatomy template
    :param
        session_data (dict): The current session data
        anatomy_template_name (string): The template name to query. i.e publish_image
        anatomy_type (string): The type of the anatomy to query. i.e path, folder, file

    :return:
        unfilled_anatomy (string): The unfilled anatomy
    """
    project_anatomy = anatomy.Anatomy(session_data["project_name"])

    try:
        # DEPRECATED
        unfilled_anatomy = project_anatomy.templates_obj[anatomy_template_name][anatomy_type]
    except KeyError:
        template_keys = anatomy_template_name.split("_", 1)
        unfilled_anatomy = project_anatomy.get_template_item(template_keys[0],
                                                             template_keys[1],
                                                             anatomy_type)

    return unfilled_anatomy

def increment_workfile_path():
    # Get EXT
    ext = 'aep'

    # Check for last version
    session_data = generate_session_data()
    try:
        unfilled_dir = get_unfilled_anatomy(session_data, "work_default", "folder")
        unfilled_anatomy = get_unfilled_anatomy(session_data, "work_default", "path")
    except KeyError:
        return None

    template_data = copy.deepcopy(session_data["anatomy_data"])
    template_data["ext"] = ext
    filled_dir = unfilled_dir.format_strict(template_data)
    filter_list = [ext]
    last_version = path_tools.get_last_version_from_path(filled_dir, filter_list)

    # Construct new file path
    if not last_version:
        print("NEW FILE")
        template_data["version"] = "001"
        template_filled = unfilled_anatomy.format_strict(template_data)
        return os.path.normpath(template_filled)

    else:
        print("HAVE LAST VERSION")
        full_path = os.path.join(filled_dir, last_version)
        increment_path = path_tools.version_up(full_path)
        return os.path.normpath(increment_path)

def convert_path_to_backup(file_path):
    directory_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)

    all_files = os.listdir(directory_name)
    numbers = []

    for name in all_files:
        if re.search(r"v(?=\d)", name, re.IGNORECASE):
            continue
        matches = re.findall(r'\d+', name)
        if matches:
            numbers.append(int(matches[-1]))

    max_number = max(numbers) if numbers else 1
    max_number_with_padding = str(max_number+1).zfill(3)

    # Remove v from base_name
    match = re.match(r"(.*)_v(\d+)(\..*)", base_name)
    if match:
        base, version, fileext = match.groups()
        new_name = f"{base}_{max_number_with_padding}{fileext}"
        new_path = os.path.join(directory_name, new_name)
        return new_path
    else:
        return file_path

def get_task_by_name(session_data, task_name=None):
    if not task_name:
        task_name = session_data['task_name']
    project_name = session_data["project_name"]
    folder_id = session_data["asset_id"]
    task_data = ayon_api.get_task_by_name(project_name=project_name,
                                          folder_id=folder_id,
                                          task_name=task_name)
    return task_data

def get_version_by_id(session_data, version_id):
    project_name = session_data["project_name"]
    version_data = ayon_api.get_version_by_id(project_name=project_name,
                                              version_id=version_id)
    return version_data

def get_representation_by_id(session_data, representation_id):
    project_name = session_data["project_name"]
    representation_data = ayon_api.get_representation_by_id(project_name=project_name,
                                                            representation_id=representation_id)
    return representation_data

''' ------------------
GENERAL CREATOR FUNCTIONS
------------------ '''
def create_operation_link_session():
    return op.OperationsSession()


def create_entity_in_database(session_data, entity_type, entity_doc, op_session=None):
    """
    :param
    entity_type (string): If it is a product, a version or a representation
    """
    if not entity_doc:
        raise Exception("There isn't any entity doc")

    if not op_session:
        op_session = op.OperationsSession()
    op_session.create_entity(session_data["project_name"], entity_type, entity_doc)
    op_session.commit()


def create_workfile_doc(session_data, file_path):
    rootless_path = get_rootless_path(session_data, file_path)

    task_name = session_data["task_name"]
    task_data = get_task_by_name(session_data, task_name)
    task_id = task_data["id"]

    extension = os.path.splitext(rootless_path)[1]
    username = get_current_username()

    workfile_info = {
        "id": uuid.uuid4().hex,
        "path": rootless_path,
        "taskId": task_id,
        "attrib": {
            "extension": extension,
            "description": ""
        },
        "createdBy": username,
        "updatedBy": username,
    }
    return workfile_info



''' ------------------
WORKFILE FUNCTIONS
------------------ '''
def r42_publish_workfile(file_path):
    session_data = generate_session_data()
    op_session = create_operation_link_session()
    workfile_info = create_workfile_doc(session_data, file_path)
    create_entity_in_database(session_data, "workfile", workfile_info, op_session)

''' ------------------
UPDATE FUNCTIONS
------------------ '''
def get_video_data(repre_data):
    video_dict = {}
    folder_name = repre_data['context']['folder']['name']
    project_name = repre_data['context']['project']['name']
    folder_data = ayon_api.get_folder_by_name(project_name=project_name,
                                              folder_name=folder_name)
    # ---- Query the products ----
    product_list = ayon_api.get_products(project_name=project_name,
                                         folder_ids=[folder_data['id']],
                                         product_types=["review", "render"],
                                         )
    product_list = list(product_list)

    # ---- Query the versions ----
    version_list = []
    for product in product_list:
        product_id = product["id"]
        version_data_generator = ayon_api.get_versions(project_name=project_name,
                                                       product_ids=[product_id])
        version_data = [*version_data_generator]
        for v in version_data:
            version_list.append(v)

    # ---- Query the representation ----
    for version in version_list:
        try:
            representation_data = ayon_api.get_representations(project_name=project_name,
                                                               version_ids=[version['id']])
            rep_data_as_list = [*representation_data]
            version_name = version["name"]

            for rep in rep_data_as_list:
                valid = check_valid_video_representation(rep, version_name)
                if valid == 0:
                    continue

                file_path = rep['attrib']['path']
                modified_time = os.path.getmtime(file_path)
                modified_time_format = datetime.fromtimestamp(modified_time).isoformat()

                # ---- Extract out the essential data ----
                data = {
                    "id": rep["id"],
                    "subset_name": rep["context"]["subset"],
                    "rep_path": rep['attrib']['path'],
                    "project_name": project_name,
                    "project_code": rep["context"]["project"]["code"],
                    "shot_name": rep["context"]["folder"]["name"],
                    "folder_path": folder_data['path'],
                    "rep_created": modified_time_format
                }

                video_dict[rep["context"]["subset"]] = data

        except TypeError:
            continue

    return video_dict

def check_valid_video_representation(rep_data, version_name):
        # ---- Check if it is ProRes representation ----
        '''
        0 - Not Valid
        1 - Review
        2 - Exrs
        '''
        project_name = rep_data['context']['project']['name']
        try:
            if rep_data["context"]["output"] not in ("ProRes", "1080p", "4K"):
                return 0
        except KeyError:
            return 0

        # ---- Check if it is storyboard comp ----
        task_type = rep_data["context"]["task"]["type"]
        if task_type == "Storyboard Comp":
            return 0

        # ---- Check if the folder is shot context ----
        shot_name = rep_data["context"]["folder"]["name"]
        folder_data = ayon_api.get_folder_by_name(project_name=project_name,
                                                  folder_name=shot_name)
        if folder_data["folderType"] != "Shot":
            return 0

        # ---- Check if the version is a hero ----
        if version_name == "HERO":
            return 0

        return 1

def compare_prores_data(video_dict):
    latest_instance = None
    for key in video_dict:
        instance = video_dict[key]
        if not latest_instance:
            latest_instance = instance
            continue

        current_time = instance["rep_created"]
        latest_time = latest_instance["rep_created"]

        # Parse the datetime strings into datetime objects
        datetime_obj1 = datetime.fromisoformat(current_time)
        datetime_obj2 = datetime.fromisoformat(latest_time)

        # Compare the datetime objects
        if datetime_obj1 > datetime_obj2:
            latest_instance = instance
        else:
            continue

    return latest_instance

def update_container(orig_container, repre_data, stub):
    # Get new container name
    folder_name = repre_data["context"]["folder"]["name"]
    product_name = repre_data["context"]["product"]["name"]
    new_layer_name = f"{folder_name}_{product_name}"

    # switching assets
    existing_footages = stub.get_items(
        comps=False, folders=False, footages=True)
    existing_footage_names = [footage_item.name for footage_item in existing_footages]

    namespace_from_container = re.sub(r'_\d{3}$', '',
                                      orig_container["namespace"])

    if namespace_from_container != new_layer_name:
        layers = stub.get_items(comps=True)
        existing_layers = [layer.name for layer in layers]
        layer_name = get_unique_layer_name(
            existing_layers,
            "{}_{}".format(folder_name, product_name))
    else:  # switching version - keep same name
        layer_name = orig_container["namespace"]
    path = get_representation_path(repre_data)

    if len(repre_data["files"]) > 1:
        path = os.path.dirname(path)

    layer_id = orig_container["members"][0]
    stub.replace_item(layer_id, path, stub.LOADED_ICON + layer_name)
    stub.imprint(
        layer_id, {"representation": repre_data["id"],
                   "name": product_name,
                   "namespace": layer_name}
    )