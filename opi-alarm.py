#!/usr/bin/env python
'''
This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
__author__ = "Bogusz Jelinski"
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Bogusz Jelinski"
__email__ = "bogusz.jelinski@gmail.com"
__status__ = "Production"

import serial
import time
import os
import os.path
from pyA20.gpio import gpio
from pyA20.gpio import port

gpio.init()
 
green_led = port.PC7
red_led = port.PC4
pir_io = port.PA8
pir2_io = port.PA9
switch_io = port.PA7
alarm_startup = 10  # secs
alarm_on = 0

gpio.setcfg(green_led, gpio.OUTPUT) # green led
gpio.setcfg(red_led, gpio.OUTPUT) # red led
gpio.setcfg(pir_io, gpio.INPUT) # PIR
gpio.setcfg(pir2_io, gpio.INPUT) # 
gpio.setcfg(switch_io, gpio.INPUT)

rfid_lst = []
email = 'bogusz.jelinski@gmail.com'
msg = 'alarmmsg.txt'
rfid_nrs = 'rfid.txt'
max_tries=3

def blink (led, tme):
    gpio.output(led,gpio.HIGH)
    time.sleep(tme)
    gpio.output(led,gpio.LOW)

def log_activity (str):
    print (time.ctime() + ": "+ str)

def send_email(str):
    global email
    global msg
    # you may use any video dump utility you want 
    os.system ('modprobe -r vfe_v4l2 && sleep 1 && modprobe vfe_v4l2')
    os.system ('streamer -c /dev/video0 -s 640x480 -o camdump.jpeg  > /dev/null')
    os.system ('streamer -c /dev/video1 -s 640x480 -o camdump2.jpeg > /dev/null')
    os.system ('mail -s "'+str+'" -t '+email+' -A camdump.jpeg -A camdump2.jpeg < '+ msg)

def watch_loop ():
    global alarm_on
    global max_tries
    bad_tries = 0
    ser = serial.Serial('/dev/ttyS1', 9600, timeout=1)
    log_activity("Starting survailance ...")
    t1 = time.time()
    while True:
        # try to read from RFID reader
        try:  
            sr = ser.read(12)
            s = sr.decode('utf8')
            if bad_tries <= max_tries and len(s) != 0:
               sl = s[1:11] #exclude start x0A and stop x0D bytes
               if sl in rfid_lst: # this list is read from rfid.txt
                   alarm_on = 0
                   log_activity ("Alarm disarmed")
                   blink (green_led,4)
                   ser.close() # keeping the serial always open was a source of troubles
                   break # quit the 'alarm_on' loop
               else: # it is not friendly RFID tag/badge
                   bad_tries = bad_tries+1
                   if bad_tries > max_tries:
                      send_email('Exceeded number of tries')
        except Exception as e:
            log_activity ("error: " + format(e))
        # is there any intruder ?    
        pir  = gpio.input(pir_io)
        pir2 = gpio.input(pir2_io)
        if pir==1 or pir2==1:       
            log_activity ("Intruder detected")
            # take a photo, send email here !!!!
            send_email('Alarm')
            blink (red_led,1)
        time.sleep(0.01)  # give the processor some rest for context switching 
        t2 = time.time()
        if t2-t1>10: #   10 seconds between blinks
            t1 = t2
            blink (red_led, 0.1) 

def standby_loop ():
    global alarm_on
    t1 = time.time()
    # just wait for the button to be pressed
    while True:
        input_state = gpio.input(switch_io)
        if input_state == 0: # pressed; pullup resistor config
            alarm_on = 1
            for num in range(0,alarm_startup):  # give some time to leave the house
               blink (green_led,0.5)
               time.sleep(0.5)
            return  # leave the standby loop
        time.sleep(0.01)   
        t2 = time.time()
        if t2-t1>10: #   10 seconds between blinks
            t1 = t2
            blink (green_led,0.1)

def read_cfg():
  global rfid_lst
  if os.path.exists(rfid_nrs):
    statinfo = os.stat(rfid_nrs)
    if statinfo.st_size>0:
       f = open(rfid_nrs, 'r')
       for line in f:
          rfid_lst.append(line[0:10])
          print(line)
       f.close()
  else: # no file or empty -> learning mode
    f = open(rfid_nrs, 'w')
    ser = serial.Serial('/dev/ttyS1', 9600, timeout=1)
    while True:
        sr = ser.read(12)
        s = sr.decode('utf8')
        if len(s) != 0:
            sl = s[1:11] #exclude start x0A and stop x0D bytes
            if sl not in rfid_lst and len(sl)>2: # hardcode, just longer than a new line
               f.write(sl+'\n')
               rfid_lst.append(sl)
            blink (green_led,2)
        # but check if not the end of learning -> button press
        input_state = gpio.input(switch_io)
        if input_state == 0: # pressed; pullup resistor config
            blink (red_led,2)
            break
        blink (green_led,0.5)
        time.sleep(0.5)   
        blink (red_led,0.5)
        time.sleep(0.2)   
    f.close()
            
try:
    read_cfg() # read RFID tags
    while True:
        if (alarm_on):
            watch_loop()
        else: # the part while the alarm state is OFF - alarm has been switched off in watch_loop()
            standby_loop()
    log_activity("closing...")
except Exception as e:
    log_activity("error: "+format(e))
   
