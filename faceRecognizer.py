#! /usr/bin/python

# import the necessary packages
from imutils.video import VideoStream
import face_recognition
import imutils
import pickle
import cv2

class detectedPerson:
    def __init__(self, name, x, y):
        self.name = name
        self.x = x
        self.y = y

class recognizer(object):
	def __init__(self):
		print("face recognizer initialize")

	def setup(self):
		#Initialize 'currentname' to trigger only when a new person is identified.
		self.currentname = "unknown"
		#Determine faces from encodings.pickle file model created from train_model.py
		self.encodingsP = "encodings.pickle"
		#use this xml file
		self.cascade = "haarcascade_frontalface_default.xml"
		# load the known faces and embeddings along with OpenCV's Haar
		# cascade for face detection
		print("[INFO] loading encodings + face detector...")
		self.data = pickle.loads(open(self.encodingsP, "rb").read())
		self.detector = cv2.CascadeClassifier(self.cascade)

		# initialize the video stream and allow the camera sensor to warm up
		print("[INFO] starting video stream...")
		self.vs = VideoStream(src=0).start()
		self.recognizedPerson = None

	def lookout(self):
		# grab the frame from the threaded video stream and resize it
		# to 500px (to speedup processing)
		frame = self.vs.read()
		frame = imutils.resize(frame, width=500)
		
		# convert the input frame from (1) BGR to grayscale (for face
		# detection) and (2) from BGR to RGB (for face recognition)
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

		# detect faces in the grayscale frame
		rects = self.detector.detectMultiScale(gray, scaleFactor=1.1, 
			minNeighbors=5, minSize=(30, 30),
			flags=cv2.CASCADE_SCALE_IMAGE)
		
		if(len(rects) > 1):
			# when detect 1+ faces, skip following
			return None

		facepos = 0
		for (x, y, w, h) in rects:
			facepos = x


		# OpenCV returns bounding box coordinates in (x, y, w, h) order
		# but we need them in (top, right, bottom, left) order, so we
		# need to do a bit of reordering
		boxes = [(y, x + w, y + h, x) for (x, y, w, h) in rects]
		

		# compute the facial embeddings for each face bounding box
		encodings = face_recognition.face_encodings(rgb, boxes)
		names = []
		


		# loop over the facial embeddings
		for encoding in encodings:
			# attempt to match each face in the input image to our known
			# encodings
			matches = face_recognition.compare_faces(self.data["encodings"], encoding)
			name = "Unknown" #if face is not recognized, then print Unknown

			# check to see if we have found a match
			if True in matches:
				# find the indexes of all matched faces then initialize a
				# dictionary to count the total number of times each face
				# was matched
				matchedIdxs = [i for (i, b) in enumerate(matches) if b]
				counts = {}

				# loop over the matched indexes and maintain a count for
				# each recognized face face
				for i in matchedIdxs:
					name = self.data["names"][i]
					counts[name] = counts.get(name, 0) + 1

				# determine the recognized face with the largest number
				# of votes (note: in the event of an unlikely tie Python
				# will select first entry in the dictionary)
				name = max(counts, key=counts.get)
				
				#If someone in your dataset is identified, print their name on the screen
				if self.currentname != name:
					self.currentname = name
					print(self.currentname + " detected")
					#return detectedPerson(self.currentname, rects[0][0], rects[0][1])
			# update the list of names
			names.append(name)

		if(len(encodings) > 0):
			# fade detected but not matched with registered user.
			if(names[0]=="Unknown"):
				print("Unknown face detected.")
				return detectedPerson("Unknown", 0, 0)
			
			return detectedPerson(names[0], rects[0][0], rects[0][1])
		# loop over the recognized faces
		# for ((top, right, bottom, left), name) in zip(boxes, names):
		# 	# draw the predicted face name on the image - color is in BGR
		# 	cv2.rectangle(frame, (left, top), (right, bottom),
		# 		(0, 255, 225), 2)
		# 	y = top - 15 if top - 15 > 15 else top + 15
		# 	cv2.putText(frame, name, (left, y), cv2.FONT_HERSHEY_SIMPLEX,
		# 		.8, (0, 255, 255), 2)

		return None

	def shutdown(self):
		# do a bit of cleanup
		#cv2.destroyAllWindows()
		print("shutdown video stream..")
		self.vs.stop()
		print("complete.")