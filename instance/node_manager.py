import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import halyard_utils as utils

def list_nodes(driver):
    nodes = driver.list_nodes()
    node_list = []
    for node in nodes:
        node_list.append({"name": node.name,
                          "creationTimestamp": node.extra['creationTimestamp'],
                          "image": node.extra['image'],
                          "public_ips": node.public_ips})
    halyard_nodes = list(filter(lambda x: x['name'].startswith('halyard'), node_list))
    return halyard_nodes

def get_node(driver, instance_name, zone):
    node = utils.find_instance(driver, instance_name, zone)
    if node:
        return {"name": node.name,
                "creationTimestamp": node.extra['creationTimestamp'],
                "image": node.extra['image'],
                "public_ips": node.public_ips}
    else:
        return {}

def delete_node(driver, instance_name, zone):
    node = utils.find_instance(driver, instance_name, zone)
    if node:
        driver.destroy_node(node)
        return {"stopped_instance": instance_name}
    else:
        return {"error": f"instance {instance_name} not found"}


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


def create_or_restore_instance(driver,
        user_id, sig_server_addr, sig_server_port, zone='us-central1-b',
        tags=[], branch='aosp-master', target='aosp_cf_x86_phone-userdebug'):
    """Restores instance with existing user disk and original base image.
       Creates a new instance with latest image if user disk doesn't exist.
       Stores runtime data in external GCP disk.
       Launches Cuttlefish if creation is successful."""

    # SETUP
    target = target.replace('_','-')
    instance_name = f'halyard-{user_id}'
    disk_name = f'halyard-user-{user_id}'
    image_family = f'halyard-{branch}-{target}'

    # Stops execution if instance already exists
    instance = utils.find_instance(driver, instance_name, zone)
    if instance:
        utils.fatal_error(f'Instance {instance_name} already exists.')

    # Looks for existing user disk
    user_disk = utils.find_disk(driver, disk_name, zone)
    if user_disk:
        base_image = get_base_image_from_labels(user_disk)
    else:
        user_disk = driver.create_volume(
            30, disk_name, location=zone, image='halyard-blank')
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
            location=zone,
            ex_service_accounts=[{'scopes': ['storage-ro']}],
            ex_disk_size=30,
            ex_tags=tags)

    # If new user, use image family
    else:
        try:
            img = driver.ex_get_image_from_family(image_family)
        except:
            utils.fatal_error(f'Image in family {image_family} does not exist.')

        set_base_image_labels(driver, user_disk, img.name, branch, target)

        new_instance = driver.create_node(
            instance_name,
            'n1-standard-4',
            None,
            location=zone,
            ex_image_family=image_family,
            ex_service_accounts=[{'scopes': ['storage-ro']}],
            ex_disk_size=30,
            ex_tags=tags)


    # ATTACH USER DISK AND LAUNCH

    utils.wait_for_instance(instance_name, zone)
    print('successfully created new instance', instance_name)

    driver.attach_volume(new_instance, user_disk)
    print(f'attached {disk_name} to {instance_name}')

    os.system(f'gcloud compute ssh --zone={zone} {instance_name} -- \
        sudo mkdir /mnt/user_data')
    os.system(f'gcloud compute ssh --zone={zone} {instance_name} -- \
        sudo mount /dev/sdb /mnt/user_data')
    os.system(f'gcloud compute ssh --zone={zone} {instance_name} -- \
        sudo chmod -R 777 /mnt/user_data')
    # FIXME : should assign specific user permissions

    launch_cvd(instance_name, zone, sig_server_addr, sig_server_port)

    return {"name": instance_name}

def create_instance(driver,
        user_id, sig_server_addr, sig_server_port, zone='us-central1-b',
        tags=[], branch='aosp-master', target='aosp_cf_x86_phone-userdebug'):
    """Creates a new Cuttlefish instance and launches it.
       Does not store runtime data in external GCP disk."""

    target = target.replace('_','-')
    instance_name = f'halyard-{user_id}'
    image_family = f'halyard-{branch}-{target}'

    try:
        driver.ex_get_image_from_family(image_family)
    except:
        utils.fatal_error(f'Image family {image_family} does not exist.\n \
            New base images can be created using the `create_base_image` endpoint.')

    # Stops execution if instance already exists
    instance = utils.find_instance(driver, instance_name, zone)
    if instance:
        utils.fatal_error(f'Instance {instance_name} already exists.')

    build_node = driver.create_node(
        instance_name,
        'n1-standard-4',
        None,
        location=zone,
        ex_image_family=image_family,
        ex_service_accounts=[{'scopes': ['storage-ro']}],
        ex_disk_size=30,
        ex_tags=tags)

    utils.wait_for_instance(instance_name, zone)

    print('successfully created new instance', instance_name)

    launch_cvd(instance_name, zone, sig_server_addr, sig_server_port, False)

    return {"name": instance_name}

def launch_cvd(instance_name, zone, sig_server_addr, sig_server_port, use_user_disk=True):
    """Launch cvd on given instance and connect to operator on given address.
       If use_user_disk is True it uses existing user data disk."""

    cuttlefish_dir = '/usr/local/share/cuttlefish'
    user_data_dir = '/mnt/user_data'

    launch_command = f'gcloud compute ssh --zone={zone} {instance_name} -- '

    if use_user_disk:
        launch_command += f'HOME={user_data_dir} \
            ANDROID_HOST_OUT={cuttlefish_dir} \
            ANDROID_PRODUCT_OUT={cuttlefish_dir} '
    else:
        launch_command += f'HOME={cuttlefish_dir} '

    launch_command += f'{cuttlefish_dir}/bin/launch_cvd \
        --start_webrtc --daemon \
        --webrtc_sig_server_addr={sig_server_addr} \
        --webrtc_sig_server_port={sig_server_port} \
        --start_webrtc_sig_server=false \
        --webrtc_device_id={instance_name} \
        --report_anonymous_usage_stats=y'

    os.system(launch_command)

    print(f'Launched cuttlefish on {instance_name} at {sig_server_addr}:{sig_server_port}')
