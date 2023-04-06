import threading
import cv2 as cv  # opencv-python
import csv
import time
from datetime import datetime
import yagmail
import os


class EmailNotification:
    """ A class which sends an email with a picture.
        Attributes:
            sender_email_account - String with sender's email address
            sender_email_password - String with sender's password for email address
            recipient_email_account - String with recipient's email address
            pi_email_account - Initialise connection with SMTP server
    """

    def __init__(self, sender_email_account, sender_email_password, recipient_email_account):
        """ Initialise the class """
        self.sender_email_account = sender_email_account
        self.sender_email_password = sender_email_password
        self.recipient_email_account = recipient_email_account
        self.pi_email_account = yagmail.SMTP(self.sender_email_account, self.sender_email_password)
        print("Sender and Recipient Email Details Setup")

    def send_email_with_attachment(self, camera, date_and_time):
        """ Sends an email with an attachment from the sender email address to the recipient email address """
        self.pi_email_account.send(to=self.recipient_email_account, subject=f"Motion Detected by Camera {camera}!",
                                   contents="Motion has been detected. Please look at the attached image.",
                                   attachments=f"./motion_detection_pictures/motion_picture_{date_and_time}.jpg")
        print("Email Sent")


class VideoStream:
    """ A class which displays a video stream from an IP camera via an RTSP URL, and detects motion within the stream.
            Attributes:
                scale - The size the video stream will be reduced or increased by for processing
                ip_camera_url - The RTSP URL of the IP camera
                capture - Open the IP video stream for video capturing
                resolution_width - The resolution width of the video stream from the IP camera
                resolution_height - The resolution height of the video stream from the IP camera
                frame_rate - The frame rate (fps) of the video stream from the IP camera
                _is_frame - Returns True or False depending on if a frame is present
                frame - Captured frame from the video stream
                previous_video_frame - Previously captured frame from the video stream
                current_video_frame - Currently captured frame from the video stream
                motion_detected - A flag that will return True or False if motion was detected
                decreased_resolution_frame - A smaller resolution of captured frame
                grey_scale_frame - A grey scale version of captured frame
                absolute_difference - The absolute difference between the current and previous captured frames
                absolute_difference_threshold - The threshold at which the difference (movement) appears white in colour
                contour - Contours are a continuous area having same colour. Contours of binary imaged stored
                x - origin on x-axis for the motion detection rectangle
                y - origin on y-axis for the motion detection rectangle
                w - The width in x-axis to add to the motion detection rectangle
                h - The height in y-axis to add to the motion detection rectangle
        """

    def __init__(self, scale, ip_camera_url, email, cam_id, start_email_cooldown, email_cooldown):
        """ Initialise the class """
        self.scale = scale
        self.ip_camera_url = ip_camera_url
        self.capture = cv.VideoCapture(self.ip_camera_url, cv.CAP_FFMPEG)  # API Preference - CAP_FFMPEG
        self.resolution_width = int(self.capture.get(cv.CAP_PROP_FRAME_WIDTH))
        self.resolution_height = int(self.capture.get(cv.CAP_PROP_FRAME_HEIGHT))
        self.frame_rate = int(self.capture.get(cv.CAP_PROP_FPS))
        self._is_frame, self.frame = self.capture.read()
        self.previous_video_frame = cv.resize(self.frame, (self.resolution_width//self.scale,
                                                           self.resolution_height//self.scale))
        self.previous_video_frame = cv.flip(self.previous_video_frame, -1)
        self.previous_video_frame = cv.cvtColor(self.previous_video_frame, cv.COLOR_BGR2GRAY)
        self.current_video_frame = None
        self.motion_detected = False
        self.decreased_resolution_frame = None
        self.grey_scale_frame = None
        self.absolute_difference = None
        self.absolute_difference_threshold = None
        self.contour = None
        self.x = None
        self.y = None
        self.w = None
        self.h = None
        self.video = None
        self.string_date_time = ""
        self.email = email
        self.id = cam_id
        self.start_email_cooldown = start_email_cooldown
        self.email_cooldown = email_cooldown
        self.cam_thread = None
        self.camera_thread_run = True
        print("Video Stream Details Setup")

    def update_frame(self):
        """ Update the frame and flip the frame to an upright and mirrored position """
        # Get frame from IP camera
        _, cap = self.capture.read()

        # Resize the frame without taking into account the original video file size
        try:
            cap = cv.resize(cap, (self.resolution_width, self.resolution_height))

            # Flip the frame: 0 - around x-axis, 1 - around y-axis, and -1 - around both axes
            self.frame = cv.flip(cap, -1)
        except Exception as error:
            print(error)
            self.restart()

    def get_previous_video_file(self):
        """ Return the previous frame, then save the current frame as the previous frame """
        # Set the current_video_file with the current video feed
        self.current_video_frame = self.grey_scale_frame

        # Store the previous_video_file into a variable so that it can be returned
        temp = self.previous_video_frame

        # Update previous_video_file with the current_video_file
        self.previous_video_frame = self.current_video_frame
        return temp

    def detect_motion(self, area_blur, absolute_diff_threshold, colour, area_of_motion, colour_box, thickness_box):
        """ Detection motion within the video stream of the IP cameras """

        # Decrease resolution of video file for motion detection processing
        try:
            self.decreased_resolution_frame = cv.resize(self.frame, (self.resolution_width // self.scale,
                                                                     self.resolution_height // self.scale))

            # Grey scale the frame
            self.grey_scale_frame = cv.cvtColor(self.decreased_resolution_frame, cv.COLOR_BGR2GRAY)
            self.grey_scale_frame = cv.GaussianBlur(self.grey_scale_frame, area_blur, 0)

            # Find the absolute difference between the current and previous frames
            self.absolute_difference = cv.absdiff(self.get_previous_video_file(), self.grey_scale_frame)

            # Create a threshold so that moving objects appear
            _, self.absolute_difference_threshold = cv.threshold(self.absolute_difference, absolute_diff_threshold,
                                                                 colour, cv.THRESH_BINARY)

            # Find the area of the movement
            self.contour, _hierarchy = cv.findContours(self.absolute_difference_threshold, cv.RETR_EXTERNAL,
                                                       cv.CHAIN_APPROX_SIMPLE)
            if len(self.contour) != 0:
                if cv.contourArea(max(self.contour, key=cv.contourArea)) > area_of_motion:
                    # Create rectangle around the largest area of movement
                    self.x, self.y, self.w, self.h = cv.boundingRect(max(self.contour, key=cv.contourArea))

                    # The rectangle needs scaled up to match the video stream
                    cv.rectangle(self.frame, (self.x * self.scale, self.y * self.scale),
                                 (self.x * self.scale + self.w * self.scale, self.y * self.scale + self.h * self.scale),
                                 colour_box, thickness_box)

                    self.motion_detected = True
        except Exception as error:
            print(error)
            self.restart()

    def restart(self):
        """ Release the RTSP and Open the RTSP so the delay from the email does not cause an error  """
        self.capture.release()
        self.capture.open(self.ip_camera_url, cv.CAP_FFMPEG)  # API Preference - CAP_FFMPEG, CAP_IMAGES, CAP_DSHOW

    def deactivate_motion_flag(self):
        """ Set the motion flag to false """
        self.motion_detected = False

    def image_and_record_video(self, recording_time):
        """ Record a video clip of the captured frames """
        # Create string of current date and time
        self.string_date_time = datetime.now().strftime("%Y-%m-%dT%H-%M-%SZ")

        # Save frame with motion as JPEG
        print("Saving Attachment Image for Email")
        cv.imwrite(f"./motion_detection_pictures/motion_picture_{self.string_date_time}.jpg", self.frame)
        print("Saved Attachment Image for Email")

        # Record mp4 video at the IP camera fps for the desired recording time
        print(f"Recording {recording_time} s at {self.frame_rate} fps Video Clip")
        self.video = cv.VideoWriter(f"./motion_detection_videos/motion_video_{self.string_date_time}.mp4",
                                    cv.VideoWriter_fourcc(*'mp4v'), self.frame_rate,
                                    (self.resolution_width, self.resolution_height))

        for _ in range(recording_time*self.frame_rate):
            self.video.write(self.frame)
            self.update_frame()

        print(f"Camera {self.id} Video Clip Recorded")

    def display_video_stream(self):
        """ Display the current frame """
        try:
            cv.imshow(f"IP Camera {self.id}", self.frame)
        except Exception as error:
            print(error)
            self.restart()

    def start_camera_thread(self):
        self.cam_thread = threading.Thread(target=self.camera_thread)
        self.cam_thread.start()

    def stop_camera_thread(self):
        self.camera_thread_run = False

    def camera_thread(self):
        if not self.capture.isOpened():
            print(f'Cannot open RTSP stream for {self.id}')
            exit(-1)

        # start the email timer before while loop begins
        email_timeout = time.time() + self.start_email_cooldown

        while self.camera_thread_run:
            self.deactivate_motion_flag()
            self.update_frame()
            self.detect_motion(GAUSSIAN_BLUR_KSIZE, ABSOLUTE_DIFFERENCE_THRESHOLD, WHITE, MOTION_MOVEMENT_AREA, GREEN,
                               THICKNESS)

            if self.motion_detected and email_timeout - time.time() <= 0:
                self.image_and_record_video(RECORD_TIME)
                self.email.send_email_with_attachment(self.id, self.string_date_time)

                # Reset camera email notification cooldown
                email_timeout = time.time() + self.email_cooldown

                print(f"Camera {self.id} Email Sent")

        print(f"Camera {self.id} Thread Closed")


# Constants
SCALE = 2
GAUSSIAN_BLUR_KSIZE = (25, 25)
ABSOLUTE_DIFFERENCE_THRESHOLD = 5
WHITE = 255
MOTION_MOVEMENT_AREA = 1000
GREEN = (0, 255, 0) # Motion Detection Box line colour
THICKNESS = 2 # Motion Detection Box line width
START_EMAIL_COOLDOWN = 5
EMAIL_COOLDOWN = 10 # Email accounts have daily limits, change this number to suit your email account limit
RECORD_TIME = 5 # Recording time when motion is detected

if __name__ == '__main__':
    # Check Version of OpenCv Python library
    print(cv.__version__)

    # Acquire email password for sender account and the RTSP URLs of the IP cameras
    with open("email_password_and_rtsp_urls.csv") as csv_file:
        text = csv.reader(csv_file, delimiter='\t')
        for t in text:
            # Acquire the resolution width and height
            email_password = t[0]
            camera1_rtsp = t[1]
            camera2_rtsp = t[2]
        print("Email Password and RTSP URLs Successfully Acquired")

    # Set environment for RTSP URLs
    os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'  # Put ;udp or ;tcp depending on IP camera

    # Create IP Camera 1 objects
    camera1_notification = EmailNotification("insert_sending_email_account_here@gmail.com", email_password,
                                             "insert_receiveing_email_account_here@outlook.com")
    camera1_stream = VideoStream(SCALE, camera1_rtsp, camera1_notification, 1, START_EMAIL_COOLDOWN, EMAIL_COOLDOWN)
    camera2_notification = EmailNotification("insert_sending_email_account_here@gmail.com", email_password,
                                             "insert_receiveing_email_account_here@outlook.com")
    camera2_stream = VideoStream(SCALE, camera2_rtsp, camera2_notification, 2, START_EMAIL_COOLDOWN, EMAIL_COOLDOWN)
    camera1_stream.start_camera_thread()
    camera2_stream.start_camera_thread()

    while True:
        camera1_stream.display_video_stream()
        camera2_stream.display_video_stream()

        # If the letter 'q' on the keyboard is pressed, then all actions will stop
        if cv.waitKey(1) == ord('q'):
            camera1_stream.capture.release()
            camera1_stream.video.release()
            camera1_stream.stop_camera_thread()

            camera2_stream.capture.release()
            camera2_stream.video.release()
            camera2_stream.stop_camera_thread()

            cv.destroyAllWindows()
            break
