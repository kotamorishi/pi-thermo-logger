# -*- coding: utf-8 -*-
# sudo -H pip3 install --upgrade luma.oled
# sudo -H pip3 install serial
# 128 x 64
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import Image, ImageFont, ImageDraw, ImageOps
import time
import os
import threading
import enum

class displayMode(enum.Enum):
   Sleep = 0
   Scan = 2
   TargetUser = 3
   Result = 4
   Log = 9


class ssd1306_oled(object):
    def __init__(self):
        print("oled initialize")
        self.displayMode = displayMode.Log
    
    def refreshThread(self):
        while True:
            # check terminate
            if(self.isShutdown == True):
                break

            #screen refresh here
            if(self.displayMode == displayMode.Sleep):
                #clear the screen and wait 1 sec.
                with canvas(self.device) as drawUpdate:
                    #drawUpdate.text((40, 40), "SLEEP" , font=self.font16, fill=100)
                    time.sleep(0.03) # 30 FPS
                continue
                

            with canvas(self.device) as drawUpdate:

                if(self.displayMode == displayMode.Result):
                    drawUpdate.text((40, 20), self.name.upper() , font=self.font16, fill=100)

                if(self.displayMode == displayMode.TargetUser):
                    drawUpdate.text((40, 20), self.name.upper() , font=self.font16, fill=100)
                    drawUpdate.text((0, 40), "measuring your temperature".upper() , font=self.font8, fill=100)
                    drawUpdate.text((40, 50), self.temp , font=self.font8, fill=100)

                    # calc width for 
                    progressWidth = 128 * self.measureProgress

                    drawUpdate.rectangle((0, 60, progressWidth, 64), outline="white", fill="white")

                if(self.displayMode == displayMode.Scan):
                    #drawUpdate.text((40, 20), "HELLO!" , font=self.font16, fill=100)
                    drawUpdate.text((20, 40), "DETECTING YOUR FACE.." , font=self.font8, fill=100)

                if(self.displayMode == displayMode.Log):
                    drawUpdate.text((10, 0), self.name , font=self.font8, fill=100)
                    drawUpdate.text((90, 0), self.status , font=self.font8, fill=100)
                    ypos = 10
                    for msg in self.lines:
                        drawUpdate.text((5, ypos), msg , font=self.font8, fill=100)
                        ypos = ypos + 9
                
            time.sleep(0.03) # 30 FPS
            
        print("refresh thread terminated.")

    def wakeUp(self):
        self.displayMode = displayMode.Scan

    # Shinuhodo kitanai code start(need to kill 'em)

    def setDisplayMode(self, mode):
        self.displayMode = mode

    def setTargetUserMode(self, name):
        self.name = name
        self.measureProgress = 0 # rest to 0%
        self.setDisplayMode(displayMode.TargetUser)

    def setResultMode(self, result):
        self.result = result
        self.setDisplayMode(displayMode.Result)


    def setup(self):
        self.serial = i2c(port=1, address=0x3C)
        self.device = ssd1306(self.serial)

        # font configuration
        self.ttf = '/usr/share/fonts/truetype/04b_03.ttf'
        basedir = os.path.dirname(os.path.realpath(__file__))
        self.imagedir = os.path.join(basedir, 'images')
        self.font8 = ImageFont.truetype(self.ttf, 8)
        self.font16 = ImageFont.truetype(self.ttf, 16)

        # logging
        self.lines = []
        self.lineNumber = 0
        
        # target user found.
        self.name = ""
        self.temp = ""
        self.measureProgress = 0 # 0 to 100 %
        self.result = None

        # flags
        self.isShutdown = False
        self.status = "BOOT"        

        #start the screen refresh thread
        self.th = threading.Thread(target=self.refreshThread, args=())
        self.th.start()
        
    def setStatus(self, statusString):
        self.status = statusString
    
    def logger(self, line):
        self.isLogMode = True
        print(str(self.lineNumber) + " " + line.upper())
        self.lines.append(str(self.lineNumber) + " " + line.upper())
        self.lineNumber = self.lineNumber + 1
        # if the line is 5+ scroll it.
        if(len(self.lines) >= 7):
            self.lines.pop(0)
        
    def setProgress(self, progress):
        self.measureProgress = progress

    def targetTemp(self, temp):
        self.temp = temp
        self.isTargetUserMode = True
        self.isScanMode = False

    
    def shutdown(self):
        # do a bit of cleanup
        self.isShutdown = True
        