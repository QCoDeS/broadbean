from broadbean.segment_concept_duration import Segment, FunctionSegment, GroupSegment, Expandable


def my_func(time, slope, offset):
    return time*slope+offset

def test_rerun():
    fs = FunctionSegment(function=my_func, duration=1, slope='conduction', offset=1)
    fs2 = FunctionSegment(function=my_func, duration=None, slope='conduction', offset=1)
    gs = GroupSegment(fs2, fs, duration=2)

    data1 = gs.forge(100, conduction=2)
    data2 = gs.forge(100, conduction=2)

    assert all(data2 == data1)


