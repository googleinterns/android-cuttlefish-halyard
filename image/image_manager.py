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
