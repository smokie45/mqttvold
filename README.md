# mqttvold - A volume daemon controlled by mqtt

This is a small daemon, which allows to remote control local audio volume (e.g. via pulseaudio) via MQTT.
It is implemented in python and utilizes [Paho MQTT](https://eclipse.dev/paho/index.php) libraries.

I'm using it to control the volume of my headless RPI by using a [Tuya Zigbee smart knob](https://www.zigbee2mqtt.io/devices/ERS-10TZBVK-AA.html) propagated via [zigbee2mqtt](https://www.zigbee2mqtt.io/).

Usage:
  - edit mqttvold.py to add your MQTT broker and the topics where the Smart knob events are
  - switch the smar knob to "event mode".
  - run the deamon on the machine having pulse audio.

Todo:
- use systemd dynamic user
- pause spotify
