from ayon_core.pipeline import context_tools, anatomy
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