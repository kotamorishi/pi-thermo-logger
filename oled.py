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
#import concurrent.futures

bootupSequence = ["b1","b2","b3","b3","b3", # wake up
    "s1","s2","s3","s4","s5","s6","s7","s8","s7","s6", # left-right
    "b4","b5","b6","b5","b4"]

scanSequence = ["b1","b2","b3","b3","b3", # wake up
    "s1","s2","s3","s4","s5","s6","s7","s8","s9","s8","s7","s6", # left-right
    "s11","s12","s13","s12","s11"] # blink]

backSequence = ["back1","back2","back3","back2","back1","back1","back1"]


# I was lazy enough to fix the bitmaps, so here is the pixel shift mappings ;p
imageXShift = {
    "s1":"0",
    "s2":"-4",
    "s3":"-6",
    "s4":"-6",
    "s5":"-4",
    "s6":"0",
    "s7":"4",
    "s8":"6",
    "s9":"6",
    "s10":"4",
    "s11":"0",
    "s12":"0",
    "s13":"0",
    "s14":"0",
    "s15":"0",
    "s16":"0",
}


class displayMode(enum.Enum):
    Sleep = 0
    Scan = 2
    TargetUser = 3
    Result = 4
    Log = 9
    Boot = 10

class ssd1306_oled(object):
    def __init__(self):
        print("oled initialize")
        self.displayMode = displayMode.Boot
        self.displayProgress = 0
        self.animationFrame = 1 
        self.distanceRange = (300, 600)
        self.distance = 0

    def imageShiftAmount(self, name):
        if(name[0] == "s"):
            return int(imageXShift[name])
        else:
            return 0
  
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
                    drawUpdate.text((20, 20), self.result.averageTemp() + "C" , font=self.tempFont32, fill=100)
                   

                if(self.displayMode == displayMode.TargetUser):
                    drawUpdate.text((5, 0), self.name.upper() , font=self.font16, fill=100)
                    #drawUpdate.text((0, 40), "measuring your temperature".upper() , font=self.font8, fill=100)
                    #drawUpdate.text((40, 50), self.temp , font=self.font8, fill=100)
                    now = datetime.datetime.now() # current date and time
                    currentTimeString = now.strftime("%p %H:%M")
                    drawUpdate.text((90, 0), currentTimeString , font=self.font8, fill=100)


                    if(self.distance <= self.distanceRange[0]):
                        # too close
                        if(self.animationFrame >= len(backSequence)):
                            self.animationFrame = 1
                        downBmp         = Image.open(os.path.join("images",  backSequence[self.animationFrame] + ".bmp"))
                        drawUpdate.bitmap((0,0), downBmp, fill=100)
                        self.animationFrame = self.animationFrame + 1
                    elif(self.distance >= self.distanceRange[1]):
                        if(self.animationFrame >= len(scanSequence)):
                            self.animationFrame = 1
                        upBmp      = Image.open(os.path.join("images",  scanSequence[self.animationFrame] + ".bmp"))
                        drawUpdate.bitmap((self.imageShiftAmount(scanSequence[self.animationFrame]),10), upBmp, fill=100)
                        self.animationFrame = self.animationFrame + 1

                    else:
                        measureBmp      = Image.open(os.path.join("images",  "measure.bmp"))
                        drawUpdate.bitmap((0,0), measureBmp, fill=100)
                    

                if(self.displayMode == displayMode.Scan):
                    scanBmp      = Image.open(os.path.join("images",  scanSequence[self.animationFrame] + ".bmp"))
                    drawUpdate.bitmap((self.imageShiftAmount(scanSequence[self.animationFrame]),10), scanBmp, fill=100)
                    self.animationFrame = self.animationFrame + 1

                    now = datetime.datetime.now() # current date and time
                    currentTimeString = now.strftime("%p %H:%M")
                    drawUpdate.text((90, 0), currentTimeString , font=self.font8, fill=100)

                    time.sleep(0.03) # lower screen refresh
                    if(self.animationFrame == 16):
                        if(randrange(1) == 1):
                            self.animationFrame = 6
                    
             

                    if(self.animationFrame >= len(scanSequence)):
                        self.animationFrame = 4
                        
                
                if(self.displayMode == displayMode.Boot):
                    bootSeqBmp      = Image.open(os.path.join("images",  bootupSequence[self.animationFrame] + ".bmp"))
                    drawUpdate.bitmap((0,10), bootSeqBmp, fill=100)
                    self.animationFrame = self.animationFrame + 1

                    now = datetime.datetime.now() # current date and time
                    currentTimeString = now.strftime("%p %H:%M")
                    drawUpdate.text((90, 0), currentTimeString , font=self.font8, fill=100)

                    if(self.animationFrame >= len(bootupSequence)):
                        self.animationFrame = 3

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
        if(mode == displayMode.Sleep):
            self.animationFrame = 0

    def setTargetUserMode(self, name):
        self.name = name
        self.setProgress(0)
        self.setDisplayMode(displayMode.TargetUser)

    def setScanMode(self):
        if(self.displayMode == displayMode.Scan):
            return
        self.setProgress(1)
        self.setDisplayMode(displayMode.Scan)
        self.animationFrame = 0

    def setResultMode(self, result):
        self.result = result
        self.setProgress(1)
        self.setDisplayMode(displayMode.Result)

    def setDistance(self, distance):
        self.distance = distance
    
    def setDistanceRange(self, distanceRange):
        self.distanceRange = distanceRange

    def setup(self, i2c_address=0x3C):
        self.serial = i2c(port=1, address=i2c_address)
        self.device = ssd1306(self.serial)

        # font configuration
        self.ttf = '/usr/share/fonts/truetype/04B_03__.TTF'
        basedir = os.path.dirname(os.path.realpath(__file__))
        self.imagedir = os.path.join(basedir, 'images')
        self.font8 = ImageFont.truetype(self.ttf, 8)
        self.font16 = ImageFont.truetype(self.ttf, 16)
        self.font32 = ImageFont.truetype(self.ttf, 32)
        self.tempFont32 = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoMono-Regular.ttf", 32)

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

        # this thrad pool not works as I wanted.
        #self.threadExcuter = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        #self.threadExcuter.submit(self.refreshThread)
        
    def setStatus(self, statusString):
        self.status = statusString
    
    def logger(self, line):
        #self.setDisplayMode(displayMode.Log)
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
        
