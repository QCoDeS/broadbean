# sandbox for filter compensation
#
# Ripasso... get it?

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import deconvolve, fftconvolve
from numpy.fft import fft, fftshift, ifft, ifftshift

plt.ion()


SR = int(1e3)
npts = int(2e3)

time = np.linspace(0, npts/SR, npts)
signal = np.sin(2*np.pi*2.5/time[-1]*time)-0.2*np.cos(2*np.pi*6/time[-1]*time)

signal2 = np.sin(2*np.pi*10/time[-1]*time)


def squarewave(npts, periods=5):

    periods = int(periods)
    array = np.zeros(npts, dtype=complex)

    for n in range(periods):
        array[int(n*npts/periods): int((2*n+1)*npts/2/periods)] = 1

    return array


def filt(SR, npts, f_cut, kind='HP'):
    """
    First-order (RC circuit) filter
    made with frequencies matching the fft output
    """

    freqs = np.fft.fftfreq(npts, 1/SR)

    tau = 1/f_cut
    top = 2j*np.pi

    if kind == 'HP':
        tf = top*tau*freqs/(1+top*tau*freqs)

        # now, we have identically zero gain for the DC component,
        # which makes the transfer function non-invertible

        tf[tf == 0] = 1e-8

    elif kind == 'LP':
        tf = 1/(1+top*tau*freqs)

    return tf


def checking():
    """
    Checking that it all makes sense
    """
    SR = int(30e3)
    npts = int(2e3)

    f_cut = 50
    order = 1
    tau = 1/f_cut

    time = np.linspace(0, npts/SR, npts)
    signal = squarewave(npts, periods=4)
    signal += 0.05*0*np.sin(2*np.pi*2/time[-1]*time)
    # signal = np.sin(2*np.pi*50*time)

    signal_fd = fft(signal)

    # filter the signal
    transferfun = filt(SR, npts, f_cut)

    signal_anti_filtered = signal_fd/transferfun

    # the filter, when convolving, has a settling time
    # we must have a full overlap before it is (in principle) settled
    signal_padded = np.concatenate((signal, signal))
    test1 = np.convolve(signal_padded, ifft(transferfun), mode='full')
    test1 = test1[npts:2*npts]

    test2 = ifft(fft(signal)*(transferfun**order))

    imax = max(np.imag(test1).max(), np.imag(test2).max())
    print('Discarding imaginary parts no larger than {}'.format(imax))
    test1 = np.real(test1)
    test2 = np.real(test2)

    test3 = ifft(signal_anti_filtered)
    test4 = np.convolve(np.tile(signal, 2), ifft(1/transferfun), mode='full')
    test4 = test4[npts:2*npts]
    # newsig = ifft(signal_filtered)  # correct
    compsig = ifft(signal_anti_filtered)

    # t1 = ifft(fft(compsig)*transferfun)  # Boom! this is the original signal

    plt.figure()
    plt.plot(time, signal, label='$s(t)$')
    plt.plot(time, test2, label='$\mathcal{F}^{-1}[\mathcal{F}[s]\cdot H]$')
    plt.title('Cutoff freq. : {} Hz. Order: {}'.format(f_cut, order))
    plt.xlabel('Time (s)')
    plt.legend()

    plt.figure()
    plt.title('Comparison of two calculations')
    plt.plot(test1, label='$s*\mathcal{F}^ {-1}[H]$')
    plt.plot(test2, label='$\mathcal{F}^{-1}[\mathcal{F}[s]\cdot H]$')
    plt.legend()

    plt.figure('Compensated signal')
    plt.plot(time, test3)
    plt.plot(time, test4+0.05)


def deconvolving():
    """
    Do filtering, compensation, and compensation+filtering

    TODO: make this take input signal and transfer-func
    """

    SR = int(30e3)
    npts = int(2e3)

    f_cut = 250
    order = 1
    tau = 1/f_cut

    time = np.linspace(0, npts/SR, npts)
    signal = squarewave(npts, periods=5)
    signal += 0.05*np.sin(2*np.pi*25/time[-1]*time)
    # signal = np.sin(2*np.pi*50*time)

    signal_fd = fft(signal)

    # filter the signal
    transferfun = filt(SR, npts, f_cut)

    signal_anti_filtered = signal_fd*(transferfun**(-order))

    # the filter, when convolving, has a settling time
    # we must have a full overlap before it is (in principle) settled
    signal_padded = np.concatenate((signal, signal))
    test1 = np.convolve(signal_padded, ifft(transferfun**order), mode='full')
    test1 = test1[npts:2*npts]

    test2 = ifft(fft(signal)*(transferfun**order))

    imax = max(np.imag(test1).max(), np.imag(test2).max())
    print('Discarding imaginary parts no larger than {}'.format(imax))
    test1 = np.real(test1)
    test2 = np.real(test2)

    test3 = ifft(signal_anti_filtered)
    test4 = np.convolve(np.tile(signal, 2), ifft(1/transferfun), mode='full')
    test4 = test4[npts:2*npts]

    imax = max(np.imag(test3).max(), np.imag(test4).max())
    print('Discarding imaginary parts no larger than {}'.format(imax))
    test3 = np.real(test3)
    test4 = np.real(test4)

    compsig = ifft(signal_anti_filtered)

    # t1 = ifft(fft(compsig)*transferfun)  # Boom! this is the original signal

    fig, axs = plt.subplots(2, 2)

    axs[0, 0].plot(time, signal)
    axs[0, 0].set_title('Input signal')
    axs[0, 0].set_xlabel('Time (s)')

    axs[0, 1].plot(time, test2)
    axs[0, 1].set_title('Filtered signal')
    axs[0, 1].set_xlabel('Time (s)')

    axs[1, 0].plot(time, test3)
    axs[1, 0].set_title('Compensated signal')
    axs[1, 0].set_xlabel('Time (s)')

    plt.tight_layout()

deconvolving()
