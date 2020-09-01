import requests
import pprint
pp = pprint.PrettyPrinter(indent=4)

BASE = "http://127.0.0.1:5000/"

def resource_get(endpoint):
    res = requests.get(endpoint)
    print('GET', endpoint)
    pp.pprint(res.json())

def resource_put(endpoint):
    res = requests.put(endpoint)
    print('PUT', endpoint)
    pp.pprint(res.json())

def resource_delete(endpoint):
    res = requests.delete(endpoint)
    print('DELETE', endpoint)
    pp.pprint(res.json())

def test_resource_endpoints(resource_name, resource_id):
    endpoint = BASE + f'{resource_name}/{resource_id}'
    print(f'{resource_name} responses')
    print('--------------------------')
    resource_get(endpoint)
    resource_put(endpoint)
    resource_delete(endpoint)
    print('')


user_id = '00001'
image_name = 'halyard-0-9-14-aosp-master-aosp-cf-x86-phone-userdebug-6796612'

resource_get(BASE + 'list')
test_resource_endpoints('instance', user_id)
test_resource_endpoints('image', image_name)