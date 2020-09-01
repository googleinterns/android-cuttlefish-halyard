import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import halyard_utils as utils
from halyard_utils import add_flag

# Parse flag arguments
parser = argparse.ArgumentParser()

# New instance info
add_flag(parser, 'user_id', '00001')
add_flag(parser, 'zone', 'us-central1-b')
parser.add_argument('--tag', action='append', dest='tags', default=[])

# Base image version
add_flag(parser, 'branch', 'aosp-master')
add_flag(parser, 'target' ,'aosp_cf_x86_phone-userdebug')

# Signaling server info
add_flag(parser, 'sig_server_addr', '127.0.0.1')
add_flag(parser, 'sig_server_port', '8443')

args = parser.parse_args()


def get_base_image_from_labels(user_disk):
    """Gets original base image from GCP disk labels"""

    labels = ['cf_version', 'branch', 'target', 'build_id']
    disk_labels = user_disk.extra['labels']

    if all(label in disk_labels for label in labels):
        cf_version = disk_labels['cf_version']
        branch = disk_labels['branch']
        target = disk_labels['target']
        build_id = disk_labels['build_id']

        base_image = f'halyard-{cf_version}-{branch}-{target}-{build_id}'
        return base_image
    else:
        utils.fatal_error(f'Labels for {user_disk.name} are not complete.\n \
            Must have all labels in: {labels}')

def set_base_image_labels(driver, user_disk, img_name, branch, target):
    """Sets disk labels with base image version data"""

    dashes = [i for i, c in enumerate(img_name) if c=='-']
    cf_version = img_name[dashes[0]+1:dashes[3]]
    build_id = img_name[dashes[-1]+1:]

    driver.ex_set_volume_labels(user_disk,
        {'cf_version': cf_version, 'branch': branch,
         'target': target, 'build_id': build_id})


def create_or_restore_instance(driver):
    """Restores instance with existing user disk and original base image.
       Creates a new instance with latest image if user disk doesn't exist.
       Stores userdata.img in external GCP disk.
       Launches Cuttlefish if creation is successful."""

    # SETUP

    args.target = args.target.replace('_','-')
    instance_name = f'halyard-{args.user_id}'
    disk_name = f'halyard-user-{args.user_id}'
    image_family = f'halyard-{args.branch}-{args.target}'

    # Stops execution if instance already exists
    instance = utils.find_instance(driver, instance_name, args.zone)
    if instance:
        utils.fatal_error(f'Instance {instance_name} already exists.')

    # Looks for existing user disk
    user_disk = utils.find_disk(driver, disk_name, args.zone)
    if user_disk:
        base_image = get_base_image_from_labels(user_disk)
    else:
        user_disk = driver.create_volume(
            30, disk_name, location=args.zone, image='halyard-blank')
        base_image = None


    # CREATE INSTANCE

    # If existing user, use original base image
    if base_image:
        try:
            driver.ex_get_image(base_image)
        except:
            utils.fatal_error(f'Image {base_image} does not exist.')

        new_instance = driver.create_node(
            instance_name,
            'n1-standard-4',
            base_image,
            location=args.zone,
            ex_service_accounts=[{'scopes': ['storage-ro']}],
            ex_disk_size=30,
            ex_tags=args.tags)

    # If new user, use image family
    else:
        try:
            img = driver.ex_get_image_from_family(image_family)
        except:
            utils.fatal_error(f'Image in family {args.image_family} does not exist.')

        set_base_image_labels(driver, user_disk, img.name, args.branch, args.target)

        new_instance = driver.create_node(
            instance_name,
            'n1-standard-4',
            None,
            location=args.zone,
            ex_image_family=image_family,
            ex_service_accounts=[{'scopes': ['storage-ro']}],
            ex_disk_size=30,
            ex_tags=args.tags)


    # ATTACH USER DISK AND LAUNCH

    utils.wait_for_instance(instance_name, args.zone)
    print('successfully created new instance', instance_name)

    driver.attach_volume(
        new_instance,
        user_disk)

    os.system(f'gcloud compute ssh --zone={args.zone} {instance_name} -- \
        sudo mkdir /mnt/user_data')
    os.system(f'gcloud compute ssh --zone={args.zone} {instance_name} -- \
        sudo mount /dev/sdb /mnt/user_data')
    os.system(f'gcloud compute ssh --zone={args.zone} {instance_name} -- \
        sudo chmod 777 /mnt/user_data/userdata.img')
    # FIXME : should assign specific user permissions

    os.system(f'gcloud compute ssh --zone={args.zone} {instance_name} -- \
        HOME=/usr/local/share/cuttlefish /usr/local/share/cuttlefish/bin/launch_cvd \
        --start_webrtc --daemon \
        --webrtc_sig_server_addr={args.sig_server_addr} \
        --webrtc_sig_server_port={args.sig_server_port} \
        --start_webrtc_sig_server=false \
        --webrtc_device_id={instance_name} \
        --data_image=/mnt/user_data/userdata.img \
        --data_policy=create_if_missing --blank_data_image_mb=30000')

    print('launched cuttlefish on', instance_name)

    return {"name": instance_name}


def create_instance(driver):
    """Creates a new Cuttlefish instance and launches it.
       Does not store userdata.img in external GCP disk."""

    # SETUP

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

    return {"name": instance_name}