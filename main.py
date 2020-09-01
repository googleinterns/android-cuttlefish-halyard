from flask import Flask, request, jsonify
from flask_restful import Api, Resource, abort
import argparse
from halyard_utils import add_flag
from instance.list_nodes import list_nodes, get_node
from image.create_base_image import create_base_image
from instance.create_or_restore_instance import create_or_restore_instance, create_instance

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

    def get(self, user_id):
        instance_name = f'halyard-{user_id}'
        node = get_node(driver, instance_name)
        abort_if_none(node, instance_name)
        return {"instance": node}

    def put(self, user_id):
        new_instance = create_or_restore_instance(driver)
        return {"new_instance": new_instance}

    def delete(self, user_id):
        instance_name = f'halyard-{user_id}'
        return {"deleted_instance": instance_name}
        # FIXME : endpoint not ready

class BaseImage(Resource):
    """Halyard base image manager"""

    def get(self, image_name):
        return {"image": image_name}
        # FIXME : endpoint not ready

    def put(self, image_name):
        new_image = create_base_image(driver)
        return {"new_image": new_image}
    
    def delete(self, image_name):
        return {"deleted_image": image_name}
        # FIXME : endpoint not ready

api.add_resource(Instance, "/instance/<string:user_id>")
api.add_resource(BaseImage, "/image/<string:image_name>")

# Extra endpoints

@app.route('/list')
def list_gce_machines():
    nodes = list_nodes(driver)
    return nodes

if __name__ == '__main__':
    app.run(debug=True)