import ctypes
from picosdk.ps3000a import ps3000a as ps
import numpy as np
import matplotlib.pyplot as plt

from picosdk.discover import find_all_units
# from picosdk.functions import assert_pico_ok, splitMSODataFast
from time import time, sleep



class DeviceAPIError(Exception):
    # Exception raised when a device API call fails.
    def __init__(self, message):
        super().__init__(message)



class MyScope():
    @classmethod
    def find_scopes(cls):
        scopes = find_all_units()
        for scope in scopes:
            print(scope.info)
            scope.close()
    
    def __init__(self):
        self.handle = ctypes.c_int16()
        # Opens the device/s
        status = ps.ps3000aOpenUnit(ctypes.byref(self.handle), None)
        self.check(status)
    
    def close(self):
        # Stop and close the connection to the scope (do not close when acquiring in a loop)
        status = ps.ps3000aStop(self.handle)
        self.check(status)
        status = ps.ps3000aCloseUnit(self.handle)
        self.check(status)
        # print("Destructor: device is closed")
        
    def setup_generator(self, config):
        offset_uV = int(config['offset_V'] * 1e6) # offset voltage in uV
        pk2pk_uV = int(config['pk2pk_V'] * 1e6) # peak-to-peak in uV
        start_frequency = float(config['frequency'])
        stop_frequency = float(config['frequency'])
        inc_frequency = 0.0
        dwell_time = 1.0
        sweep_type = {
            'UP': 0,
            'DOWN': 1,
            }['UP']
        operation = {
            'PS3000A_ES_OFF': 0
            }['PS3000A_ES_OFF']
        shots = 0
        sweeps = 0
        trigger_type = 0 # trigger on rising edge
        trigger_source = 0 # PS3000A_SIGGEN_NONE
        ext_trig_threshold = 1 # does not matter, because no ext. trigger
        status = ps.ps3000aSetSigGenBuiltIn(
            self.handle, offset_uV, pk2pk_uV, config['wave_type'],
            start_frequency, stop_frequency, inc_frequency, dwell_time,
            sweep_type, operation, shots, sweeps, trigger_type, trigger_source,
            ext_trig_threshold
            )
        self.check(status)
    
    def setup_analog(self, config_analog):
        '''
        Setup analog channels with a given configuration.
        '''
        for chan in ps.PICO_CHANNEL:
            status = ps.ps3000aSetChannel(
                self.handle, ps.PICO_CHANNEL[chan],
                config_analog['enabled'][chan], config_analog['coupling'][chan],
                config_analog['range'][chan], config_analog['offset'][chan])
            # check status with throwing exception in case of error
            self.check(status)
        
        # Min and Max ADC values (used for the conversion)
        max_adc = ctypes.c_int16()
        min_adc = ctypes.c_int16()
        status = ps.ps3000aMaximumValue(self.handle, ctypes.byref(max_adc))
        self.check(status)
        status = ps.ps3000aMinimumValue(self.handle, ctypes.byref(min_adc))
        self.check(status)
        self.min_adc = min_adc.value
        self.max_adc = max_adc.value
        self.config_analog = config_analog
    
    def setup_digital(self, config_digital):
        # Setup digital port
        for name, ena, lev_V in zip(
                config_digital['names'], config_digital['enabled'],
                config_digital['logic_level_V']):
            if lev_V > 5.0: lev_V = 5.0
            if lev_V < -5.0: lev_V = -5.0
            lev = round(lev_V / 5.0 * 32767)
            # print(name, ena, lev_V, lev)
            # digital_port = ps.PS3000A_DIGITAL_PORT["PS3000A_DIGITAL_PORT0"]
            status = ps.ps3000aSetDigitalPort(
                self.handle, ps.PS3000A_DIGITAL_PORT[name], ena, lev)
            self.check(status)
        
        # Disable analog ports when working with digital inputs
        if config_digital['dis_analog']:
            enabled = 0
            coupling = ps.PS3000A_COUPLING['PS3000A_DC']
            chan_range = ps.PS3000A_RANGE['PS3000A_5V']
            offset = 0.0
            
            for chan in ps.PICO_CHANNEL:
                # print(chan)
                status = ps.ps3000aSetChannel(
                    self.handle, ps.PICO_CHANNEL[chan], enabled, coupling,
                    chan_range, offset)
                # check status with throwing exception in case of error
                self.check(status)
    
    def setup_trigger(self, config):
        status = ps.ps3000aSetSimpleTrigger(
            self.handle, config['enable'], config['source'],
            config['threshold'], config['direction'], config['delay'],
            config['auto_trig_ms']
            )
        self.check(status)
        
    def setup_timebase(self, config):
        '''
        Setup timebase with config with following parameters:
            fs - sampling frequency
            len_s - record length
        '''
        # Prepare memory segments to store the desired number of samples
        # Preparing memory segment is important because after a trigger event,
        # the memory segment is filled completely.
        # wanted number of samples. Provide some headroom here, because 
        # the factual number of samples is always less than this number
        
        # The number of enabled channels
        nch = sum(config['enabled'])
        # the number of total samples requested according to config parameters
        nof_samples_requested = int(config['len_s'] * config['fs']) * nch
        # the number of samples without segmentation available to all enabled channels
        # this number is shared among the enabled channels
        nof_samples_total = ctypes.c_int32()
        # factual number of samples after segmentation
        nof_samples_fact = ctypes.c_int32() 
        # Get max number of samples without segmentation (whole memory is one segment)
        status = ps.ps3000aMemorySegments(self.handle, 1, ctypes.byref(nof_samples_total))
        self.check(status)
        # The number of segments to store the desired number of samples
        nof_segments = nof_samples_total.value // nof_samples_requested
        
        max_segments = ctypes.c_uint32() # maximum number of segments
        status = ps.ps3000aGetMaxSegments(self.handle, ctypes.byref(max_segments))
        self.check(status)
        
        if nof_segments > max_segments.value:
            print(f"N segments requested: {nof_segments}")
            print(f"Max segments: {max_segments.value}")
            print('Using max. number of segments')
            nof_segments = max_segments.value
            # raise ValueError("Number of segments exceeds maximum!")
        
        # Segment memory for the calculated number of segments
        status = ps.ps3000aMemorySegments(self.handle, nof_segments, ctypes.byref(nof_samples_fact))
        self.check(status)
        
        # fs = 3e6 # desired sampling frequency
        dt = 1/config['fs'] # requested sampling interval
        
        # Calculate timebase according to the formula from the scope's manual
        timebase = round(dt * 125e6) + 2 # (n–2) / 125,000,000 = dt [s] for n = 3 ... 2^32-1
        dt_ns = ctypes.c_float() # actual sampling interval
        seg_ind = 0 # memory segment index
        # seg_ind = ctypes.c_uint32() # memory segment index
        
        nof_samples_requested = nof_samples_fact.value // nch
        status = ps.ps3000aGetTimebase2(
            self.handle, timebase, nof_samples_requested, ctypes.byref(dt_ns), 0,
            ctypes.byref(nof_samples_fact), seg_ind
            )
        self.check(status)
        
        self.dt = dt_ns.value * 1e-9 # factual sampling interval
        self.fs = 1/self.dt # factual sampling frequency
        self.nof_samples = nof_samples_fact.value # factual number of samples
        self.timebase = timebase
    
    
    def get_data_analog(self):
        # Acquiring the data
        nof_samp_pretrig = 0
        nof_samp_posttrig = self.nof_samples
        oversample = 0 # This parameter is ignored in the following function
        record_time_ms = ctypes.c_int32() # The length of the record
        seg_ind = 0 # Memory segment index to store data to
        ready_cb_func = None # Pointer to the call back function when the data is acquired
        param_to_cb_func = None # Pointer to the structure passed to the callback function
        
        status = ps.ps3000aRunBlock(
            self.handle, nof_samp_pretrig, nof_samp_posttrig, self.timebase, oversample,
            ctypes.byref(record_time_ms), seg_ind, ready_cb_func, param_to_cb_func
            )
        self.check(status)
        
        # Check if the data is ready
        data_ready = ctypes.c_int16(0)
        
        timeout = 5 # data acquisition timeout, seconds
        t0 = time()
        while True:
            status = ps.ps3000aIsReady(self.handle, ctypes.byref(data_ready))
            self.check(status)
            if data_ready.value:
                break
            t = time()
            if t - t0 > timeout:
                print('Data timeout!')
                break
            sleep(50e-3)
        
        # Prepare a buffer to store the data
        # (this can be done out of loop if multiple reads of data are required)
        chan = ps.PICO_CHANNEL['A']
        buffer = np.zeros(nof_samp_posttrig, dtype=np.dtype('int16'))
        seg_ind = 0
        downsampling_mode = ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE']
        
        status = ps.ps3000aSetDataBuffer(
            self.handle, chan, buffer.ctypes.data, buffer.size, seg_ind, downsampling_mode
            )
        self.check(status)
        
        # Get data values
        start_ind = 0 # Starting point for data collection
        downsampling_ratio = 1 # Downsampling ratio when decimation is used
        # a set of flags that indicate whether an overvoltage has
        # occurred on any of the channels, zero means no overflow on any of the channels
        overflow = ctypes.c_int16()
        # factual number of samples
        nof_samples_fact = ctypes.c_int32(self.nof_samples)
        
        status = ps.ps3000aGetValues(
            self.handle, start_ind, ctypes.byref(nof_samples_fact), downsampling_ratio,
            downsampling_mode, seg_ind, ctypes.byref(overflow)
            )
        self.check(status)
        
        return buffer, nof_samples_fact.value, overflow.value
    
    def get_data_digital(self):
        
        #%% Prepare a buffer to store the data
        # (this can be done out of loop if multiple reads of data are required)
        chan = ps.PS3000A_DIGITAL_PORT["PS3000A_DIGITAL_PORT0"]
        buffer = np.empty(self.nof_samples, dtype=np.dtype('int16'))
        seg_ind = 0
        downsampling_mode = ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE']
        
        status = ps.ps3000aSetDataBuffer(
            self.handle, chan, buffer.ctypes.data, buffer.size, seg_ind, downsampling_mode
            )
        self.check(status)
        
        #%% Acquire the data
        nof_samp_pretrig = 0
        nof_samp_posttrig = self.nof_samples
        oversample = 0 # This parameter is ignored in the following function
        record_time_ms = ctypes.c_int32() # The length of the record
        seg_ind = 0
        ready_cb_func = None # Pointer to the call back function when the data is acquired
        param_to_cb_func = None # Pointer to the structure passed to the callback function
        
        status = ps.ps3000aRunBlock(
            self.handle, nof_samp_pretrig, nof_samp_posttrig, self.timebase, oversample,
            ctypes.byref(record_time_ms), seg_ind, ready_cb_func, param_to_cb_func
            )
        self.check(status)
        
        # Check if the data is ready
        data_ready = ctypes.c_int16(0)
        
        timeout = 5 # data acquisition timeout, seconds
        t0 = time()
        while True:
            status = ps.ps3000aIsReady(self.handle, ctypes.byref(data_ready))
            self.check(status)
            if data_ready.value:
                break
            t = time()
            if t - t0 > timeout:
                print('Data timeout!')
                break
            sleep(50e-3)
        #%% Get data values
        start_ind = 0 # Starting point for data collection
        downsampling_ratio = 1 # Downsampling ratio when decimation is used
        # a set of flags that indicate whether an overvoltage has
        # occurred on any of the channels, zero means no overflow on any of the channels
        overflow = ctypes.c_int16()
        # factual number of samples
        nof_samples_fact = ctypes.c_int32(self.nof_samples)
        
        status = ps.ps3000aGetValues(
            self.handle, start_ind, ctypes.byref(nof_samples_fact), downsampling_ratio,
            downsampling_mode, seg_ind, ctypes.byref(overflow)
            )
        self.check(status)
        
        #%% Split digital data into separate arrays
        data = np.empty((8, len(buffer)), dtype=np.int8)
        for i in range(len(data)):
            data[i, :] = (buffer & (1 << i)) >> i
        
        return data
    
    
    def adc2volts(self, buffer, chan_range):
        voltage_ranges_mV = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000]
        voltage_range_mV = voltage_ranges_mV[chan_range]
        data_V = voltage_range_mV*1e-3/self.max_adc*buffer
        return data_V
    
    def check(self, status):
        # checks status for error code, throws exception with an error message
        # in case of error
        if status != ps.PICO_STATUS['PICO_OK']:
            error_message = 'UNKNOWN_ERROR'
            for error_key in ps.PICO_STATUS.keys():
                if ps.PICO_STATUS[error_key] == status:
                    error_message = error_key
                    break
            error_message += f', {status:#04x}'
            raise DeviceAPIError(error_message)