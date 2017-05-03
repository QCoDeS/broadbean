# Module providing filter compensation. Developed for use with the broadbean
# pulse building module, but provides a standalone API
#
# The name is (of course) a pun. Ripasso; first a filter, then a compensation,
# i.e. something that is re-passed. Also not quite an Amarone...
#

import numpy as np
import matplotlib.pyplot as plt
from numpy.fft import fft, ifft, fftfreq

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


def filt(SR, npts, f_cut, kind='HP', order=1, DGgain=0):
    """
    First-order (RC circuit) filter
    made with frequencies matching the fft output
    """

    freqs = fftfreq(npts, 1/SR)

    tau = 1/f_cut
    top = 2j*np.pi

    if kind == 'HP':
        tf = top*tau*freqs/(1+top*tau*freqs)

        # now, we have identically zero gain for the DC component,
        # which makes the transfer function non-invertible
        #
        # It is a bit of an open question what DC compensation we want...

        tf[tf == 0] = DCgain  # No DC suppression

    elif kind == 'LP':
        tf = 1/(1+top*tau*freqs)

    return tf**order


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

    f_cut = 100
    order = 3
    tau = 1/f_cut

    time = np.linspace(0, npts/SR, npts)
    signal = squarewave(npts, periods=5)
    signal += 0.05*np.sin(2*np.pi*25/time[-1]*time)
    # signal = np.sin(2*np.pi*50*time)

    signal_fd = fft(signal)

    # filter the signal
    transferfun = filt(SR, npts, f_cut, kind='LP')

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

    # Now the final thing
    out1 = np.convolve(np.tile(test1, 2), ifft(transferfun**(-order)), mode='full')
    out1 = out1[npts:2*npts]
    out2 = ifft(fft(test3)*transferfun**(order))

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

    axs[1, 1].plot(time, out2)
    axs[1, 1].set_title('Filtered compensated signal')
    axs[1, 1].set_xlabel('Time (s)')

    plt.tight_layout()


###############################################################################
# API BEGINS HERE
###############################################################################


def _rcFilter(SR, npts, f_cut, kind='HP', order=1, DCgain=0):
    """
    Nth order (RC circuit) filter
    made with frequencies matching the fft output
    """

    freqs = fftfreq(npts, 1/SR)

    tau = 1/f_cut
    top = 2j*np.pi

    if kind == 'HP':
        tf = top*tau*freqs/(1+top*tau*freqs)

        # now, we have identically zero gain for the DC component,
        # which makes the transfer function non-invertible
        #
        # It is a bit of an open question what DC compensation we want...

        tf[tf == 0] = DCgain  # No DC suppression

    elif kind == 'LP':
        tf = 1/(1+top*tau*freqs)

    return tf**order


def applyRCFilter(signal, SR, kind, f_cut, order, DCgain=0):
    """
    Apply a simple RC-circuit filter
    to signal and return the filtered signal.

    Args:
        signal (np.array): The input signal. The signal is assumed to start at
            t=0 and be evenly sampled at sample rate SR.
        SR (int): Sample rate (Sa/s) of the input signal
        kind (str): The type of filter. Either 'HP' or 'LP'.
        f_cut (float): The cutoff frequency of the filter (Hz)
        order (int): The order of the filter. The first order filter is
            applied order times.
        DCgain (Optional[float]): The DC gain of the filter. ONLY used by the
            high-pass filter. Default 0.

    Returns:
        np.array: The filtered signal along the original time axis. Imaginary
            parts are discarded prior to return.

    Raises:
        ValueError: If kind is neither 'HP' nor 'LP'
    """

    if kind not in ['HP', 'LP']:
        raise ValueError('Please specify filter type as either "HP" or "LP".')

    N = len(signal)
    transfun = _rcFilter(SR, N, f_cut, kind=kind, order=order, DCgain=DCgain)
    output = ifft(fft(signal*transfun))
    output = np.real(output)

    return output


def applyInverseRCFilter(signal, SR, kind, f_cut, order, DCgain=1):
    """
    Apply the inverse of an RC-circuit filter to a signal and return the
    compensated signal.

    Note that a high-pass filter in principle has identically zero DC
    gain which requires an infinite offset to compensate.

    Args:
        signal (np.array): The input signal. The signal is assumed to start at
            t=0 and be evenly sampled at sample rate SR.
        SR (int): Sample rate (Sa/s) of the input signal
        kind (str): The type of filter. Either 'HP' or 'LP'.
        f_cut (float): The cutoff frequency of the filter (Hz)
        order (int): The order of the filter. The first order filter is
            applied order times.
        DCgain (Optional[float]): The DC gain of the filter. ONLY used by the
            high-pass filter. Default 1.

    Returns:
        np.array: The filtered signal along the original time axis. Imaginary
            parts are discarded prior to return.

    Raises:
        ValueError: If kind is neither 'HP' nor 'LP'
        ValueError: If DCgain is zero.
    """

    if kind not in ['HP', 'LP']:
        raise ValueError('Wrong filter type. '
                         'Please specify filter type as either "HP" or "LP".')

    if not DCgain > 0:
        raise ValueError('Non-invertible DCgain! '
                         'Please set DCgain to a finite value.')

    N = len(signal)
    transfun = _rcFilter(SR, N, f_cut, order=-order, kind=kind, DCgain=DCgain)
    output = ifft(fft(signal*transfun))
    output = np.real(output)

    return output


SR = int(10e3)
npts = int(2e3)
f_cut = 250

signal = squarewave(npts, periods=4)

signal_hp = applyRCFilter(signal, SR, 'HP', f_cut, order=1)

plt.figure()
plt.plot(signal)
plt.plot(signal_hp)
