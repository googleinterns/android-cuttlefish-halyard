from flask import Flask, request, jsonify
from flask_restful import Api, Resource, abort
import argparse
from halyard_utils import add_flag
from image.create_base_image import create_base_image
from instance.create_or_restore_instance import create_or_restore_instance, create_instance
from instance.node_manager import list_nodes, get_node, delete_node
from image.image_manager import list_images, get_image, delete_image
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

# Extra endpoints

@app.route('/list')
def list_gce_machines():
    nodes = list_nodes(driver)
    return nodes

if __name__ == '__main__':
    app.run(debug=True)