from functools import wraps, partial
from broadbean.segment import Segment

def atom(function):
    @wraps(function)
    def decorated_func(*args, **kwargs):
        return Segment(function=function, *args, **kwargs)
    return decorated_func


@atom
def sine(time, frequency, amplitude=1, phase=0):
    return amplitude*np.sin(frequency*np.pi*time + phase)

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
def on(time):
    return np.ones(time.shape)

@atom
def off(time):
    return np.zeros(time.shape)
