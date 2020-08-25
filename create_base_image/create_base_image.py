from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
import os
import time
import argparse

# Parse flag arguments

parser = argparse.ArgumentParser()

def add_flag(flag_name, default):
    parser.add_argument(f'--{flag_name}', dest=flag_name,
                        action='store', default=default)

# Base image info
add_flag('source_image_family', 'debian-10')
add_flag('source_image_project', 'debian-cloud')

# Cuttlefish repo info
add_flag('repository_url', 'https://github.com/google/android-cuttlefish.git')
add_flag('repository_branch', 'main')

# Build artifacts info
add_flag('build_branch', 'aosp-master')
add_flag('build_target' ,'aosp_cf_x86_phone-userdebug')
add_flag('build_id', '')

# Build instance info
add_flag('build_instance', 'halyard-build')
add_flag('build_zone', 'europe-west4-a')
parser.add_argument('--tag', action='append', dest='tags', default=[])

# New image info
add_flag('dest_image', '')
add_flag('dest_family', '')
add_flag('image_disk', 'halyard-image-disk')
parser.add_argument('--respin', action='store_true', default=False)

# GCE Project info
add_flag('datacenter', 'us-central1-b')
add_flag('project', 'cloud-android-testing')

args = parser.parse_args()


# Get GCE Driver
ComputeEngine = get_driver(Provider.GCE)
driver = ComputeEngine('', '',
                       datacenter=args.datacenter, project=args.project)


def fatal_error(msg):
    print(f'Error: {msg}')
    exit()

def wait_for_instance():
    not_running = 1
    while not_running != 0:
        time.sleep(5)
        # uptime returns a value other than 0 when not successful
        not_running = os.system(f'gcloud compute ssh {args.build_instance} --zone={args.build_zone} -- uptime')

def update_dest_names():
    os.system(f'gcloud compute scp {args.build_instance}:~/image_name_values \
        name_values --zone={args.build_zone}')

    variables = {}

    with open('name_values') as f:
        for line in f:
            name, value = line.split('=')
            variables[name] = value.strip()

    cf_version = variables['cf_version']
    args.build_id = variables['build_id']

    os.remove('name_values')

    args.build_target = args.build_target.replace('_','-')

    if not args.dest_image:
        args.dest_image = f'halyard-{cf_version}-{args.build_branch}-{args.build_target}-{args.build_id}'

    if not args.dest_family:
        args.dest_family = f'halyard-{args.build_branch}-{args.build_target}'


# DELETE OBJECTS WITH NAMES WE NEED

try:
    build_node = driver.ex_get_node(args.build_instance, args.build_zone)
    driver.destroy_node(build_node)
    print('successfully deleted', args.build_instance)
except:
    pass

try:
    build_volume = driver.ex_get_volume(args.image_disk, args.build_zone)
    driver.destroy_volume(build_volume)
    print('successfully deleted', args.image_disk)
except:
    pass


# BUILD INSTANCE CREATION

build_volume = driver.create_volume(
    30, args.image_disk,
    location=args.build_zone,
    ex_image_family=args.source_image_family)

print('built', args.source_image_family, 'disk')

gpu_type='nvidia-tesla-p100-vws'
try:
    driver.ex_get_accelerator_type(
        gpu_type,
        zone=args.build_zone)
except:
    fatal_error(f'Please use a zone with {gpu_type} GPUs available')

build_node = driver.create_node(
    args.build_instance,
    'n1-standard-16',
    None,
    location=args.build_zone,
    ex_image_family=args.source_image_family,
    ex_accelerator_type=gpu_type,
    ex_on_host_maintenance='TERMINATE',
    ex_accelerator_count=1,
    ex_service_accounts=[{'scopes':['storage-ro']}],
    ex_disk_size=30,
    ex_tags=args.tags)
print('successfully created', args.build_instance)

wait_for_instance()

driver.attach_volume(
    build_node,
    build_volume)

os.system(f'gcloud compute scp create_base_image_gce.sh {args.build_instance}: \
    --zone={args.build_zone}')


# IMAGE CREATION

os.system(f'gcloud compute ssh --zone={args.build_zone} \
    {args.build_instance} -- ./create_base_image_gce.sh \
    {args.repository_url} {args.repository_branch} \
    {args.build_branch} {args.build_target} {args.build_id}')

update_dest_names()

try:
    build_image = driver.ex_get_image(args.dest_image)
except:
    build_image = None

if (build_image):
    if (args.respin):
        driver.ex_delete_image(build_image)
    else:
        fatal_error(f'''Image {args.dest_image} already exists.
        (To replace run with flag --respin)''')

driver.destroy_node(build_node)

driver.ex_create_image(
    args.dest_image,
    build_volume,
    ex_licenses=['https://www.googleapis.com/compute/v1/projects/vm-options/global/licenses/enable-vmx'],
    family=args.dest_family
)

print(f'Created image {args.dest_image} in {args.dest_family} family')

driver.destroy_volume(build_volume)