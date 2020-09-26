import requests
import pprint
pp = pprint.PrettyPrinter(indent=4)

BASE = "http://127.0.0.1:5000/"

class Resource():
    def __init__(self, resource_name):
        self.base = BASE + resource_name

    def get(self, id):
        endpoint = self.base
        if id:
            endpoint += f'/{id}'
        res = requests.get(endpoint)
        print('GET', endpoint)
        pp.pprint(res.json())

    def post(self, body={}):
        endpoint = self.base
        res = requests.post(endpoint, json=body)
        print('POST', endpoint)
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

images = Resource('image-list')
instances = Resource('instance-list')

image_body = {"build_instance": "my-build", "tags": ['kradtke-ssh'], "respin": True}
instance_body = {"sig_server_port": 8444, "tags": ['kradtke-ssh']}

# Test Image List Endpoints
images.get('')
images.post(image_body)

# Test Instance List Endpoints
instances.get('')
instances.post(instance_body)