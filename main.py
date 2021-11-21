# -*- coding: UTF-8 -*-

import argparse
import sys
import time

import cv2
import numpy as np
import PIL.Image
from PIL.ImageOps import pad
from PIL import Image

from pygame import mixer

from covpass_scanner import CovpassScanner
from id_card_scanner import IdCardScanner

DEFAULT_CERTIFICATE_DB_JSON = 'certs/Digital_Green_Certificate_Signing_Keys.json'

CAMERA_ID = 7
CAM_WIDTH, CAM_HEIGHT = 640, 480

TIME_WAIT_AFTER_CERTIFICATE_FOUND_SEC = 3
TIME_WAIT_FOR_ID_CARD_SEC = 30

TIME_SHOW_INVALID_CERTIFICATE_MESSAGE_SEC = 10
TIME_SHOW_SUCCESSFUL_VERIFICATION_MESSAGE_SEC = 5

BORDER_PERCENTAGE = 0.2

class Main:

    active_certificate_data = None
    last_certificate_found_timestamp = 0
    id_card_matches_certificate = False
    invalid_certificate_found = False

    def __init__(self):
        # parser = argparse.ArgumentParser(description='EU COVID Vaccination Passport Verifier')
        # parser.add_argument('--image-file', metavar="IMAGE-FILE",
        #                     help='Image to read QR-code from')
        # parser.add_argument('--raw-string', metavar="RAW-STRING",
        #                     help='Contents of the QR-code as string')
        # parser.add_argument('image_file_positional', metavar="IMAGE-FILE", nargs="?",
        #                     help='Image to read QR-code from')
        # parser.add_argument('--certificate-db-json-file', default=DEFAULT_CERTIFICATE_DB_JSON,
        #                     help="Default: {0}".format(DEFAULT_CERTIFICATE_DB_JSON))
        # parser.add_argument('--camera', metavar="CAMERA-FILE",
        #                     help='camera path')
        #
        # args = parser.parse_args()
        #
        # covid_cert_data = None
        # image_file = None
        # if args.image_file_positional:
        #     image_file = args.image_file_positional
        # elif args.image_file:
        #     image_file = args.image_file
        #
        # if image_file:
        #     data = pyzbar.pyzbar.decode(PIL.Image.open(image_file))
        #     covid_cert_data = data[0].data.decode()
        # elif args.raw_string:
        #     covid_cert_data = args.raw_string
        # elif args.camera:
        #     run_interactive(args.camera, args.certificate_db_json_file)
        #     sys.exit(0)
        # else:
        #     log.error("Input parameters: Need either --camera, --image-file or --raw-string QR-code content.")
        #     exit(2)
        #
        # # Got the data, output
        # log.debug("Cert data: '{0}'".format(covid_cert_data))
        # output_covid_cert_data(covid_cert_data, args.certificate_db_json_file)

        self.capture = cv2.VideoCapture(CAMERA_ID)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)

        self.covpass_scanner = CovpassScanner()
        self.id_card_scanner = IdCardScanner()

        # cv2.namedWindow("Camera", cv2.WND_PROP_FULLSCREEN)
        # cv2.setWindowProperty("Camera", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        self.font_title = PIL.ImageFont.truetype("fonts/Roboto-Regular.ttf", 80)
        self.font_subtitle = PIL.ImageFont.truetype("fonts/Roboto-Regular.ttf", 50)

        self.invalid_certificate_image = cv2.imread("img/failure.png")
        self.successful_verification_image = cv2.imread("img/success.png")

        self.run_interactive()

    def run_interactive(self):
        while True:
            ret, frame = self.capture.read()
            if frame is None:
                print('No frame from camera')
                continue

            now = time.time()

            # Check if a certificate is found in the frame
            found_certificate, is_valid, parsed_covid_cert_data = self.covpass_scanner.process_frame(frame)

            if found_certificate:
                already_scanned_certificate = self.active_certificate_data == parsed_covid_cert_data
                if not already_scanned_certificate:  # Only continue if it is new certificate
                    #frame[:] = (0, 255, 255)
                    #cv2.imshow("Camera", frame)

                    if is_valid:
                        self.active_certificate_data = parsed_covid_cert_data
                        self.last_certificate_found_timestamp = now

                    else:
                        self.invalid_certificate_found = True

            else:  # Only check for ID card if no certificate is found in the current frame
                if self.active_certificate_data is not None:

                    # Wait at least XX seconds after certificate has been detected in frame
                    # This should at least somewhat prevent detecting text from the certificate itself while we have no
                    # proper verification of an ID card
                    if now - self.last_certificate_found_timestamp >= TIME_WAIT_AFTER_CERTIFICATE_FOUND_SEC:
                        self.id_card_matches_certificate = self.id_card_scanner.scan_for_id_cards(frame, self.active_certificate_data)

                    # Delete saved certificate data after XX seconds
                    if now - self.last_certificate_found_timestamp > TIME_WAIT_AFTER_CERTIFICATE_FOUND_SEC + TIME_WAIT_FOR_ID_CARD_SEC:
                        self.active_certificate_data = None

            self.update_ui(frame)

            if self.invalid_certificate_found:
                self.on_invalid_certificate(frame)
                key = cv2.waitKey(TIME_SHOW_INVALID_CERTIFICATE_MESSAGE_SEC * 1000)  # sec to ms
            elif self.id_card_matches_certificate:
                self.on_successful_verification(frame)
                key = cv2.waitKey(TIME_SHOW_SUCCESSFUL_VERIFICATION_MESSAGE_SEC * 1000)  # sec to ms
            else:
                key = cv2.waitKey(1)

            # Press esc or 'q' to close the image window
            if key & 0xFF == ord('q') or key == 27:
                cv2.destroyAllWindows()
                sys.exit(0)

    def update_ui(self, frame):
        old_shape = frame.shape  # Remember to resize later after adding borders to the frame

        frame = self.add_borders_to_frame(frame)
        frame = self.add_text_to_frame(frame)
        frame = cv2.resize(frame, (old_shape[1], old_shape[0]))
        cv2.imshow("Camera", frame)

    def add_borders_to_frame(self, frame):
        # Add small black border around camera preview
        frame = cv2.copyMakeBorder(frame, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        # Add large white border
        frame = cv2.copyMakeBorder(frame,
                                   int(BORDER_PERCENTAGE * frame.shape[1]), int(BORDER_PERCENTAGE * frame.shape[1]),
                                   int(BORDER_PERCENTAGE * frame.shape[0]), int(BORDER_PERCENTAGE * frame.shape[0]),
                                   cv2.BORDER_CONSTANT, value=(255, 255, 255))

        return frame

    def add_text_to_frame(self, frame):
        title = 'Step 1: Scan COVPASS Certificate:'
        subtitle = ''

        if self.active_certificate_data is not None:
            title = 'Step 2: Scan ID card:'
            last_name = self.active_certificate_data['fn'][1]
            first_name = self.active_certificate_data['gn'][1]
            subtitle = 'Name: {} {}'.format(first_name, last_name)

        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = PIL.ImageDraw.Draw(pil_image)

        title_width = max(draw.textsize(title, font=self.font_title), draw.textsize(title, font=self.font_title))[0]
        subtitle_width = max(draw.textsize(title, font=self.font_subtitle), draw.textsize(title, font=self.font_subtitle))[0]

        # TODO: make drawing code independent of screen size
        draw.text(xy=((int((frame.shape[1] - title_width) / 2)), 10), text=title, fill=(0, 0, 0), font=self.font_title)
        draw.text(xy=((int((frame.shape[1] - subtitle_width) / 2)), frame.shape[0] - 100), text=subtitle,
                  fill=(0, 0, 0), font=self.font_subtitle)

        frame[:] = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

        return frame

    def reset(self):
        self.active_certificate_data = None
        self.last_certificate_found_timestamp = 0
        self.id_card_matches_certificate = False
        self.invalid_certificate_found = False

    def on_successful_verification(self, frame):
        mixer.init()
        mixer.music.load("sounds/complete.oga")
        mixer.music.play()

        output = cv2.resize(self.successful_verification_image, (frame.shape[1], frame.shape[0]))
        cv2.imshow('Camera', output)

        self.reset()

    def on_invalid_certificate(self, frame):
        mixer.init()
        mixer.music.load("sounds/dialog-error.oga")
        mixer.music.play()

        output = cv2.resize(self.invalid_certificate_image, (frame.shape[1], frame.shape[0]))
        cv2.imshow('Camera', output)

        self.reset()


def main():
    Main()
    sys.exit()


if __name__ == '__main__':
    main()
