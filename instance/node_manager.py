import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import halyard_utils as utils

def list_nodes(driver):
    nodes = driver.list_nodes()
    node_list = []
    for node in nodes:
        node_list.append({"name": node.name,
                          "creationTimestamp": node.extra['creationTimestamp'],
                          "image": node.extra['image'],
                          "public_ips": node.public_ips})
    halyard_nodes = list(filter(lambda x: x['name'].startswith('halyard'), node_list))
    return halyard_nodes

def get_node(driver, instance_name, zone):
    node = utils.find_instance(driver, instance_name, zone)
    if node:
        return {"name": node.name,
                "creationTimestamp": node.extra['creationTimestamp'],
                "image": node.extra['image'],
                "public_ips": node.public_ips}
    else:
        return {}

def delete_node(driver, instance_name, zone):
    node = utils.find_instance(driver, instance_name, zone)
    if node:
        driver.destroy_node(node)
        return {"stopped_instance": instance_name}
    else:
        return {"error": "node not found"}
