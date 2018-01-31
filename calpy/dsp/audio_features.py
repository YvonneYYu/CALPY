# -*- coding: utf-8 -*-
import numpy
from scipy.fftpack import dct
from .yin import *
from .. import utilities

def _silence_or_sounding(signal, eps=1e-8):
    """Determine silence and sounding of a given (usually a relatively long period of time) audio.

        Implements algorithms of `PAPER`_ .
        
        Args:
            signal (numpy.array(float)): Sound signal in time domain.
            eps (float, optional): The minimum threshold. Defaults to 1e-8.
        
        Returns:
            list: A 0-1 list marking silence (0) and sounding (1).

        .. _paper:
            http://www.iaeng.org/publication/WCE2009/WCE2009_pp801-806.pdf
    """
    
    N = len(signal)
    signal = signal ** 2
    
    e_max, e_min = signal[0] if signal[0]>eps else 2*eps, eps

    marker = list()
    lamda  = (e_max - e_min)/e_max
    threshold  = (1 - lamda) * e_max + lamda * e_min

    marker.append(1 if signal[0]>threshold else 0)

    for i in range(1, N):
        #YYY modified the original equation from engy = signal[i] to the following.
        #YYY doesn't know why, bu it works more acurately than the original.
        #Happy accident
        engy = signal[i] ** 2
        if engy > e_max:
            e_max = engy
        elif engy < e_min:
            e_min = eps if engy <= eps else engy
        #thresholding
        lamda = (e_max - e_min) / e_max
        threshold = (1 - lamda) * e_max + lamda * e_min
        marker.append(1 if engy > threshold else 0)
        
    return marker

def pause_profile(signal, sampling_rate, min_silence_duration=0.01, time_step = 0.01, frame_window = 0.025):
    """Find pauses in audio.

        Args:
            signal (:obj:`numpy.array(float)`): Audio signal.
            sampling_rate (float): Sampling frequency in Hz.
            min_silence_duration (float, optional): The minimum duration in seconds to be considered pause. Default to 0.01.
            time_step (float, optional): The time interval (in seconds) between two pauses. Default to 0.01.
            frame_window (float, optional): The length of speech (in seconds) used to estimate pause. Default to 0.025.
        
        Returns:
            numpy.array(float): 0-1 1D numpy integer array with 1s marking pause.
    """
    
    signal = signal / max(abs(signal))
    signal = _silence_or_sounding(signal)
    signal = numpy.array(signal)
    
    N = len(signal)
    ans = numpy.zeros(N)

    i, count, start, end = 0, 0, 0, 0

    T = min_silence_duration * sampling_rate
    for i in range(N):
        if signal[i] == 0:
            if i == N-1 and signal[i-1] == 0 and count >= T:
                ans[start:end] = 1
            elif count==0:
                start, end, count = i, i+1, count+1
            else:
                end, count = end+1, count+1
        elif i > 0 and signal[i-1] == 0:
            if count >= T:  
                ans[start:end] = 1
            count = 0
    return utilities.compress_pause_to_time(ans, sampling_rate, time_step=time_step, frame_window=frame_window)

def dB_profile(signal, sampling_rate, time_step = 0.01, frame_window = 0.025):
    """Computes decible of signal amplitude of an entire conversation
       
        Args:
            signal (numpy.array(float)): Padded audio signal.
            sampling_rate (float): Sampling frequency in Hz.
            time_step (float, optional): The time interval (in seconds) between two dB values. Default to 0.01.
            frame_window (float, optional): The length of speech (in seconds) used to estimate dB. Default to 0.025.
        
        Returns:
            numpy.array(float): The decibles.
    """
    signal = numpy.abs(signal)
    
    T  = int(sampling_rate * time_step)
    Fr = int(sampling_rate * frame_window)
    Fr += (sampling_rate * frame_window - Fr) > 0
    
    N = (len(signal) - Fr) // T + 1

    dB = numpy.empty(N)
    
    #use mean over the entire converstaion as reference signal
    #should avoid using square opertion on row signal in case of overflow
    
    ref = 20*numpy.log(numpy.mean(signal[signal>0]))
    for i in range(N):
        dB[i] = sum(signal[i*Fr:(i+1)*Fr])/(Fr-1)

    vfunc = numpy.vectorize(lambda x: -float('inf') if not x else numpy.log(x) - numpy.log(ref))
    return vfunc(dB)

def pitch_profile(signal, sampling_rate, time_step = 0.01, frame_window = 0.025, lower_threshold = 75, upper_threshold = 255):
    """Compute pitch for a long (usually over an entire conversation) sound signal
        
        Args:
            signal (numpy.array(float)): Padded audio signal.
            sampling_rate (float): Sampling frequency in Hz.
            time_step (float, optional): The time interval (in seconds) between two pitches. Default to 0.01.
            frame_window (float, optional): The length of speech (in seconds) used to estimate pitch. Default to 0.025.
            lower_threshold (int, optional): Defaults to 75.
            upper_threshold (int, optional): Defaults to 225.
        
        Returns:
            numpy.array(float): Estimated pitch in Hz.
    """
    
    T  = int(sampling_rate * time_step)
    Fr = int(sampling_rate * frame_window)
    Fr += sampling_rate * frame_window - Fr > 0
    
    N = (len(signal) - Fr) // T + 1

    if not N:
        print("Warning: not enough signal, pitch profile will be empty.")
    
    p = numpy.empty( N )
    for i in range(N):
        p[i] = instantaneous_pitch(signal[i*T:i*T+Fr], sampling_rate)
    p[numpy.where( (p > upper_threshold) | (p < lower_threshold) )] = 0
    
    return p

def mfcc_profile(signal, sampling_rate, time_step = 0.01, frame_window = 0.025, NFFT = 512, nfilt = 40, ceps = 12):
    """ Compute MFCC for a long (usually over an entire conversation) sound signal.

        Reference: http://haythamfayek.com/2016/04/21/speech-processing-for-machine-learning.html

        Args:
            signal (numpy.array(float)): Padded audio signal.
            sampling_rate (float): Sampling frequency in Hz.
            time_step (float, optional): The time interval (in seconds) between two MFCC. Default to 0.01.
            frame_window (float, optional): The length of speech (in seconds) used to estimate MFCC. Default to 0.025.
            NFFT (int, optional): NFFT-point FFT.  Defaults to 512.
            nfilt (int, optional): Number of frequency bands in Mel-scaling.  Defaults to 40.
            ceps (int, optional): Number of mel frequency ceptral coefficients to be retained.  Defaults to 12.

        Returns:
            numpy.array() : Calculated Mel-Frequecy Cepstral Coefficients Matrix.
    """
    
    T  = int(sampling_rate * time_step)
    Fr = int(sampling_rate * frame_window)
    Fr += sampling_rate * frame_window - Fr > 0
    N = (len(signal) - Fr) // T + 1
    res = numpy.empty((ceps, N))
     
    if not N:
        print("Warning: not enough signal, mfcc profile will be empty.")
 
    #pre-calculate routine filter bank array
    low_mel, high_mel = 0, 2595 * numpy.log10(1 + sampling_rate / 1400)
    # Mel points
    mel_pts = numpy.linspace(low_mel, high_mel, nfilt + 2)
    # Corresponding Hz points
    hz_pts = (10 ** (mel_pts / 2595) - 1) * 700
    hz_pts = numpy.floor((NFFT + 1) * hz_pts / sampling_rate)
    # filter bank array
    fltBank = numpy.zeros((nfilt, int(numpy.floor(NFFT / 2 + 1))))
    for i in range(1, nfilt + 1):
        left, mid, right = int(hz_pts[i - 1]), int(hz_pts[i]), int(hz_pts[i + 1])
        for k in range(left, mid):
            fltBank[i - 1, k] = (k - hz_pts[i - 1]) / (hz_pts[i] - hz_pts[i - 1])
        for k in range(mid, right):
            fltBank[i - 1, k] = (hz_pts[i + 1] - k) / (hz_pts[i + 1] - hz_pts[i])
    fltBank = fltBank.T
 
    for i in range(N):
        frame = signal[i * T : i * T + Fr]
        # applies a hamming window before STFT, optional but highly recommended
        frame *= numpy.hamming(Fr)
        # power spectrum of FFT
        pow_frame = (1.0 / NFFT) * (numpy.absolute(numpy.fft.rfft(frame, NFFT)) ** 2)
        # filter bank it
        filter_bank = numpy.dot(pow_frame, fltBank)
        # special process of 0 points
        filter_bank = numpy.where(filter_bank == 0, numpy.finfo(float).eps, filter_bank)
        #scale to dB
        filter_bank = 20 * numpy.log10(filter_bank)
        #mfcc
        mfcc = dct(filter_bank, norm='ortho')
        res[:, i] = mfcc[1 : ceps + 1]
 
    return res