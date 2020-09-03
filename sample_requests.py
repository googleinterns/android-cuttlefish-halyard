import requests
import pprint
pp = pprint.PrettyPrinter(indent=4)

BASE = "http://127.0.0.1:5000/"

class Resource():
    def __init__(self, resource_name):
        self.base = BASE + resource_name + '/'

    def get(self, id):
        endpoint = self.base + id
        res = requests.get(endpoint)
        print('GET', endpoint)
        pp.pprint(res.json())

    def put(self, id, body={}):
        endpoint = self.base + id
        res = requests.put(endpoint, json=body)
        print('PUT', endpoint)
        pp.pprint(res.json())

    def delete(self, id):
        endpoint = self.base + id
        res = requests.delete(endpoint)
        print('DELETE', endpoint)
        pp.pprint(res.json())

def test_resource_endpoints(resource, id, body=None):
    resource.get(id)
    resource.put(id, body)
    resource.delete(id)


user_id = '00001'
image_name = 'halyard-0-9-14-aosp-master-aosp-cf-x86-phone-userdebug-6796612'

image = Resource('image')
instance = Resource('instance')

image_body = {"build_instance": "my-build", "tags": ['kradtke-ssh'], "respin": True}
instance_body = {"sig_server_port": 8444, "tags": ['kradtke-ssh']}

test_resource_endpoints(image, image_name, image_body)
test_resource_endpoints(instance, user_id, instance_body)