import json
import os
import sys

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf
import cv2

img=pf.getGui(4,2)
cv2.imwrite("gui.png",img)