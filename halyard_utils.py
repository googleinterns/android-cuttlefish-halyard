import os
import time

def add_flag(parser, flag_name, default):
    parser.add_argument(f'--{flag_name}', dest=flag_name,
                        action='store', default=default)

def wait_for_instance(instance_name, zone):
    not_running = 1
    while not_running != 0:
        time.sleep(5)
        # uptime returns a value other than 0 when not successful
        not_running = os.system(f'gcloud compute ssh {instance_name} --zone={zone} -- uptime')

def fatal_error(msg):
    print(f'Error: {msg}')
    exit()

def find_instance(driver, instance_name, zone):
    try:
        instance = driver.ex_get_node(instance_name, zone)
    except:
        instance = None
    return instance

def find_image(driver, image_name):
    try:
        image = driver.ex_get_image(image_name)
    except:
        image = None
    return image

def find_disk(driver, disk_name, zone):
    try:
        disk = driver.ex_get_volume(disk_name, zone)
    except:
        disk = None
    return disk

def find_gpu(driver, gpu_type, zone):
    try:
        gpu = driver.ex_get_accelerator_type(
            gpu_type, zone=zone)
    except:
        gpu = None
    return gpu