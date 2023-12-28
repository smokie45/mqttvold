#!/bin/python
#
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe
import logging
import sys
import argparse
import time
import json
from types import SimpleNamespace
import subprocess

MQTT_SERVER = "192.168.0.90"
MQTT_PORT   = 1883
MQTT_TOPICS = [ 'z2m_DG/buero_rotary' ]
volume = 80
pause = False

def adjustVolume( step: int) -> int:
    """
    Increases the pulseaudio volume by step.
    Args:
        step: a pos- or negative integer to adjust the volume

    Returns:
        int: the volume
    """
    global volume, pause
    volume += int(step/2)
    if volume > 100:
        volume = 100
    if volume < 0:
        volume = 0
    pause = False
    cmd = ["/usr/bin/pactl", "set-sink-volume", "0", f"{volume}%"]
    subprocess.run( cmd )
    return volume

def togglePlay():
    global pause, volume
    newVolume = 0
    if pause:
        newVolume = volume
        pause = False
    else:
        pause = True

    cmd = ["/usr/bin/pactl", "set-sink-volume", "0", f"{newVolume}%"]
    subprocess.run( cmd )

def on_mqtt( client, userdata, msg ):
    log.debug("on_mqtt: '"+msg.topic+"' -> '" + str(msg.payload) +"'")
    # convert the received JSON payload to an python object
    o = json.loads( msg.payload, object_hook=lambda d: SimpleNamespace(**d))
    action = o.action
    step = o.action_step_size
    match action:
        case 'brightness_step_down':
            adjustVolume( step*-1 )
            log.info(f"cmd: volume down by {step} to {volume}")
        case 'brightness_step_up':
            adjustVolume( step )
            log.info(f"cmd: volume up by {step} to {volume}")
        case 'toggle':
            togglePlay()
            log.info(f"cmd: toggle_play")
        case '' | None:
            log.debug(f"cmd: idle")
        case _:
            log.error(f"cmd: unknown '{o.action}'")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info("connected to mqtt server")
        client.isConnected = True
        for topic in MQTT_TOPICS:
            log.debug(f"subscribing to mqtt topic: {topic}")
            client.subscribe( topic, 0 )
    else:
        log.error("on_connect: failed to connect to mqtt server")

def on_subscribe( client, userdata, mid, granted_qos):
    log.debug("on_subscribe:")

def on_log( client, userdata, level, buf):
    if "PING" not in buf:
        log.debug("on_log: " + buf)

my_parser = argparse.ArgumentParser(
        description='A daemon to control pulseaudio via MQTT')
my_parser.add_argument('--mqtt-server',
                       required=False,
                       type=str,
                       default=MQTT_SERVER,
                       help='Name or IP of MQTT server')
my_parser.add_argument('--mqtt-port',
                       required=False,
                       type=int,
                       default=MQTT_PORT,
                       help='Port of MQTT server')
my_parser.add_argument('--loglevel',
                       required=False,
                       type=str,
                       default="ERROR",
                       help='Set loglevel to [DEBUG, INFO, ..]')
my_parser.add_argument('--logfile',
                       required=False,
                       default=False,
                       action='store_true',
                       help='If provided, we log into a file')
args = my_parser.parse_args()

# get name of program. Remove prefixed path and postfixed fileytpe
myName = sys.argv[0]
myName = myName[ myName.rfind('/')+1: ]
myName = myName[ : myName.find('.')]

log = logging.getLogger( __name__ )
log.setLevel( getattr(logging, args.loglevel.upper()))
fmt = logging.Formatter('%(asctime)s %(levelname)7s: %(message)s')
sh  = logging.StreamHandler(sys.stdout)
sh.setFormatter( fmt )
log.addHandler( sh )
if args.logfile:
    print( 'Logging to /tmp/'+myName+'.log')
    rh = logging.handlers.RotatingFileHandler( '/tmp/'+myName+'.log',
                 maxBytes=10000000, backupCount=1 )
    rh.setFormatter( fmt )
    log.addHandler( rh )

print( 'Started ' + myName  )
state='stop'


# create mqtt client
mqttC = mqtt.Client( client_id = myName )
mqttC.isConnected = False
mqttC.on_connect = on_connect
mqttC.on_message = on_mqtt
mqttC.on_subscribe = on_subscribe
#mqttC.on_log = on_log
mqttC.connect( MQTT_SERVER, MQTT_PORT, 10)

try:
    # this is a blocking call !
    mqttC.loop_forever()
except KeyboardInterrupt:
    mqttC.loop_stop()
    mqttC.disconnect()
    print("Terminated")
