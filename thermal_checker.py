from Adafruit_AMG88xx import Adafruit_AMG88xx
import os
import math
import datetime
import time
import busio
import board
import smbus
import numpy
import queue
import csv
from gpiozero import LED


# when detected the face, will scan frequently.
freqencyScanDuration = 5000 # 5 sec
# Seconds to sleep with inactivity
noneActivityDuration = 30000 # 30 sec
# Thermal camera measure count(default : 10 times, 30 times makes slightly better?)
thermalCameraMeasureCount = 10
# Face recognition skip threshold (User recognized consecutive 2 times ,then skip 2 seconds)
faceRecognitionSkipThreshold = 2
faceRecognitionSkipDuration = 2000 # in ms

# Sleep / Wake up range (1.5m)
wakeUpRangeThreshold = 1500

# exclude measurements
#excludeTemp = (30, 42) # low, high
distanceRange = (300, 600) # close, far

# User surface to internal temp adjustment - this is totall depending on person.
userOffsets = {'Kota':1.5, 'Taro':1.2, 'Hanako':0.3}

# i2c addresses - check with "i2cdetect -y 1"
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 00:          -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 20: -- -- -- -- -- -- -- -- -- 29 -- -- -- -- -- -- 
# 30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- -- 
# 40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 60: -- -- -- -- -- -- -- -- -- 69 -- -- -- -- -- -- 
# 70: -- -- -- -- -- -- -- --     
# AMG8833 (default:0x69)
I2C_ADDRESS_AMG8833=0x69
# OLED SSD1306 (default:0x3C)
I2C_ADDRESS_OLED=0x3C
# VL53L0X (default:0x29)
I2C_ADDRESS_VL53L0X=0x29

# init i2c bus
i2c_bus = busio.I2C(board.SCL, board.SDA)
i2c = smbus.SMBus(1)

led = LED(18)
led.on()

import oled
from oled import displayMode
oled = oled.ssd1306_oled()
oled.setup(i2c_address=I2C_ADDRESS_OLED)
oled.setDistanceRange(distanceRange)

oled.logger("VL53L0X ToF..")
from vl53l0x.api import VL53L0X
tof = VL53L0X(I2C_ADDRESS_VL53L0X)
tof.setup()
oled.setProgress(0.2)

oled.logger("Camera face recognizer..")
from faceRecognizer import recognizer
fRecognizer = recognizer()
fRecognizer.setup()
oled.setProgress(0.6)

os.putenv('SDL_FBDEV', '/dev/fb1')

#initialize the sensor
oled.logger("AMG8833..")
sensor = Adafruit_AMG88xx(0x00, I2C_ADDRESS_AMG8833)
oled.setProgress(0.8)
# Operating Modes
#AMG88xx_NORMAL_MODE = 0x00
#AMG88xx_SLEEP_MODE = 0x01
#AMG88xx_STAND_BY_60 = 0x20
#AMG88xx_STAND_BY_10 = 0x21

# enable moving average
i2c.write_byte_data(I2C_ADDRESS_AMG8833, 0x1F, 0x50)
i2c.write_byte_data(I2C_ADDRESS_AMG8833, 0x1F, 0x45)
i2c.write_byte_data(I2C_ADDRESS_AMG8833, 0x1F, 0x57)
i2c.write_byte_data(I2C_ADDRESS_AMG8833, 0x07, 0x20)
i2c.write_byte_data(I2C_ADDRESS_AMG8833, 0x1F, 0x00)

#some utility functions
def constrain(val, min_val, max_val):
    return min(max_val, max(min_val, val))

def map(x, in_min, in_max, out_min, out_max):
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

#let the sensor initialize
oled.logger("waiting for sensors...")
oled.setProgress(0.9)
time.sleep(1)
oled.setProgress(1)
oled.setStatus("READY")
oled.logger("READY")
led.off()

class measureResult:
	def __init__(self, name,measureCount, offset = 0):
		self.name = name
		self.measureCount = measureCount
		self.estimated = []
		self.thermista = []
		self.distance = []
		self.raw = []
		self.offset = offset

	def addMeasureResut(self, estimatedTemp, thermistaTemp, distance, rawTemp):
		# exclude out of range values.. here
		self.estimated.append(estimatedTemp + self.offset)
		self.thermista.append(thermistaTemp)
		self.distance.append(distance)
		self.raw.append(rawTemp)
		print( datetime.datetime.now().isoformat() + " Sample[" + str(len(self.estimated)) + "] User : " + self.name + " TEMP : " + str(round(float(estimatedTemp+self.offset), 1)))
		if(len(self.estimated) == self.measureCount):
			return True
		return False

	def getName(self):
		return self.name

	def getProgress(self):
		currentMeasureCount = len(self.estimated)
		return currentMeasureCount / self.measureCount

	def averageTemp(self):
		avg = numpy.average(numpy.array(self.estimated))
		#print( datetime.datetime.now().isoformat() + " User : " + self.name + " TEMP : " + str(round(float(avg), 1)))
		return str(round(float(avg), 1))
		
		


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
			shouldSkipFaceRecognitionUntil = time.time() * 1000
			recognizedQueue = queue.Queue(maxsize=faceRecognitionSkipThreshold)

			while(True):

				if(int(time.time() * 1000) - latestActivityAt > noneActivityDuration):
					currentDetectedPerson = None
					oled.setStatus(str(int((time.time() * 1000) - latestActivityAt) / 1000) + " s")
					oled.setDisplayMode(displayMode.Sleep)
					time.sleep(0.2)
					# check distance sensor
					distance = tof.measure()
					#print("d : " + str(distance) + " diff: " + str(int(time.time() * 1000) - latestActivityAt) + " cur : " + str(int(time.time() * 1000)) + " / " + str(latestActivityAt))
					if(distance < wakeUpRangeThreshold):
						oled.logger("Range sensor detected at "+ str(distance) +" mm")
						oled.setProgress(1) # full progress
						oled.setScanMode()
						latestActivityAt = int(time.time() * 1000)

					continue


				led.on()
				detectedPerson = None
				# if the same person is keep detecting, we can skip for a while.
				if(time.time() * 1000 < shouldSkipFaceRecognitionUntil):
					# skip face recognition(just detect face)
					faceRecogResult = fRecognizer.lookout(shouldRecognizeFace=False)
					if(faceRecogResult != None):
						detectedPerson = currentDetectedPerson
				else:
					# try camera for face recognition
					detectedPerson = fRecognizer.lookout()
					if(detectedPerson != None):
						print("detected : " + detectedPerson.name)
						if(detectedPerson.name != "Unknown"):
							# if the queue is full, remove it.
							if(recognizedQueue.qsize() == faceRecognitionSkipThreshold):
								recognizedQueue.get_nowait()
							recognizedQueue.put_nowait(detectedPerson.name)
						# check if entire queue is the same person, then set skip for 2 seconds
						if(recognizedQueue.qsize() == faceRecognitionSkipThreshold):
							isSamePerson = True
							for name in recognizedQueue.queue:
								if(detectedPerson.name != name):
									isSamePerson = False

							if(isSamePerson == True):
								shouldSkipFaceRecognitionUntil = shouldSkipFaceRecognitionUntil = time.time() * 1000 + faceRecognitionSkipDuration
				led.off()


				#print("==> " + str(int(time.time() * 1000) - currentTargetLastseenAt) + " ms")

				# If user cannot recognized on the camera, try to recognize as fast as possible.
				# Once face recognized, ignore no detection within 3 seconds. Also assume the same person is there.
				if((int(time.time() * 1000) - currentTargetLastseenAt > 3000) and (detectedPerson == None)):
					# recognized face within 5 seconds, continue immediately.
					#print("Transition to Scan mode")
					currentDetectedPerson = None
					oled.setScanMode()
					# send sleep until progress to OLED
					oled.setProgress(1 - ( int(time.time() * 1000) - latestActivityAt ) / noneActivityDuration)
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
						offsetAmount = 0
						try:
							offsetAmount = userOffsets[detectedPerson.name]
						except KeyError:
							pass

						currentUserResult = measureResult(detectedPerson.name, thermalCameraMeasureCount, offsetAmount)
						oled.setTargetUserMode(detectedPerson.name)
					currentDetectedPerson = detectedPerson
					# update latest activity timestamp

				# skip for not-detecting people
				if(currentUserResult == None):
					continue

				# check the distance between AMG8833 and human. 
				distance = tof.measure()
				oled.setDistance(distance)
				print("distance : " + str(distance))

				if(distance <= distanceRange[0]):
					continue
				elif(distance >= distanceRange[1]):
					continue
				
				#read the pixels
				pixels = sensor.readPixels()
				#print(pixels)

				pixels_array = numpy.array(pixels)
				pixels_max   = numpy.amax(pixels_array)
				#pixels_min   = numpy.amin(pixels_array) #never used
				thermistor_temp = i2c.read_word_data(AMG8833_ADDRESS, 0xE)
				thermistor_temp = thermistor_temp * 0.0625
				offset_thrm = (-0.6857*thermistor_temp+27.187) # thermistor correction
				offset_thrm = offset_thrm-((60-(distance/10))*0.065) # correction with distance
					
				offset_temp = offset_thrm
				max_temp =  round(pixels_max + offset_temp, 1) 
				#print('temp:' + str(max_temp) + ' c / distance ' + str(distance/10) + 'cm')
				#oled.targetTemp(str(max_temp) + ' c ' + str(distance/10) + 'cm')


				isMeasureComplete = currentUserResult.addMeasureResut(max_temp, thermistor_temp, distance, pixels_max)
				oled.setProgress(currentUserResult.getProgress())

				if(isMeasureComplete):
					# move to result mode
					print("complete measurement for " + currentUserResult.getName())
					self.showUserResult(currentUserResult)

					# restore scan mode
					currentDetectedPerson = None
					currentUserResult = None
					oled.setScanMode()

		except KeyboardInterrupt:
			oled.logger("shutdown")
			oled.shutdown()
			fRecognizer.shutdown()

		print("bye!")

	def showUserResult(self, userResult):
		oled.setResultMode(userResult)

		# save to file
		self.writeToCSV(userResult)
		
		for x in range(50):
			oled.setProgress( 1 - (x / float(50)))
			time.sleep(0.1)
		# if user is not detected for 3 seconds, return to the main loop
		time.sleep(0.2)

	def writeToCSV(self, userResult):
		try:
			from pathlib import Path
			Path(os.path.join("history")).mkdir(parents=True, exist_ok=True)
			filepath = os.path.join("history", userResult.name + ".csv")

			# if file does not exists, add header
			shouldMakeHeader = False
			if(os.path.exists(filepath) == False):
				shouldMakeHeader = True

			# open file
			f = open(filepath, 'a')

			writer = csv.writer(f, lineterminator='\n')

			# header write
			if(shouldMakeHeader == True):
				csvlist = []
				csvlist.append("timestamp")
				csvlist.append("Estimated")
				csvlist.append("Estimate")
				csvlist.append("Thermistor")
				csvlist.append("Distance")
				csvlist.append("Maximum")
				writer.writerow(csvlist)

			csvlist = []
			csvlist.append(datetime.datetime.now().isoformat()) # timestamp
			csvlist.append(userResult.averageTemp()) # average estimated body temp
			csvlist.append(userResult.estimated)     # array of estimated temp
			csvlist.append(userResult.thermista)     # array of thermist temp
			csvlist.append(userResult.distance)      # array of distance
			csvlist.append(userResult.raw)           # array of raw(surface) temp by sensor

			writer.writerow(csvlist)
			f.close()

		except:
			oled.logger("FILE ERROR")
			oled.logger(userResult.name + ".csv")



# run it
tl = thermalLogger()
tl.main()