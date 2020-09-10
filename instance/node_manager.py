
def list_nodes(driver):
    nodes = driver.list_nodes()
    node_list = {}
    for i, node in enumerate(nodes):
        node_list.update({i: {"name": node.name,
                              "public_ips": node.public_ips} })
    return node_list

def get_node(driver, instance_name):
    try:
        node = driver.ex_get_node(instance_name)
        return {"name": node.name,
                "public_ips": node.public_ips}
    except:
        return {}