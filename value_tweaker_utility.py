import sys
import cv2
import numpy as np

WINDOW_NAME = 'ID card scanner value tweaker utility'

CAMERA = 2
CAM_WIDTH, CAM_HEIGHT = 1280, 720


# Based on: https://docs.opencv.org/3.4/da/d97/tutorial_threshold_inRange.html
class ValueTweakerUtility:
    """ ValueTweakerUtility
    """

    max_value_name = 'Max value'
    blocksize_name = 'BlockSize'
    C_name = 'C'

    low_blocksize = 3
    high_blocksize = 255

    low_C = 0
    high_C = 30

    max_value = 255
    blocksize = 199
    C = 17

    def __init__(self):
        self.cap = cv2.VideoCapture(CAMERA)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)

        cv2.namedWindow(WINDOW_NAME)

        cv2.createTrackbar(self.max_value_name, WINDOW_NAME, self.max_value, self.max_value, self.on_max_value_trackbar)
        cv2.createTrackbar(self.blocksize_name, WINDOW_NAME, self.low_blocksize, self.high_blocksize, self.on_blocksize_trackbar)
        cv2.createTrackbar(self.C_name, WINDOW_NAME, self.low_C, self.high_C, self.on_C_trackbar)

        cv2.setTrackbarPos(self.blocksize_name, WINDOW_NAME, self.blocksize)
        cv2.setTrackbarPos(self.C_name, WINDOW_NAME, self.C)

        self.loop()

    def loop(self):
        while True:
            ret, frame = self.cap.read()

            # Only continue if needed frames are available
            if frame is not None:

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                threshold = cv2.adaptiveThreshold(frame, self.max_value, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, self.blocksize, self.C)

                kernel = np.ones((2, 2), np.uint8)
                threshold = cv2.erode(threshold, kernel)

                # cv2.imshow(WINDOW_NAME, combined_frames)
                cv2.imshow(WINDOW_NAME, threshold)

                print('')
                print('Max Value:', self.max_value, 'Blocksize:', self.blocksize, 'C:', self.C)

            key = cv2.waitKey(1)
            # Press esc or 'q' to close the image window
            if key & 0xFF == ord('q') or key == 27:
                cv2.destroyAllWindows()
                break

    def on_max_value_trackbar(self, val):
        self.max_value = val
        cv2.setTrackbarPos(self.max_value_name, WINDOW_NAME, self.max_value)

    def on_blocksize_trackbar(self, val):
        if val % 2 != 1:
            val = val - 1
        if val < 3:
            val = 3
        self.blocksize = val
        cv2.setTrackbarPos(self.blocksize_name, WINDOW_NAME, self.blocksize)

    def on_C_trackbar(self, val):
        self.C = val
        cv2.setTrackbarPos(self.C_name, WINDOW_NAME, self.C)


def main():
    ValueTweakerUtility()
    sys.exit()


if __name__ == '__main__':
    main()
