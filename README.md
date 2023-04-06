# iot_based_surveillance_system_using_raspberry_pi
Python script for a EEE BEng university project. The aim of the project was to develop a prototype IoT-based surveillance system using low-cost off the shelf components that will be used in a residential property. 

The system was tested with two IP cameras at frame rates between 10 to 15 fps, and resolutions between 720p to 1080p. After testing, would reccomend that the IP cameras be set to a resolution of 720p at 10 fps as the code would become unstable at a resolution of 1080p. 

At 720p a 3rd IP camera can be used with this code. Feel free to copy and customise the code for your own needs.

Hardware details: 1x 8 GB Raspberry Pi 4 Model B (SBC), 1x PoE Hat D (from Pi Hut), 1x SanDisk Ultra 32 GB (micro-SD card), 1x TL-SF1005LP (PoE Network Switch), 2x IPC-T221H (IP Camera).

SBC OS details: Raspberry Pi OS with Desktop, Debian version 11, bullseye, 64-bit.

Remote access software: VNC Viewer.

BoM Price: ~£200.

N.B. The code is CPU intensive, not RAM intensive. Thus, a 4 GB version can be used in place of the 8 GB version of the Raspberry Pi 4 Model B.
