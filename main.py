from flask import Flask, request, render_template, jsonify
from flask_restful import Api, Resource, abort
import requests
import argparse
from halyard_utils import add_flag
from instance.node_manager import list_nodes, get_node, delete_node, create_or_restore_instance
from image.image_manager import list_images, get_image, delete_image, create_base_image
from disk.disk_manager import list_disks, delete_disk, list_stopped_disks

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

# Parse flag arguments
parser = argparse.ArgumentParser()
add_flag(parser, 'datacenter', 'us-central1-b')
add_flag(parser, 'project', 'cloud-android-testing')
args = parser.parse_args()

# Get GCE Driver
ComputeEngine = get_driver(Provider.GCE)
driver = ComputeEngine('', '',
                       datacenter=args.datacenter,
                       project=args.project)

app = Flask(__name__)
api = Api(app)

def abort_if_none(obj, name):
    if not obj:
        abort(404, message=f"Error: {name} not found.")


class Instance(Resource):
    """Cuttlefish instance manager"""

    def get(self, instance_name):
        node = get_node(driver, instance_name, args.datacenter)
        abort_if_none(node, instance_name)
        return {"instance": node}

    def delete(self, instance_name):
        return delete_node(driver, instance_name, args.datacenter)

class InstanceList(Resource):
    """Shows a list of all instances and creates new ones"""

    def get(self):
        nodes = list_nodes(driver)
        return {"instances": nodes}

    def post(self):
        body = request.json
        new_instance = create_or_restore_instance(driver, **body)
        return {"new_instance": new_instance}

class BaseImage(Resource):
    """Halyard base image manager"""

    def get(self, image_name):
        image = get_image(driver, image_name)
        abort_if_none(image, image_name)
        return {"image": image}
    
    def delete(self, image_name):
        return delete_image(driver, image_name)

class BaseImageList(Resource):
    """Shows a list of all base images and creates new ones"""

    def get(self):
        images = list_images(driver)
        return {"images": images}

    def post(self):
        body = request.json
        new_image = create_base_image(driver, **body)
        return {"new_image": new_image}

class Disk(Resource):
    """Halyard disk manager"""

    def delete(self, disk_name):
        return delete_disk(driver, disk_name, args.datacenter)

class DiskList(Resource):
    """Shows a list of disks which can be used to restore instances"""

    def get(self):
        stopped_instances = list_stopped_disks(driver)
        return {"disks": stopped_instances}

api.add_resource(InstanceList, "/instance-list")
api.add_resource(BaseImageList, "/image-list")
api.add_resource(DiskList, "/disk-list")
api.add_resource(Instance, "/instance/<string:instance_name>")
api.add_resource(BaseImage, "/image/<string:image_name>")
api.add_resource(Disk, "/disk/<string:disk_name>")

# Demo UI Endpoints

BASE = "http://127.0.0.1:5000/"
SIG_SERVER_HOST = "localhost:8443"

@app.route('/')
def index():
    instances = requests.get(BASE + "instance-list").json()['instances']
    disks = requests.get(BASE + "disk-list").json()['disks']
    return render_template('instances.html', instances=instances, disks=disks)

@app.route('/instances')
def instances_page():
    instances = requests.get(BASE + "instance-list").json()['instances']
    disks = requests.get(BASE + "disk-list").json()['disks']
    return render_template('instances.html',
        instances=instances, disks=disks)

@app.route('/images')
def images_page():
    images = requests.get(BASE + "image-list").json()['images']
    return render_template('images.html', images=images)

@app.route('/connect')
def enter_instance():
    args = request.args
    if not 'device_id' in args:
        return 'missing device_id in query params'
    data = {}
    data['device_id'] = args['device_id']
    data['sig_server_host'] = SIG_SERVER_HOST

    return render_template('cvd_interface.html', data=data)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)