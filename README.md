# timelapse_tool
A simple and automated timelapse tool built using Python and a Raspberry Pi with a camera hat.
The tool takes as input the final length in seconds, the desired framerate and the real time duration in days and based on these values
computes the necessary number of frames to be taken each day and equally spaces them out in between sunrise and sunset.
It is designed to be completely autonomous, saving its state and progress at every step, and because it runs as a service it is able to recover itself 
from a crash.
