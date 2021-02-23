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

class ssd1306_oled(object):
    def __init__(self):
        print("oled initialize")
    
    def refreshThread(self):
        while True:
            # check terminate
            if(self.isShutdown == True):
                break

            #screen refresh here
            if(self.isSleepMode == True):
                #clear the screen and wait 1 sec.
                with canvas(self.device) as drawUpdate:
                    #drawUpdate.text((40, 40), "SLEEP" , font=self.font16, fill=100)
                    time.sleep(0.03) # 30 FPS
                continue
                

            with canvas(self.device) as drawUpdate:

                if(self.isTaegetUserMode == True):
                    drawUpdate.text((40, 20), self.name.upper() , font=self.font16, fill=100)
                    drawUpdate.text((0, 40), "measuring your temperature".upper() , font=self.font8, fill=100)
                    drawUpdate.text((40, 60), self.temp , font=self.font16, fill=100)

                if(self.isScanMode == True):
                    #drawUpdate.text((40, 20), "HELLO!" , font=self.font16, fill=100)
                    drawUpdate.text((20, 40), "DETECTING YOUR FACE.." , font=self.font8, fill=100)

                if(self.isLogMode == True):
                    drawUpdate.text((10, 0), self.name , font=self.font8, fill=100)
                    drawUpdate.text((90, 0), self.status , font=self.font8, fill=100)
                    ypos = 10
                    for msg in self.lines:
                        drawUpdate.text((5, ypos), msg , font=self.font8, fill=100)
                        ypos = ypos + 9
                
            time.sleep(0.03) # 30 FPS
            
        print("refresh thread terminated.")

    def wakeUp(self):
        self.isSleepMode = False

    def setSleepMode(self):
        self.isSleepMode = True
        self.isScanMode = False
        self.isLogMode = False
        self.isTaegetUserMode = False

    def setScanMode(self):
        self.isScanMode = True
        self.isLogMode = False
        self.isTaegetUserMode = False
    
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

        # flags
        self.isShutdown = False
        self.isLogMode = True
        self.isScanMode = False
        self.isTaegetUserMode = False
        self.isSleepMode = False
        self.status = "BOOT"


        # animation frame number
        self.scanFrame = 0 # 0 to 30

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
    
    def targetName(self, name):
        self.name = name
        self.isTaegetUserMode = True
        self.isScanMode = False

    def targetTemp(self, temp):
        self.temp = temp
        self.isTaegetUserMode = True
        self.isScanMode = False

    def update(self, distance):
        with canvas(self.device) as drawUpdate:
            drawUpdate.text((0, 0), "Distance".format((distance/ 10.0)) , font=self.font16, fill=100)
            drawUpdate.text((10, 20), "{:.0f} cm".format((distance/ 10.0)) , font=self.font16, fill=255)
            drawUpdate.text((10, 40), "{:.2f} c".format( 34.5) , font=self.font16, fill=255)
    
    def message(self, text):
        with canvas(self.device) as drawUpdate:
            drawUpdate.text((0, 20), text , font=self.font16, fill=255)
    
    def tooClose(self):
        with canvas(self.device) as drawUpdate:
            dlIcon = Image.open(os.path.join(self.imagedir,  "left.bmp"))
            drawUpdate.bitmap((0,0), dlIcon, fill=1)
            #drawUpdate.text((10, 45), "TOO CLOSE" , font=font16, fill=255)
    
    def tooFar(self):
        with canvas(self.device) as drawUpdate:
            dlIcon = Image.open(os.path.join(self.imagedir,  "right.bmp"))
            drawUpdate.bitmap((0,0), dlIcon, fill=1)
            #dlIcon = Image.open(os.path.join(imagedir,  "ghost.bmp"))
            #drawUpdate.bitmap((0,0), dlIcon, fill=1)
            drawUpdate.text((0, 0), "HARUNA" , font=self.font16, fill=255)
    
    def shutdown(self):
        # do a bit of cleanup
        self.isShutdown = True
        