from Adafruit_AMG88xx import Adafruit_AMG88xx
import os
import math
import time
import busio
import board
import smbus
import numpy
from gpiozero import LED

# I2C address setting
AMG8833_ADDRESS = 0x69 # set address for AMG8833(0x68 or 0x69)
# when detected the face, will scan frequently.
freqencyScanDuration = 5000 # 5 sec
# Seconds to sleep with inactivity
noneActivityDuration = 10000 # 30 sec
# Thermal camera measure count(default : 20 times, 30 times makes slightly better?)
thermalCameraMeasureCount = 30

# init i2c bus
i2c_bus = busio.I2C(board.SCL, board.SDA)
i2c = smbus.SMBus(1)

led = LED(18)
led.on()

import oled
from oled import displayMode
oled = oled.ssd1306_oled()
oled.setup()

oled.logger("VL53L0X ToF..")
from vl53l0x.api import VL53L0X
tof = VL53L0X()
tof.setup()

oled.logger("Camera face recognizer..")
from faceRecognizer import recognizer
fRecognizer = recognizer()
fRecognizer.setup()

os.putenv('SDL_FBDEV', '/dev/fb1')

#initialize the sensor
oled.logger("AMG8833..")
sensor = Adafruit_AMG88xx(0x00, AMG8833_ADDRESS)

# Operating Modes
#AMG88xx_NORMAL_MODE = 0x00
#AMG88xx_SLEEP_MODE = 0x01
#AMG88xx_STAND_BY_60 = 0x20
#AMG88xx_STAND_BY_10 = 0x21

# enable moving average
i2c.write_byte_data(AMG8833_ADDRESS, 0x1F, 0x50)
i2c.write_byte_data(AMG8833_ADDRESS, 0x1F, 0x45)
i2c.write_byte_data(AMG8833_ADDRESS, 0x1F, 0x57)
i2c.write_byte_data(AMG8833_ADDRESS, 0x07, 0x20)
i2c.write_byte_data(AMG8833_ADDRESS, 0x1F, 0x00)

#some utility functions
def constrain(val, min_val, max_val):
    return min(max_val, max(min_val, val))

def map(x, in_min, in_max, out_min, out_max):
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

#let the sensor initialize
oled.logger("waiting for sensors...")
time.sleep(1)
oled.setStatus("READY")
oled.logger("READY")
led.off()

class measureResult:
	def __init__(self, name, measureCount):
		self.name = name
		self.measureCount = measureCount
		self.results = []
	def addMeasureResut(self, result):
		# exclude out of range values.. here
		self.results.append(result)
		if(len(self.results) == self.measureCount):
			return True
		return False

	def getName(self):
		return self.name

	def getProgress(self):
		currentMeasureCount = len(self.results)
		print("progress : " + str(currentMeasureCount / self.measureCount))
		return currentMeasureCount / self.measureCount

	def averageTemp(self):
		sampleCount = len(self.results)
		for result in self.results:
			print(result)


class thermalLogger:
	def __init__(self):
		print("initalize thermal logger")

	def main(self):
		try:

			# for sleep
			latestActivityAt = int(time.time() * 1000) - noneActivityDuration # lastseen timestamp in ms

			# for user lock on
			currentTargetLastseenAt = 0 # lastseen timestamp in ms
			currentDetectedPerson = None
			currentUserResult = None

			while(True):

				if(int(time.time() * 1000) - latestActivityAt > noneActivityDuration):
					currentDetectedPerson = None
					oled.setStatus(str(int((time.time() * 1000) - latestActivityAt) / 1000) + " s")
					oled.setDisplayMode(displayMode.Sleep)
					time.sleep(0.2)
					# check distance sensor
					distance = tof.measure()
					#print("d : " + str(distance) + " diff: " + str(int(time.time() * 1000) - latestActivityAt) + " cur : " + str(int(time.time() * 1000)) + " / " + str(latestActivityAt))
					if(distance < 2000):
						print("range sensor detected")
						oled.wakeUp()
						latestActivityAt = int(time.time() * 1000)

					continue

				led.on()
				#when camera detect the face, start the 
				detectedPerson = fRecognizer.lookout()
				led.off()

				#print("==> " + str(int(time.time() * 1000) - currentTargetLastseenAt) + " ms")

				# If user cannot recognized on the camera, try to recognize as fast as possible.
				# Once face recognized, ignore no detection within 3 seconds. Also assume the same person is there.
				if((int(time.time() * 1000) - currentTargetLastseenAt > 3000) and (detectedPerson == None)):
					# recognized face within 5 seconds, continue immediately.
					oled.setDisplayMode(displayMode.Scan)
					#print("skipping ToF.. try to recognize user.")
					continue


				# update latests
				if((detectedPerson != None) and (detectedPerson.name != "Unknown")):
					latestActivityAt = int(time.time() * 1000)
					currentTargetLastseenAt = int(time.time() * 1000)


				# when face is not detected, copy latest copy of the detect info.
				if(detectedPerson == None):
					detectedPerson = currentDetectedPerson

				if(detectedPerson.name != "Unknown"):
					if(currentDetectedPerson == None) or (detectedPerson.name != currentDetectedPerson.name):
						# detect person and initialize
						currentUserResult = measureResult(detectedPerson.name, thermalCameraMeasureCount)
						oled.setTargetUserMode(detectedPerson.name)
					currentDetectedPerson = detectedPerson
					# update latest activity timestamp


				# check the distance between AMG8833 and human. 
				distance = tof.measure()
				if(distance <= 300):
					oled.setStatus("CLOSE")
					continue
				elif(distance >= 600):
					oled.setStatus("FAR")
					continue
				else:
					oled.setStatus(str(distance) +" mm")
					#oled.logger("Distance "+ str(distance) +" mm")
				
				#read the pixels
				pixels = sensor.readPixels()
				#print(pixels)

				pixels_array = numpy.array(pixels)
				pixels_max   = numpy.amax(pixels_array)
				pixels_min   = numpy.amin(pixels_array)
				thermistor_temp = i2c.read_word_data(AMG8833_ADDRESS, 0xE)
				thermistor_temp = thermistor_temp * 0.0625
				offset_thrm = (-0.6857*thermistor_temp+27.187) # thermistor correction
				offset_thrm = offset_thrm-((60-(distance/10))*0.064) # correction with distance
					
				offset_temp = offset_thrm
				max_temp =  round(pixels_max + offset_temp, 1) 
				print('temp:' + str(max_temp) + ' c / distance ' + str(distance/10) + 'cm')
				oled.targetTemp(str(max_temp) + ' c ' + str(distance/10) + 'cm')

				isMeasureComplete = currentUserResult.addMeasureResut(max_temp)
				oled.setProgress(currentUserResult.getProgress())

				if(isMeasureComplete):
					# move to result mode
					print("complete measurement for " + currentUserResult.getName())
					self.showUserResult(currentUserResult)

		except KeyboardInterrupt:
			oled.logger("shutdown")
			oled.shutdown()
			fRecognizer.shutdown()

	def showUserResult(self, userResult):
		# save to file

		oled.setResultMode(userResult)
		#oled.setDisplayMode(displayMode.Result)
		time.sleep(10)
		# if user is not detected for 3 seconds, return to the main loop



# run it
tl = thermalLogger()
tl.main()