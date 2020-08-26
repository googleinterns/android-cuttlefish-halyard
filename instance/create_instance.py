import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import halyard_utils as utils
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

# Parse flag arguments

parser = argparse.ArgumentParser()

def add_flag(flag_name, default):
    parser.add_argument(f'--{flag_name}', dest=flag_name,
                        action='store', default=default)

# New instance info
add_flag('branch', 'aosp-master')
add_flag('target' ,'aosp_cf_x86_phone-userdebug')
add_flag('user_id', '00001')
add_flag('zone', 'us-central1-b')
parser.add_argument('--tag', action='append', dest='tags', default=[])

# GCE Project info
add_flag('datacenter', 'us-central1-b')
add_flag('project', 'cloud-android-testing')

# Signaling server info
add_flag('sig_server_addr', '127.0.0.1')
add_flag('sig_server_port', '8443')

args = parser.parse_args()


# Get GCE Driver
ComputeEngine = get_driver(Provider.GCE)
driver = ComputeEngine('', '',
                       datacenter=args.datacenter, project=args.project)


# SETUP

# Set global vars
args.target = args.target.replace('_','-')
instance_name = f'halyard-{args.user_id}'
image_family = f'halyard-{args.branch}-{args.target}'

try:
    driver.ex_get_image_from_family(image_family)
except:
    utils.fatal_error(f'Image family {image_family} does not exist.\n \
        New base images can be created using the `create_base_image` endpoint.')

# Stops execution if instance already exists
instance = utils.find_instance(driver, instance_name, args.zone)
if instance:
    utils.fatal_error(f'Instance {instance_name} already exists.')

build_node = driver.create_node(
    instance_name,
    'n1-standard-4',
    None,
    location=args.zone,
    ex_image_family=image_family,
    ex_service_accounts=[{'scopes': ['storage-ro']}],
    ex_disk_size=30,
    ex_tags=args.tags)

utils.wait_for_instance(instance_name, args.zone)

print('successfully created new instance', instance_name)

os.system(f'gcloud compute ssh --zone={args.zone} {instance_name} -- \
    HOME=/usr/local/share/cuttlefish /usr/local/share/cuttlefish/bin/launch_cvd \
    --start_webrtc --daemon \
    --webrtc_sig_server_addr={args.sig_server_addr} \
    --webrtc_sig_server_port={args.sig_server_port} \
    --start_webrtc_sig_server=false \
    --webrtc_device_id={instance_name}')

print('launched cuttlefish on', instance_name)