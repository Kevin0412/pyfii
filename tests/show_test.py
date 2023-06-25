import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

name='output/...'
data,t0,music=pf.read_fii(name)
pf.show(data,t0,music)