#!/bin/python
""" Volume daemon controlled by MQTT

This script is a simple volume daemon, which is acting on MQTT events.
It utilizes the Eclipse paho library.

Usage:
    - edit MQTT_SERVER, MQTT_PORT and MQTT_TOPICS to match your env.
    - depending on your MQTT device, you may need to adjust on_mqtt()

"""

import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe
import logging
import sys, os
import argparse
import json
from types import SimpleNamespace
import subprocess

MQTT_SERVER = "192.168.0.90"
MQTT_PORT   = 1883
MQTT_TOPICS = [ 'z2m_DG/buero_rotary' ]

class Volume:
    """Class to handle the pulse audio volume adjusts"""
    volume = 80
    mute   = False

    def adjust( self, step: int):
        """
        Increases the pulseaudio volume by step.
        Args:
            step: a pos- or negative integer to adjust the volume
        """

        self.volume += int(step/2)
        if self.volume > 100:
            self.volume = 100   # don't go beyond 100%
        if self.volume < 0:
            self.volume = 0     # don't go below 0%
        self.mute = False       #unblock possible mute state

        log.debug(f"adjust volume by {step} to {self.volume}")
        # call pulse audio to adjust volume
        self._exec( ["/usr/bin/pactl", "set-sink-volume", "0", f"{self.volume}%"] )

    def toggleMute(self):
        """Toggles mute by toggling volume to 0 and back"""
        newVolume = 0
        if self.mute:
            newVolume = self.volume
            self.mute= False
        else:
            self.mute = True

        log.debug(f"toggle mute. Set volume to {newVolume}")
        # call pulse audio to adjust mute/unmute
        self._exec( ["/usr/bin/pactl", "set-sink-volume", "0", f"{newVolume}%"] )

    def _exec(self, cmd ):
        """Execute a cmd on host"""
        log.debug(f"excuting: '{cmd}'")
        subprocess.run( cmd )


def on_message( client, userdata, msg ):
    """Callback from paho on mqtt message receive. Let's dispatch it ..."""
    log.debug("on_mqtt: '"+msg.topic+"' -> '" + str(msg.payload) +"'")
    # convert the received JSON payload into a python object
    o = json.loads( msg.payload, object_hook=lambda d: SimpleNamespace(**d))
    action = o.action
    step = o.action_step_size
    vol = userdata
    match action:
        case 'brightness_step_down':
            vol.adjust( step*-1 )
        case 'brightness_step_up':
            vol.adjust( step )
        case 'toggle':
            vol.toggleMute()
        case '' | None:
            # this is provided as end notification after each command.
            log.debug(f"cmd: idle")
        case _:
            # the default catch .....
            log.error(f"cmd: unknown '{o.action}'")


def on_connect(client, userdata, flags, rc):
    """Callback from paho on mqtt connect.Let's subscribe to topics ..."""
    if rc == 0:
        log.info("connected to mqtt server")
        client.isConnected = True
        for topic in MQTT_TOPICS:
            log.debug(f"subscribing to mqtt topic: {topic}")
            client.subscribe( topic, 0 )
    else:
        log.error("on_connect: failed to connect to mqtt server")

def on_subscribe( client, userdata, mid, granted_qos):
    """Callback from paho on subscription."""
    log.debug("on_subscribe: " + str(mid))

def on_log( client, userdata, level, buf):
    """Calback from paho on log message"""
    if "PING" not in buf:
        log.debug("on_log: " + buf)

if __name__ == "__main__":
    # parse the cmdline options
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

    #instanciating a logger
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

    vol = Volume()
    # create mqtt client and connect to it ....
    myPid=os.getpid()
    mqttC = mqtt.Client( client_id = f"{myName}_{myPid}", userdata=vol )
    mqttC.isConnected = False
    mqttC.on_connect = on_connect
    mqttC.on_message = on_message
    mqttC.on_subscribe = on_subscribe
    mqttC.on_log = on_log
    mqttC.connect( MQTT_SERVER, MQTT_PORT, 10)

    try:
        # this is a blocking call !
        mqttC.loop_forever()
    except KeyboardInterrupt:
        mqttC.loop_stop()
        mqttC.disconnect()
        print("Terminated")
