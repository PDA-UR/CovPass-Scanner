# -*- coding: UTF-8 -*-

import sys
import cv2
from pytesseract import pytesseract

PYTESSERACT_LANGUAGE = 'deu'

class IdCardScanner:

    def __init__(self):
        pass

    def scan_for_id_cards(self, frame, data):

        # This script is currently optimised for german ID cards.
        if data['co'] != 'DE':
            print('Certificate not issued in germany, therefore probably no german passport')

        modified_frame = self.__prepare_frame(frame)
        variants_dict = self.__generate_variants_dict(data)

        match_found = self.__find_matches(modified_frame, variants_dict)

        print('Match found:', match_found)

    # Do some magic to improve the readability of text in the frame
    # TODO: Improve this and maybe offer multiple options
    def __prepare_frame(self, frame):
        frame_grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # TODO: Find better values and remove magic numbers
        threshold = cv2.adaptiveThreshold(frame_grey, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 199, 17)

        cv2.imshow('Adaptive Gaussian Thresh', threshold)

        return threshold

    # Perform OCR on the frame and compare the found text with the strings from the dict
    def __find_matches(self, frame, variants_dict):
        raw_text = pytesseract.image_to_string(frame, lang=PYTESSERACT_LANGUAGE)

        first_name_found = False
        last_name_found = False
        dob_found = False

        for first_name in variants_dict['first_name']:
            if first_name in raw_text:
                print('First name matches!')
                first_name_found = True
                break

        for last_name in variants_dict['last_name']:
            if last_name in raw_text:
                print('Last name matches!')
                last_name_found = True
                break

        for dob in variants_dict['dob']:
            if dob in raw_text:
                print('Date of birth matches!')
                dob_found = True
                break

        return first_name_found and last_name_found and dob_found

    # Generate a dict of strings that we expect to find in the text on the ID card
    # -> Different variants of first name, last name and date of birth
    def __generate_variants_dict(self, data):
        variants_dict = {
            'first_name': [data['gn'], data['gnt'], data['gn'][0] + data['gnt'][1:].lower(), data['gn'].upper()],
            'last_name': [data['fn'], data['fnt'], data['fn'][0] + data['fnt'][1:].lower(), data['fn'].upper()],
            'dob': self.__generate_possible_dob_variants(data['dob'])
        }

        return variants_dict

    # The date of birth (dob) can appear in different variants on passports (dd.mm.yyyy, dd.mm.yy, yymmdd, ...)
    # This method generates a list of all possible variants
    def __generate_possible_dob_variants(self, dob):

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


# EVERYTHING BELOW IS JUST FOR TESTING THE SCRIPT


def main():
    id_card_scanner = IdCardScanner()

    CAMERA = '/dev/video2'
    CAM_WIDTH, CAM_HEIGHT = 1280, 720
    TEST_DATA = {'co': 'DE', 'dob': '2000-12-01', 'fn': 'Müller', 'gn': 'Max', 'fnt': 'MUELLER', 'gnt': 'MAX'}

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
