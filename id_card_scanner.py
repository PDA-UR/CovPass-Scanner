# -*- coding: UTF-8 -*-
import sys
import time

import cv2
import numpy as np
from pytesseract import pytesseract
import imutils

PYTESSERACT_LANGUAGE = 'deu'

# Check if at least X% of the center of the image are edges
# (Many edges -> Probably text -> High possibility that an ID card is present)
MIN_NUM_EDGES_PERCENTAGE = 1.5

USE_MOVEMENT_DETECTOR = True
USE_LEVENSHTEIN = True


class IdCardScanner:

    last_frame = None
    last_movement_timestamp = 0

    def __init__(self):
        pass

    def scan_for_id_cards(self, frame, data):

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_center = self.__extract_center_of_frame(frame)

        if USE_MOVEMENT_DETECTOR:
            movement = self.__detect_movement(frame_center, 40, 300)

            now = time.time_ns() // 1_000_000
            if movement:
                print('Movement detected')
                self.last_movement_timestamp = now
                return False

            if now - self.last_movement_timestamp < 400:
                return False

        edges_present = self.__detect_edges(frame_center)

        if not edges_present:
            return False

        variants_dict = self.__generate_variants_dict(data)

        # This script is currently optimised for german ID cards.
        if data['co'][1] != 'DE':
            print('Certificate not issued in Germany, therefore probably also no german passport')

        modified_frame = self.__prepare_frame(frame)

        match_found = self.__find_matches(modified_frame, variants_dict)

        print('Match found:', match_found)
        return match_found

    @staticmethod
    def __detect_edges(frame):
        blurred = cv2.GaussianBlur(frame, (3, 3), 0)
        canny = cv2.Canny(blurred, 50, 130)
        # cv2.imshow("Canny Edge Map", canny)

        edges_percentage = cv2.countNonZero(canny) / (frame.shape[0] * frame.shape[1]) * 100

        print('Edges Percentage: {}%'.format(edges_percentage))

        if edges_percentage > MIN_NUM_EDGES_PERCENTAGE:
            return True
        return False

    # Do some magic to improve the readability of text in the frame
    # TODO: Improve this and maybe offer multiple options
    @staticmethod
    def __prepare_frame(frame):
        # TODO: Find better values and remove magic numbers
        threshold = cv2.adaptiveThreshold(frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 16)

        # Erode frame
        kernel = np.ones((2, 2), np.uint8)
        threshold = cv2.erode(threshold, kernel)

        # cv2.imshow('Adaptive Gaussian Thresh', threshold)
        return threshold

    @staticmethod
    def __get_text_from_frame(frame):
        # Windows Workaround
        # pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

        raw_text = pytesseract.image_to_string(frame, lang=PYTESSERACT_LANGUAGE)
        raw_text = ' '.join(raw_text.split())  # Remove new lines and double spaces
        print(raw_text)
        return raw_text

    # Perform OCR on the frame and compare the found text with the strings from the dict
    def __find_matches(self, frame, variants_dict):
        raw_text = self.__get_text_from_frame(frame)

        detected_word_list = raw_text.split(' ')

        first_name_found = False
        last_name_found = False
        dob_found = False

        for first_name in variants_dict['first_name']:
            if first_name in raw_text:
                first_name_found = True
                break

        if not first_name_found and USE_LEVENSHTEIN:
            first_name_found = self.match_witch_levenshtein(variants_dict['first_name'], detected_word_list)

        for last_name in variants_dict['last_name']:
            if last_name in raw_text:
                last_name_found = True
                break

        if not last_name_found and USE_LEVENSHTEIN:
            last_name_found = self.match_witch_levenshtein(variants_dict['last_name'], detected_word_list)

        for dob in variants_dict['dob']:
            if dob in raw_text:
                dob_found = True
                break

        if not dob_found and USE_LEVENSHTEIN:
            dob_found = self.match_witch_levenshtein(variants_dict['dob'], detected_word_list)

        return first_name_found and last_name_found and dob_found

    def match_witch_levenshtein(self, variants, detected_word_list):
        for variant in variants:
            for word in detected_word_list:
                if len(word) == len(variant):
                    word_distance = self.levenshtein_distance(word, variant)
                    # If just one char is different
                    if word_distance == 1:
                        print('{} vs. {} -> Just one char is different'.format(variant, word, word_distance))
                        return True
        return False

    # Based on: https://blog.paperspace.com/implementing-levenshtein-distance-word-autocomplete-autocorrect/
    def levenshtein_distance(self, token1, token2):
        distances = np.zeros((len(token1) + 1, len(token2) + 1))

        for t1 in range(len(token1) + 1):
            distances[t1][0] = t1

        for t2 in range(len(token2) + 1):
            distances[0][t2] = t2

        for t1 in range(1, len(token1) + 1):
            for t2 in range(1, len(token2) + 1):
                if token1[t1 - 1] == token2[t2 - 1]:
                    distances[t1][t2] = distances[t1 - 1][t2 - 1]
                else:
                    a = distances[t1][t2 - 1]
                    b = distances[t1 - 1][t2]
                    c = distances[t1 - 1][t2 - 1]

                    if a <= b and a <= c:
                        distances[t1][t2] = a + 1
                    elif b <= a and b <= c:
                        distances[t1][t2] = b + 1
                    else:
                        distances[t1][t2] = c + 1

        return distances[len(token1)][len(token2)]

    # Generate a dict of strings that we expect to find in the text on the ID card
    # -> Different variants of first name, last name and date of birth
    def __generate_variants_dict(self, data):
        variants_dict = {
            'first_name': [data['gn'][1], data['gnt'][1], data['gn'][1][0] + data['gnt'][1][1:].lower(), data['gn'][1].upper()],
            'last_name': [data['fn'][1], data['fnt'][1], data['fn'][1][0] + data['fnt'][1][1:].lower(), data['fn'][1].upper()],
            'dob': self.__generate_possible_dob_variants(data['dob'][1])
        }

        return variants_dict

    # The date of birth (dob) can appear in different variants on passports (dd.mm.yyyy, dd.mm.yy, yymmdd, ...)
    # This method generates a list of all possible variants
    @staticmethod
    def __generate_possible_dob_variants(dob):

        dob_variants = [dob]

        parts = dob.split('-')
        yyyy = parts[0]
        yy = parts[0][2:]
        mm = parts[1]
        dd = parts[2]

        dob_variants.append('{}.{}.{}'.format(dd, mm, yyyy))
        dob_variants.append('{}.{}.{}'.format(dd, mm, yy))
        dob_variants.append('{}{}{}'.format(yy, mm, dd))

        return dob_variants

    @staticmethod
    def __extract_center_of_frame(frame):
        width = frame.shape[1]
        height = frame.shape[0]
        center_x = int(width/2)
        center_y = int(height/2)
        size = int((0.5 * height) / 2)
        frame = frame[center_y - size:center_y+size, center_x - size:center_x+size]

        # cv2.imshow('center', frame)

        return frame

    # Check if movement was detected within the frame
    # Based on https://www.pyimagesearch.com/2015/05/25/basic-motion-detection-and-tracking-with-python-and-opencv/
    def __detect_movement(self, frame, movement_threshold, min_area_for_movement_px):
        movement = False

        if self.last_frame is None:
            self.last_frame = frame
            return True

        try:
            # Compute the absolute difference between the current frame and first frame
            frame_delta = cv2.absdiff(self.last_frame, frame)

            # Now threshold the difference image
            thresh = cv2.threshold(frame_delta, movement_threshold, 255, cv2.THRESH_BINARY)[1]

            # dilate the thresholded image to fill in holes, then find contours on thresholded image
            # TODO: Check if this is still needed
            thresh = cv2.dilate(thresh, None, iterations=2)

            # Find contours in the thresholded image (Those are areas where movement has been detected)
            # RETR_EXTERNAL: Return only outer contours. All child contours are left behind
            # CV_CHAIN_APPROX_SIMPLE: Contour approximation method: compresses horizontal, vertical, and diagonal
            #                         segments and leaves only their end points
            contours = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = imutils.grab_contours(contours)

            # Loop over the contours
            for contour in contours:

                # If the contour is too small, ignore it.
                # Otherwise we accept it as an area where movement has been detected
                if cv2.contourArea(contour) >= min_area_for_movement_px:
                    movement = True
                    break

        except Exception as e:
            print('Error on detecting movement:', e)

        self.last_frame = frame

        return movement


# EVERYTHING BELOW IS JUST FOR TESTING THE SCRIPT

def main():
    id_card_scanner = IdCardScanner()

    CAMERA = 2
    CAM_WIDTH, CAM_HEIGHT = 1280, 720
    TEST_DATA = {}  # INSERT HERE

    cap = cv2.VideoCapture(CAMERA)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
    while True:
        ret, frame = cap.read()

        if frame is not None:
            cv2.imshow('raw frame', frame)
            id_card_scanner.scan_for_id_cards(frame, TEST_DATA)

        key = cv2.waitKey(1)

        # Press esc or 'q' to close the image window
        if key & 0xFF == ord('q') or key == 27:
            cv2.destroyAllWindows()
            sys.exit(0)


if __name__ == '__main__':
    main()
