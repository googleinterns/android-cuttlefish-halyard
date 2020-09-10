import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import halyard_utils as utils
from instance.node_manager import list_nodes

def list_disks(driver):
    disks = driver.list_volumes()
    disk_list = []
    for disk in disks:
        disk_list.append({"name": disk.name})
    halyard_disks = list(filter(lambda x: x['name'].startswith('halyard-user'), disk_list))
    return halyard_disks

def list_stopped_disks(driver):
    disks = driver.list_volumes()
    disk_list = []
    for disk in disks:
        disk_list.append({"name": disk.name})

    active_nodes = list_nodes(driver)
    halyard_nodes = list(filter(lambda x: x['name'].startswith('halyard'), active_nodes))
    node_ids = [x['name'][8:] for x in halyard_nodes]
    
    halyard_disks = list(filter(lambda x: x['name'].startswith('halyard-user'), disk_list))
    stopped_instances = [{"name": x['name']} for x in halyard_disks if x['name'][13:] not in node_ids]

    return stopped_instances

def delete_disk(driver, disk_name, zone):
    disk = utils.find_disk(driver, disk_name, zone)
    if disk:
        driver.destroy_volume(disk)
        return {"deleted_disk": disk_name}
    else:
        return {"error": "disk not found"}
