import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import halyard_utils as utils

def list_images(driver):
    images = driver.list_images()
    image_list = []
    for image in images:
        image_list.append({"name": image.name})
    halyard_images = list(filter(lambda x: x['name'].startswith('halyard'), image_list))
    return halyard_images

def get_image(driver, image_name):
    image = utils.find_image(driver, image_name)
    if image:
        return {"name": image.name,
                "creationTimestamp": image.extra['creationTimestamp'],
                "family": image.extra['family'],
                "diskSizeGb": image.extra['diskSizeGb']}
    else:
        return {}

def delete_image(driver, image_name):
    image = utils.find_image(driver, image_name)
    if image:
        driver.ex_delete_image(image)
        return {"deleted_image": image_name}
    else:
        return {"Error": f"image {image_name} not found."}


PATH = 'image'

def get_dest_names(build_branch, build_target, build_id, build_instance, build_zone,
                      dest_image, dest_family):
    """Updates cf_version and build_id values extracted from gce script to name the new image"""

    os.system(f'gcloud compute scp {build_instance}:~/image_name_values \
        {PATH}/image_name_values --zone={build_zone}')

    variables = {}

    with open(f'{PATH}/image_name_values') as f:
        for line in f:
            name, value = line.split('=')
            variables[name] = value.strip()

    cf_version = variables['cf_version']
    build_id = variables['build_id']

    os.remove(f'{PATH}/image_name_values')

    build_target = build_target.replace('_','-')

    if not dest_image:
        dest_image = f'halyard-{cf_version}-{build_branch}-{build_target}-{build_id}'

    if not dest_family:
        dest_family = f'halyard-{build_branch}-{build_target}'

    return {'dest_image': dest_image, 'dest_family': dest_family}


def create_base_image(driver,
        source_image_family='debian-10', source_image_project='debian-cloud',
        repository_url='https://github.com/google/android-cuttlefish.git',
        repository_branch='main', build_branch='aosp-master',
        build_target='aosp_cf_x86_phone-userdebug', build_id='',
        build_instance='halyard-build', build_zone='europe-west4-a', tags=[],
        dest_image='', dest_family='', image_disk='halyard-image-disk', respin=False):
    """Creates new base image that holds Cuttlefish packages and Android build artifacts"""

    # SETUP
    
    build_node = utils.find_instance(driver, build_instance, build_zone)
    if build_node:
        driver.destroy_node(build_node)
        print('successfully deleted', build_instance)

    build_volume = utils.find_disk(driver, image_disk, build_zone)
    if build_volume:
        driver.destroy_volume(build_volume)
        print('successfully deleted', image_disk)


    # BUILD INSTANCE CREATION

    build_volume = driver.create_volume(
        30, image_disk,
        location=build_zone,
        ex_image_family=source_image_family)

    print('built', source_image_family, 'disk')

    gpu_type='nvidia-tesla-p100-vws'
    gpu = utils.find_gpu(driver, gpu_type, build_zone)
    if not gpu:
        utils.fatal_error(f'Please use a zone with {gpu_type} GPUs available')

    build_node = driver.create_node(
        build_instance,
        'n1-standard-16',
        None,
        location=build_zone,
        ex_image_family=source_image_family,
        ex_accelerator_type=gpu_type,
        ex_on_host_maintenance='TERMINATE',
        ex_accelerator_count=1,
        ex_service_accounts=[{'scopes':['storage-ro']}],
        ex_disk_size=30,
        ex_tags=tags)
    print('successfully created', build_instance)

    utils.wait_for_instance(build_instance, build_zone)

    driver.attach_volume(build_node, build_volume)

    src_files = ['create_base_image_gce.sh', 'download_artifacts.sh']
    src_files = [PATH + '/' + file for file in src_files]
    src = ' '.join(list(map(str,src_files)))

    os.system(f'gcloud compute scp {src} {build_instance}: \
        --zone={build_zone}')


    # IMAGE CREATION

    os.system(f'gcloud compute ssh --zone={build_zone} \
        {build_instance} -- ./create_base_image_gce.sh \
        {repository_url} {repository_branch} \
        {build_branch} {build_target} {build_id}')

    dest_names = get_dest_names(
        build_branch, build_target, build_id,
        build_instance, build_zone, dest_image, dest_family)
    
    dest_image = dest_names['dest_image']
    dest_family = dest_names['dest_family']

    try:
        build_image = driver.ex_get_image(dest_image)
    except:
        build_image = None

    if build_image:
        if respin:
            driver.ex_delete_image(build_image)
        else:
            utils.fatal_error(f'''Image {dest_image} already exists.
            (To replace run with flag --respin)''')

    driver.destroy_node(build_node)

    driver.ex_create_image(
        dest_image,
        build_volume,
        ex_licenses=['https://www.googleapis.com/compute/v1/projects/vm-options/global/licenses/enable-vmx'],
        family=dest_family
    )

    print(f'Created image {dest_image} in {dest_family} family')

    driver.destroy_volume(build_volume)

    return {"name": dest_image, "family": dest_family}
