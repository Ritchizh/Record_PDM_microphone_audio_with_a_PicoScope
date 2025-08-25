# Record_PDM_microphone_audio_with_a_PicoScope
This project captures and decodes audio from a PDM digital microphone using a PicoScope 3406D MSO. Python with PicoSDK acquires the PDM signals, decodes them via low-pass filtering and decimation to 48 kHz, and plays the reconstructed audio.

# Introduction:
This project implements the acquisition and decoding of audio from a digital Pulse Density Modulation (PDM) microphone. PDM microphones encode analog sound into a 1-bit digital bitstream using delta–sigma modulation, where the density of logical ones represents the instantaneous amplitude of the signal. To reconstruct the audio waveform, the PDM signal must undergo low-pass filtering to suppress high-frequency quantization noise, followed by decimation to obtain a conventional audio sampling rate of 48 kHz.

# Hardware
The microphone used was the TDK Invensense T5838. Its operating requirements are:
•	Power supply: +1.8 V DC
•	Clock input: 3.072 MHz square wave, 50% duty cycle, 1.8 V peak-to-peak with 0.9 V DC offset (at lower clock frequency the microphone is in low-power mode)
•	Audio output: digital bitstream on the DATA pin
To capture and decode the PDM data, a PicoScope 3406D MSO oscilloscope was employed. The setup required both the clock and data signals to be recorded simultaneously:
•	Clock (CLK): connected to digital input D0
•	Data (DATA): connected to digital input D1
A signal splitter was attached to an arbitrary waveform generator to distribute the same clock source to both the microphone and the oscilloscope, ensuring precise synchronization.
<img width="600" alt="Setup_Picoscope" src="https://github.com/user-attachments/assets/e10966df-4bf1-4d79-afbb-794c4fdec925" />


# Software
Signal acquisition and processing were performed in Python using the official PicoSDK wrapper (picosdk.ps3000a), available from the https://github.com/picotech/picosdk-python-wrappers/tree/master  PicoTech GitHub repository. To install, the repository is downloaded as a ZIP archive, and setup.py is executed according to the official instructions.
The main script implemented the following sequence:
1.	Connection and configuration of the PicoScope to capture PDM signal over a specified recording duration in seconds.
2.	Decoding of the PDM signal by applying digital low-pass filtering and subsequent decimation to 48 kHz audio sampling rate.
<img width="600"  alt="CLK and DATA" src="https://github.com/user-attachments/assets/15c5c07a-1f4d-4ae4-9fc7-119d8f957c58" />

3.	Playback of the reconstructed audio through the user computer’s speakers.
<img width="600"  alt="audio plot" src="https://github.com/user-attachments/assets/dcf52813-9972-4f20-8b61-8532db03547b" />

