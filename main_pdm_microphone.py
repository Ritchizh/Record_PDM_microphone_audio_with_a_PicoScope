#!/usr/bin/env python
# -*-coding:utf-8 -*-
'''
@File    :   main_pdm_microphone.py
@Time    :   2025/08/25 22:26:21
@Author  :   Margarita Chizh
@Contact :   margarita.chizh@hm.edu
'''


import os
PROJECT_DIR = "C:/Users/chizh/Desktop/Workspace/Python/Picoscope/"
os.chdir(PROJECT_DIR) ## Make Project directory the current working directory to access files easily

import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from time import sleep

from scipy.signal import butter, sosfiltfilt, sosfilt
import sounddevice as sd

from my_picoscope import MyScope



def save_npy(save_folder, filename_prefix, data):
    """Save data numpy array into a .npy file."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") # for unique filename
    filename = save_folder +'/'+ filename_prefix + str(timestamp) + ".npy"
    np.save(filename, data)
    print("\nData saved to a .npy file.\n")


SAVE_DATA = True
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True) # Create the folder

DVDD_V = 1.8 # Power voltage [V]
CLK_FREQ = 3.072e6 # CLK frequency [Hz]
DECIM_FACTOR = 64  # Decimation factor for PDM (from CLK_freq to audio_freq of 48 kHz)

##===============================================##
##================   PICOSCOPE:  ================##
##===============================================##


config_pico = {
    'names': ('PS3000A_DIGITAL_PORT0', 'PS3000A_DIGITAL_PORT1'),
    'enabled': (1, 1),
    'logic_level_V': (DVDD_V*0.5, DVDD_V*0.5),
    'dis_analog': True, # disables all analog channels (influences possible timebases),
    'fs': 25e6,
    'len_s': 2 # Record duration [seconds]
    }


##===========  Reading and displaying digital data:  ============##

scope = MyScope()

scope.setup_digital(config_pico)
scope.setup_timebase(config_pico)

print("\nPrepare for recording...\n")
sleep(2)
print("Go!")

data = scope.get_data_digital()


# # Call this once in the very end to release the resource:
# scope.close()


##=================  Save data:  =================##
if SAVE_DATA == True:
    save_npy(save_folder=RESULTS_DIR, filename_prefix="raw_", data=data)
##================================================##


##=================  Parse data:  =================##

# ##----------------##
# ## Import from file:
# saved_file = "C:/Users/chizh/Desktop/Workspace/Python/Picoscope/results/raw_data_2025-07-29_18-07-24.npy"
# data = np.load(saved_file)
# ##----------------##

# Physical pins to which device is connected:
CLK_ID = 0
DAT_ID = 1
clk = data[CLK_ID]
dat = data[DAT_ID]

# Differentiate CLK to grab data at falling edge:
pos_pul_id = np.diff(clk, append=clk[-1])
idx = np.where(pos_pul_id == 1)[0]

sig = dat[idx] # PDM signal


##=================  Plot:  =================##
n_plot=100
plt.figure(figsize=(8, 4), constrained_layout=True)
plt.plot(clk[:n_plot], label='CLK')
plt.plot(dat[:n_plot], label='DATA')
# plt.plot(idx, dat[idx], marker='x', linestyle='none', label='pos_pul')
plt.grid()
plt.legend(loc='upper right')
plt.show()
##================================================##

    

##=================  Lowpass filtering and decimation:  =================##

fcut = 10e3      # Cutoff frequency (Hz)
order = 8        # Filter order
fs = CLK_FREQ    # Original signal sampling frequency
fs_dec = fs/DECIM_FACTOR # final audio signal frequency

if fs_dec != 48e3:
    raise ValueError(f"Check decimation factor. Value for audio freq: {fs_dec}. Expected 48000.0.")

sos = butter(N=order, Wn=fcut, btype='lowpass', fs=fs, output='sos')
# sig_lp = sosfiltfilt(sos, sig)  # zero-phase filtering
sig_lp = sosfilt(sos, sig)

wav = sig_lp[::DECIM_FACTOR] # decimation


##=================  Play sound:  =================##

# ##----------------##
# ## Import from file:
# saved_file = "C:/Users/chizh/Desktop/Workspace/Python/Picoscope/results/proc_2025-08-20_10-12-28.npy"
# wav = np.load(saved_file)
# ##----------------##


wav = wav[500:] # cut the transition region of the filter
wav -= np.mean(wav)

sd.play(20*wav, fs_dec) # Here volume can be adjusted

t = np.arange(len(wav)) / fs_dec # Time array for plotting

plt.figure(figsize=(10, 4))
plt.plot(t, wav)
plt.xlabel("Time [s]")
plt.ylabel("Amplitude")
plt.title("Audio Signal")
plt.grid(True)
plt.show()

##=================  Save data:  =================##
if SAVE_DATA == True:
    save_npy(save_folder=RESULTS_DIR, filename_prefix="proc_", data=wav)
##================================================##