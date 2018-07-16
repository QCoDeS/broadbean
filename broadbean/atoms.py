import numpy as np
from functools import wraps, partial
from broadbean.segment import Segment

def atom(function):
    # wraps is incorrect here, we need to pop the kwarg 'time' and add duration
    @wraps(function)
    def decorated_func(*args, **kwargs):
        return Segment(function=function, *args, **kwargs)
    return decorated_func


@atom
def sine(time, frequency, amplitude=1, phase=0):
    return amplitude*np.sin(frequency*2*np.pi*time + phase)

@atom
def ramp(time, start=0, stop=1):
    #TODO: is this correct or do we need todo something about the endpoint?
    dur = time[-1]-time[0]
    return (stop-start)*time/dur+start

@atom
def flat(time, amplitude=1):
    return amplitude*np.ones(time.shape)

@atom
def zero(time):
    return np.zeros(time.shape)


# for markers
@atom
def marker_on(time):
    return np.ones(time.shape)

@atom
def marker_off(time):
    return np.zeros(time.shape)

@atom
def marker_pulse(time, delay, marker_duration):
    if time.size < 2:
        return off(time)
    SR = time[1] - time[0]
    # TODO: make checks on delay and marker_duration
    index_start = round(delay/SR)
    index_stop = round((delay+marker_duration)/SR)
    output = np.zeros(time.shape)
    output[index_start:index_stop] = 1
    return output
