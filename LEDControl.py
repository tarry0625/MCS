#!/usr/bin/env python3
import requests
import socket
import threading
import logging
import RPi.GPIO as GPIO
import time
import sys
import Adafruit_DHT
import http.client as http
import urllib
import json
deviceId = "DMtJZwJF"
deviceKey = "90rgqH0uAQjGWxHJ"
GPIO.setmode(GPIO.BCM)
GPIO.setup(24,GPIO.IN,pull_up_down=GPIO.PUD_UP)
GPIO.setup(17,GPIO.OUT)


#sudo ./MCS_ControlButton.py 11 4
#DHT11  ->  3.3v GPIO-4 ground
#Switch ->  GPIO-24 ground
#Led    ->  GPIO-17 ground


# change this to the values from MCS web console
DEVICE_INFO = {
    'device_id' : 'DyC3n5DY',
    'device_key' : '2jfe4RaoWBCOdwkv'
}

# change 'INFO' to 'WARNING' to filter info messages
logging.basicConfig(level='INFO')

heartBeatTask = None

def establishCommandChannel():
    # Query command server's IP & port
    connectionAPI = 'https://api.mediatek.com/mcs/v2/devices/%(device_id)s/connections.csv'
    r = requests.get(connectionAPI % DEVICE_INFO,
                 headers = {'deviceKey' : DEVICE_INFO['device_key'],
                            'Content-Type' : 'text/csv'})
    logging.info("Command Channel IP,port=" + r.text)
    (ip, port) = r.text.split(',')

    # Connect to command server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, int(port)))
    s.settimeout(None)

    # Heartbeat for command server to keep the channel alive
    def sendHeartBeat(commandChannel):
        keepAliveMessage = '%(device_id)s,%(device_key)s,0' % DEVICE_INFO
        keepAliveMessage = keepAliveMessage.encode(encoding="utf-8")
        commandChannel.sendall(keepAliveMessage)
        logging.info("beat:%s" % keepAliveMessage)

    def heartBeat(commandChannel):
        sendHeartBeat(commandChannel)
        # Re-start the timer periodically
        global heartBeatTask
        heartBeatTask = threading.Timer(10, heartBeat, [commandChannel]).start()

    heartBeat(s)
    return s

def waitAndExecuteCommand(commandChannel):
        command = commandChannel.recv(1024).decode(encoding="utf-8")
        logging.info("recv:" + command)
        # command can be a response of heart beat or an update of the LED_control,
        # so we split by ',' and drop device id and device key and check length
        fields = command.split(',')[2:]

        if len(fields) > 1:
            timeStamp, dataChannelId, commandString = fields
            if dataChannelId == 'LEDControl':
                # check the value - it's either 0 or 1
                commandValue = int(commandString)
                logging.info("led :%d" % commandValue)
                setLED(commandValue)

def setLED(state):
    # Note the LED is "reversed" to the pin's GPIO status.
    # So we reverse it here.
    LED=GPIO.output(17,state)

def post_to_mcs(payload):
	headers = {"Content-type": "application/json", "deviceKey": deviceKey}
	not_connected = 1
	while (not_connected):
		try:
			conn = http.HTTPConnection("api.mediatek.com:80")
			conn.connect()
			not_connected = 0
		except (http.HTTPException, socket.error) as ex:
			print ("Error: %s" % ex)
			time.sleep(10)
			 # sleep 10 seconds
	conn.request("POST", "/mcs/v2/devices/" + deviceId + "/datapoints", json.dumps(payload), headers)
	response = conn.getresponse()
	print( response.status, response.reason, json.dumps(payload), time.strftime("%c"))
	data = response.read()
	conn.close()

#if __name__ == '__main__':
channel = establishCommandChannel()
# Parse command line parameters.
sensor_args = { '11': Adafruit_DHT.DHT11,
                '22': Adafruit_DHT.DHT22,
                '2302': Adafruit_DHT.AM2302 }
if len(sys.argv) == 3 and sys.argv[1] in sensor_args:
    sensor = sensor_args[sys.argv[1]]
    pin = sys.argv[2]
else:
    print('Usage: sudo ./Adafruit_DHT.py [11|22|2302] <GPIO pin number>')
    print('Example: sudo ./Adafruit_DHT.py 2302 4 - Read from an AM2302 connected to GPIO pin #4')
    sys.exit(1)
while True:
	h0, t0= Adafruit_DHT.read_retry(sensor, pin)
	if h0 is not None and t0 is not None:
		print('Temp={0:0.1f}*  Humidity={1:0.1f}%'.format(t0, h0))
	else:
		print('Failed to get reading. Try again!')
		sys.exit(1)
	SwitchStatus=GPIO.input(24)
	if(SwitchStatus==0):
		print('Button pressed')
		SwitchStatus=1
	else:
		print('Button released')
		SwitchStatus=0
	payload = {"datapoints":[{"dataChnId":"Humidity","values":{"value":h0}},
			{"dataChnId":"Temperature","values":{"value":t0}}]}
	post_to_mcs(payload)

	payload = {"datapoints":[{"dataChnId":"SwitchStatus","values":{"value":SwitchStatus}},
			{"dataChnId":"SwitchStatus2","values":{"value":SwitchStatus}}]}
	post_to_mcs(payload)

	waitAndExecuteCommand(channel)

#	time.sleep(1)
