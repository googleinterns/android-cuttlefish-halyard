from flask import Flask
from flask_sockets import Sockets
import json

app = Flask(__name__)
sockets = Sockets(app)

devices = {} # A dictionary of id to devices

SERVER_CONFIG = {"ice_servers": [{"urls":["stun:stun.l.google.com:19302"]}],
                 "message_type": "config"}

def send_error(msg):
    print('ERROR -', msg)

def send_server_config(ws):
    config_json = json.dumps(SERVER_CONFIG)
    ws.send(config_json)

def send_data_ws(ws, data):
    data_json = json.dumps(data)
    ws.send(data_json)

class Client:
    """Client class for users that connect to devices"""

    client_id = None
    device = None
    ws = None

    def __init__(self, ws):
        self.ws = ws

    def send_device_info(self):
        client_ws = self.ws
        device_info_msg = {}
        device_info_msg['message_type'] = 'device_info'
        device_info_msg['device_info'] = self.device.device_info
        send_data_ws(client_ws, device_info_msg)
    
    def forward_device_message(self, message):
        device_msg = {}
        device_msg['message_type'] = 'device_msg'
        device_msg['payload'] = message['payload']
        send_data_ws(self.ws, device_msg)

    def handle_connect(self, message):
        """Connects client user to device"""
        
        if 'device_id' not in message:
            send_error('Missing device_id field.')
            return

        device_id = message['device_id']        
        if self.client_id:
            send_error('Attempt to connect to multiple devices over same websocket.')
        else:
            send_server_config(self.ws)
            if device_id not in devices:
                send_error(f'Device id {device_id} not registered.')
            else:
                self.device = devices[device_id]
                self.device.register_client(self)
                print(f'Connected client {self.client_id} to device {self.device.device_id}.')
                self.send_device_info()

    def handle_forward(self, message):
        """Handle forward for client"""

        if not self.client_id:
            send_error('No device associated to client.')
        elif 'payload' not in message:
            send_error('Missing payload field.')
        else:
            self.device.forward_client_message(self.client_id, message)
            print(f'Forwarded message from client {self.client_id} to device {self.device.device_id}.')

    def process_request(self, message):
        if 'message_type' not in message:
            send_error('Missing field message_type')
        elif message['message_type'] == 'connect':
            self.handle_connect(message)
        elif message['message_type'] == 'forward':
            self.handle_forward(message)
        else:
            send_error(f'Unknown message type: {message["message_type"]}')


class Device:

    client_number = 1
    device_id = None
    device_info = None
    clients = {}

    def __init__(self, ws):
        self.ws = ws

    def forward_client_message(self, client_id, message):
        client_msg = {}
        client_msg['message_type'] = 'client_msg'
        client_msg['client_id'] = client_id
        client_msg['payload'] = message['payload']
        send_data_ws(self.ws, client_msg)

    def handle_registration(self, message):
        """Registers device id and info in device list and sends config"""

        if 'device_id' not in message:
            send_error('Missing device id in registration request')
            return

        device_id = message['device_id']
        if message['device_id'] in devices:
            send_error(f'Device with id {device_id} already exists.')
        elif 'device_info' not in message:
            send_error('Missing device info in registration request.')
        else:
            devices[device_id] = self
            self.device_id = device_id
            self.device_info = message['device_info']
            send_server_config(self.ws)
            print(f'Registered device with id {device_id}')

    def handle_forward(self, message):
        """Handles forward for device"""

        if 'client_id' not in message:
            send_error('Missing client id in forward message.')
        elif 'payload' not in message:
            send_error('Missing payload field in forward message.')
        elif message['client_id'] not in self.clients:
            send_error(f'Unregistered client id {message["client_id"]}.')
        else:
            client_id = message['client_id']
            client = self.clients[client_id]
            client.forward_device_message(message)
            print(f'Forwarded message from device {self.device_id} to client {client_id}.')

    def process_request(self, message):
        if 'message_type' not in message:
            send_error('Missing field message_type')
        elif message['message_type'] == 'register':
            self.handle_registration(message)
        elif message['message_type'] == 'forward':
            self.handle_forward(message)
        else:
            send_error(f'Unknown message type: {message["message_type"]}')

    def register_client(self, client):
        client_id = self.client_number
        client.client_id = client_id
        self.clients[client_id] = client
        self.client_number += 1

    def unregister_client(self, client_id):
        self.clients.pop(client_id)

@sockets.route('/register_device')
def register_device(ws):
    print('ws connected to /register_device')
    device = Device(ws)
        while not ws.closed:
            raw_message = ws.receive()
            message = json.loads(raw_message)
            device.process_request(message)
        if device.device_id:
            devices.pop(device.device_id)

@sockets.route('/connect_client')
def connect_client(ws):
    print('ws connected to /connect_client')
    client = Client(ws)
        while not ws.closed:
            raw_message = ws.receive()
            message = json.loads(raw_message)
            client.process_request(message)
        if client.device:
        device_id = client.device.device_id
        devices[device_id].unregister_client(client.client_id)
