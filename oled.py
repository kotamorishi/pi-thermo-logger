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
import datetime
from random import randrange


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
        self.displayProgress = 0
        self.animationFrame = 1 
        self.distanceRange = (300, 600)
        self.distance = 0
  
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
                    time.sleep(0.03)
                continue
                

            with canvas(self.device) as drawUpdate:

                if(self.displayProgress < self.measureProgress):
                    self.displayProgress = self.displayProgress + abs(self.measureProgress - self.displayProgress) / 5.0
                else:
                    self.displayProgress = self.displayProgress - abs(self.displayProgress - self.measureProgress) / 5.0

                progressWidth = 128 * self.displayProgress
                drawUpdate.rectangle((0, 63, progressWidth, 64), outline="white", fill="white")


                if(self.displayMode == displayMode.Result):
                    drawUpdate.text((5, 0), self.name.upper() , font=self.font16, fill=100)
                    drawUpdate.text((20, 10), self.result.averageTemp() + "C" , font=self.tempFont32, fill=100)
                   

                if(self.displayMode == displayMode.TargetUser):
                    drawUpdate.text((5, 0), self.name.upper() , font=self.font16, fill=100)
                    #drawUpdate.text((0, 40), "measuring your temperature".upper() , font=self.font8, fill=100)
                    #drawUpdate.text((40, 50), self.temp , font=self.font8, fill=100)
                    now = datetime.datetime.now() # current date and time
                    currentTimeString = now.strftime("%p %H:%M")
                    drawUpdate.text((90, 0), currentTimeString , font=self.font8, fill=100)


                    if(self.distance <= self.distanceRange[0]):
                        # too close
                        downBmp         = Image.open(os.path.join("images",  "down.bmp"))
                        drawUpdate.bitmap((0,0), downBmp, fill=100)
                    elif(self.distance >= self.distanceRange[1]):
                        upBmp           = Image.open(os.path.join("images",  "up.bmp"))
                        drawUpdate.bitmap((0,0), upBmp, fill=100)
                    else:
                        measureBmp      = Image.open(os.path.join("images",  "measure.bmp"))
                        drawUpdate.bitmap((0,0), measureBmp, fill=100)
                    

                if(self.displayMode == displayMode.Scan):
                    #drawUpdate.text((15, 0), "DETECTING" , font=self.font16, fill=100)
                    #drawUpdate.text((30, 20), "FACE" , font=self.font32, fill=100)
                    scanBmp      = Image.open(os.path.join("images",  "s" + str(self.animationFrame) + ".bmp"))
                    drawUpdate.bitmap((0,0), scanBmp, fill=100)
                    self.animationFrame = self.animationFrame + 1

                    now = datetime.datetime.now() # current date and time
                    currentTimeString = now.strftime("%p %H:%M")
                    drawUpdate.text((90, 0), currentTimeString , font=self.font8, fill=100)

                    time.sleep(0.03) # lower screen refresh
                    if(self.animationFrame > 14):
                        if(randrange(3) == 1):
                            self.animationFrame = 10
                        elif(randrange(3) == 2):
                            self.animationFrame = 6
                        else:
                            self.animationFrame = 1

                if(self.displayMode == displayMode.Log):
                    drawUpdate.text((10, 0), self.name , font=self.font8, fill=100)
                    drawUpdate.text((90, 0), self.status , font=self.font8, fill=100)
                    ypos = 10
                    for msg in self.lines:
                        drawUpdate.text((5, ypos), msg , font=self.font8, fill=100)
                        ypos = ypos + 9
                
            time.sleep(0.03) # 30 FPS
            
        print("refresh thread terminated.")

    def setDisplayMode(self, mode):
        self.displayMode = mode

    def setTargetUserMode(self, name):
        self.name = name
        self.setProgress(0)
        self.setDisplayMode(displayMode.TargetUser)

    def setScanMode(self):
        if(self.displayMode == displayMode.Scan):
            return
        self.setProgress(1)
        self.setDisplayMode(displayMode.Scan)

    def setResultMode(self, result):
        self.result = result
        self.setProgress(1)
        self.setDisplayMode(displayMode.Result)

    def setDistance(self, distance):
        self.distance = distance
    
    def setDistanceRange(self, distanceRange):
        self.distanceRange = distanceRange

    def setup(self):
        self.serial = i2c(port=1, address=0x3C)
        self.device = ssd1306(self.serial)

        # font configuration
        self.ttf = '/usr/share/fonts/truetype/04b_03.ttf'
        basedir = os.path.dirname(os.path.realpath(__file__))
        self.imagedir = os.path.join(basedir, 'images')
        self.font8 = ImageFont.truetype(self.ttf, 8)
        self.font16 = ImageFont.truetype(self.ttf, 16)
        self.font32 = ImageFont.truetype(self.ttf, 32)
        self.tempFont32 = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", 32)

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
        self.setDisplayMode(displayMode.Log)
        print(datetime.datetime.now().isoformat() + " " + str(self.lineNumber) + " " + line.upper())
        self.lines.append(str(self.lineNumber) + " " + line.upper())
        self.lineNumber = self.lineNumber + 1
        # if the line is 5+ scroll it.
        if(len(self.lines) >= 7):
            self.lines.pop(0)
        
    def setProgress(self, progress):
        self.measureProgress = progress
        if((progress == 1) or (progress == 0)):
            self.displayProgress = progress

    def targetTemp(self, temp):
        self.temp = temp
    
    def shutdown(self):
        # do a bit of cleanup
        self.isShutdown = True
        