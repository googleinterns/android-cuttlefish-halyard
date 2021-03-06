
const SIG_SERVER_ADDR = "10.128.0.45"
const SIG_SERVER_PORT = "8443"

ajaxCall = function(msg, url, type, body) {
    console.log(msg);
    return $.ajax({
        url: url,
        contentType: 'application/json; charset=utf-8',
        dataType: 'json',
        type: type,
        data: JSON.stringify(body),
        success: ((res) => {
            console.log('Result: ', res);
        }),
        error: ((error) => {
            console.log('Error: ', error);
        })
    });
}

// INSTANCES

createNewInstance = function() {
    var userId = document.getElementById("userIdInput").value;
    let msg = 'New Instance AJAX call'
    let url = 'instance-list'
    let type = 'POST'
    let body = {"user_id": userId, "sig_server_addr": SIG_SERVER_ADDR,
                "sig_server_port": SIG_SERVER_PORT, "tags": ["kradtke-ssh"]}
    return ajaxCall(msg, url, type, body)
}

infoInstance = function(instance_name) {
    let msg = 'Info Instance AJAX call'
    let url = 'instance/' + instance_name
    let type = 'GET'
    let body = {}
    return ajaxCall(msg, url, type, body)
}

stopInstance = function(instance_name) {
    let msg = 'Stop Instance AJAX call'
    let url = 'instance/' + instance_name
    let type = 'DELETE'
    let body = {}
    return ajaxCall(msg, url, type, body)
}

// DISKS

restoreDisk = function(disk_name) {
    let userId = disk_name.replace(/^(halyard-user-)/,"");
    let msg = 'Restore Disk AJAX call'
    let url = 'instance-list'
    let type = 'POST'
    let body = {"user_id": userId, "sig_server_addr": SIG_SERVER_ADDR,
                "sig_server_port": SIG_SERVER_PORT, "tags": ["kradtke-ssh"]}
    return ajaxCall(msg, url, type, body)
}

deleteDisk = function(disk_name) {
    let msg = 'Delete Disk AJAX call'
    let url = 'disk/' + disk_name
    let type = 'DELETE'
    let body = {}
    return ajaxCall(msg, url, type, body)
}

// IMAGES

createNewImage = function() {
    let msg = 'New Image AJAX call'
    let url = 'image-list'
    let type = 'POST'
    let body = {"tags": ["kradtke-ssh"]}
    return ajaxCall(msg, url, type, body)
}

infoImage = function(image_name) {
    let msg = 'Info Image AJAX call'
    let url = 'image/' + image_name
    let type = 'GET'
    let body = {}
    return ajaxCall(msg, url, type, body)
}

deleteImage = function(image_name) {
    let msg = 'Delete Image AJAX call'
    let url = 'image/' + image_name
    let type = 'DELETE'
    let body = {}
    return ajaxCall(msg, url, type, body)
}
