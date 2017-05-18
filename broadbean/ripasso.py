# Module providing filter compensation. Developed for use with the broadbean
# pulse building module, but provides a standalone API
#
# The name is (of course) a pun. Ripasso; first a filter, then a compensation,
# i.e. something that is re-passed. Also not quite an Amarone...
#

import numpy as np
import matplotlib.pyplot as plt
from numpy.fft import fft, ifft, fftfreq
import logging

log = logging.getLogger(__name__)


class MissingFrequenciesError(Exception):
    pass


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
            high-pass filter. Default: 0.

    Returns:
        np.array:
            The filtered signal along the original time axis. Imaginary
            parts are discarded prior to return.

    Raises:
        ValueError: If kind is neither 'HP' nor 'LP'
    """

    if kind not in ['HP', 'LP']:
        raise ValueError('Please specify filter type as either "HP" or "LP".')

    N = len(signal)
    transfun = _rcFilter(SR, N, f_cut, kind=kind, order=order, DCgain=DCgain)
    output = ifft(fft(signal)*transfun)
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
            high-pass filter. Default: 1.

    Returns:
        np.array:
            The filtered signal along the original time axis. Imaginary
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
    output = ifft(fft(signal)*transfun)
    output = np.real(output)

    return output


def applyCustomTransferFunction(signal, SR, tf_freqs, tf_amp, invert=False):
    """
    Apply custom transfer function

    Given a signal, its sample rate, and a provided transfer function, apply
    the transfer function to the signal.

    Args:
        signal (np.array): A numpy array containing the signal
        SR (int): The sample rate of the signal (Sa/s)
        tf_freqs (np.array): The frequencies of the transfer function. Must
            be monotonically increasing.
        tf_amp (np.array): The amplitude of the transfer function. Must be
            dimensionless.
        invert (Optional[bool]): If True, the inverse transfer function is
            applied. Default: False.

    Returns:
        np.array:
        The modified signal.
    """

    npts = len(signal)

    # validate tf_freqs

    df = np.diff(tf_freqs).round(6)

    if not np.sum(df > 0) == len(df):
        raise ValueError('Invalid transfer function freq. axis. '
                         'Frequencies must be monotonically increasing.')

    if not tf_freqs[-1] >= SR/2:
        # TODO: think about whether this is a problem
        # What is the desired behaviour for high frequencies if nothing
        # is specified? I guess NOOP, i.e. the transfer func. is 1
        raise MissingFrequenciesError('Supplied transfer function does not '
                                      'specify frequency response up to the '
                                      'Nyquist frequency of the signal.')

    if not tf_freqs[0] == 0:
        # what to do in this case? Extrapolate 1s? Make the user do this?
        pass

    # Step 1: resample to fftfreq type axis
    freqax = fftfreq(npts, 1/SR)
    freqax_pos = freqax[:npts//2]
    freqax_neg = freqax[npts//2:]

    resampled_pos = np.interp(freqax_pos, tf_freqs, tf_amp)
    resampled_neg = np.interp(-freqax_neg[::-1], tf_freqs, tf_amp)

    transferfun = np.concatenate((resampled_pos, resampled_neg[::-1]))

    # Step 2: Apply transfer function
    if invert:
        power = -1
    else:
        power = 1

    signal_filtered = ifft(fft(signal)*(transferfun**power))
    imax = np.imag(signal_filtered).max()
    log.debug('Applying custom transfer function. Discarding imag parts '
              'no larger than {}'.format(imax))
    signal_filtered = np.real(signal_filtered)

    return signal_filtered
