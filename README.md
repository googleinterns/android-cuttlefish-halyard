Halyard
=======

Orchestration service that coordinates Cuttlefish virtual devices in the cloud.

## Getting Started

We must have a GCP project configured and an authenticated account on gcloud CLI that is able to create new instances.

### Preparing the instance

The main API and server run inside a GCE instance. A service account is needed in order for the instance to be able to access other GCE resources through the apache-libcloud library. You can create a new instance with the required values through the gcloud CLI.

```bash
$ gcloud compute instances create \
  --image-project=cloud-android-testing \
  --image-family=halyard-aosp-master-aosp-cf-x86-phone-userdebug \
  --machine-type=n1-standard-16 \
  --scopes storage-ro,https://www.googleapis.com/auth/compute \
  --service-account ${SERVICE_ACCOUNT} \
  --boot-disk-size=30GiB \
  --min-cpu-platform="Intel Haswell" \
  ${USERNAME}-halyard-operator
```

- The image family was set to one of the `halyard` families but it is not strictly necessary to initialize the instance with this image.
- ${SERVICE_ACCOUNT} refers to the default service account in the project where the instance will exist.
- ${USERNAME} can be replaced with your username or some other name to give this instance that will hold the service.


### How to install

From the command line in the newly created GCE instance:

```bash
# Clone this repository
$ git clone https://github.com/googleinterns/android-cuttlefish-halyard.git

# Go into the repository
$ cd android-cuttlefish-halyard

# Install dependencies
$ pip3 install -r requirements.txt

# Run the app (Runs on port 5000)
$ python3 main.py

# In another terminal run the signaling server (Runs on port 8000)
$ python3 wsgi.py
```

The main API and demo UI will be accessible on port 5000 while the signaling server will be running on port 8000.

### Secure WS Setup

When launching a new Cuttlefish device, it registers itself to the signaling server by using secure websockets. When we run the flask applications normally, they don't use HTTPS. In order to provide this in a development setup we can use `nginx` to create a reverse proxy server.

To install `nginx`:

```bash
$ sudo apt update
$ sudo apt install nginx
```

We can check with the `systemd` init system to make sure the service is running by typing:
```bash
$ systemctl status nginx
```

We now have to create reverse proxies for each of our servers (the main API and the signaling server).
To do that create the following files and copy the sample code from the `reamde-extra` directory.

From the proxy-api file. (link missing)
```bash
$ sudo vim /etc/nginx/sites-available/proxy-api
```

From the proxy-signaling-server file. (link missing)
```bash
$ sudo vim /etc/nginx/sites-available/proxy-signaling-server
```

Link these new files with the `sites-enabled` directory.
```bash
$ sudo ln -s /etc/nginx/sites-available/proxy-api /etc/nginx/sites-enabled/
$ sudo ln -s /etc/nginx/sites-available/proxy-signaling-server /etc/nginx/sites-enabled/
```

To make sure there are no syntax errors in any of the nginx files:
```bash
$ sudo nginx -t
```

We can now restart nginx:
```bash
$ sudo systemctl restart nginx
```

And now we can access the port 5001 through a web browser using HTTPS, while new devices can register themselves in port 8443 with wss.

## How to use

When launching both servers one can access the Demo UI on either http://localhost:5000 or https://localhost:5001. Due to these running on a GCE instance one might set up port forwarding in order for these pages to be accessible from the local machine.
From here a user can interact with various endpoints that the API implements.

In case the signaling server was just launched but instances appear on the instances list, these need to be destroyed and restored, or relaunched in order to connect to the signaling server. Since the register message is only sent the moment Cuttlefish launches, these instances will not be registered with the new server instance and therefore will not be accessible through the device interface unless relaunched.

<!-- LICENSE -->
## License

Distributed under the Apache License. See `LICENSE` for more information.
