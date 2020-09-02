import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import halyard_utils as utils
from halyard_utils import add_flag, set_args

PATH = 'image'

# Parse flag arguments
parser = argparse.ArgumentParser()

# Base image info
add_flag(parser, 'source_image_family', 'debian-10')
add_flag(parser, 'source_image_project', 'debian-cloud')

# Cuttlefish repo info
add_flag(parser, 'repository_url', 'https://github.com/google/android-cuttlefish.git')
add_flag(parser, 'repository_branch', 'main')

# Build artifacts info
add_flag(parser, 'build_branch', 'aosp-master')
add_flag(parser, 'build_target' ,'aosp_cf_x86_phone-userdebug')
add_flag(parser, 'build_id', '')

# Build instance info
add_flag(parser, 'build_instance', 'halyard-build')
add_flag(parser, 'build_zone', 'europe-west4-a')
parser.add_argument('--tag', action='append', dest='tags', default=[])

# New image info
add_flag(parser, 'dest_image', '')
add_flag(parser, 'dest_family', '')
add_flag(parser, 'image_disk', 'halyard-image-disk')
parser.add_argument('--respin', action='store_true', default=False)


def update_dest_names():
    """Updates cf_version and build_id values extracted from gce script to name the new image"""

    os.system(f'gcloud compute scp {args.build_instance}:~/image_name_values \
        {PATH}/image_name_values --zone={args.build_zone}')

    variables = {}

    with open(f'{PATH}/image_name_values') as f:
        for line in f:
            name, value = line.split('=')
            variables[name] = value.strip()

    cf_version = variables['cf_version']
    args.build_id = variables['build_id']

    os.remove(f'{PATH}/image_name_values')

    args.build_target = args.build_target.replace('_','-')

    if not args.dest_image:
        args.dest_image = f'halyard-{cf_version}-{args.build_branch}-{args.build_target}-{args.build_id}'

    if not args.dest_family:
        args.dest_family = f'halyard-{args.build_branch}-{args.build_target}'


def create_base_image(driver, body):
    """Creates new base image that holds Cuttlefish packages and Android build artifacts"""

    # SETUP

    args = set_args(parser, body)
    
    build_node = utils.find_instance(driver, args.build_instance, args.build_zone)
    if build_node:
        driver.destroy_node(build_node)
        print('successfully deleted', args.build_instance)

    build_volume = utils.find_disk(driver, args.image_disk, args.build_zone)
    if build_volume:
        driver.destroy_volume(build_volume)
        print('successfully deleted', args.image_disk)


    # BUILD INSTANCE CREATION

    build_volume = driver.create_volume(
        30, args.image_disk,
        location=args.build_zone,
        ex_image_family=args.source_image_family)

    print('built', args.source_image_family, 'disk')

    gpu_type='nvidia-tesla-p100-vws'
    gpu = utils.find_gpu(driver, gpu_type, args.build_zone)
    if not gpu:
        utils.fatal_error(f'Please use a zone with {gpu_type} GPUs available')

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

    utils.wait_for_instance(args.build_instance, args.build_zone)

    driver.attach_volume(build_node, build_volume)

    src_files = ['create_base_image_gce.sh', 'download_artifacts.sh']
    src_files = [PATH + '/' + file for file in src_files]
    src = ' '.join(list(map(str,src_files)))

    os.system(f'gcloud compute scp {src} {args.build_instance}: \
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

    if build_image:
        if args.respin:
            driver.ex_delete_image(build_image)
        else:
            utils.fatal_error(f'''Image {args.dest_image} already exists.
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

    return {"name": args.dest_image, "family": args.dest_family}