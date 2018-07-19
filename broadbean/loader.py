
from broadbean import Segment, SegmentGroup, Element, Sequence
from broadbean.atoms import sine, ramp, flat, zero, marker_on, marker_off
from broadbean.types import ForgedSequenceType
from broadbean.plotting import plotter
from broadbean.tools import check_sequence_duration_consistent
from broadbean.transformations import make_delcarative_linear_transformation
import broadbean


# reading
def get_single_entry(input_dict):
    k = list(input_dict.keys())
    assert len(k) == 1
    return k[0], input_dict[k[0]]

def read_segment(data):
    key, args = get_single_entry(data)
    if key == 'SegmentGroup':
        segs = [read_segment(seg) for seg in args['segments']]
        transformation_yaml = args.get('transformation', None)
        transformation = read_transformation(transformation_yaml)
        seg = SegmentGroup(*segs,
                           duration=args['duration'],
                           transformation=transformation)
    else:
        func = getattr(broadbean.atoms, key)
        seg = func(**args)
    return seg

def read_element(data):
    seg_dict = {}
    duration = data['duration']
    for channel_id, channel_data in data['segments'].items():
        if isinstance(channel_data, list):
            segs = [read_segment(seg) for seg in channel_data]
            seg = SegmentGroup(*segs, duration=duration)
        else:
            seg = read_segment(channel_data)
        seg_dict[channel_id] = seg

    transformation_yaml = data.get('transformation', None)
    transformation = read_transformation(transformation_yaml)
    return Element(segments=seg_dict,
                   sequencing=data.get('sequencing', {}),
                   local_context=data.get('local_context', {}),
                   transformation=transformation)

def read_transformation(data):
        transformation = None
        if data:
            if data['type'] == 'declarative_linear_transformation':
                transformation = read_simple_transformation(data['data'])
        return transformation

def read_simple_transformation(data):
    items = []
    for item in data:
        assigned, l = get_single_entry(item)
        independents = [tuple(pair) for pair in l]
        items.append((assigned, independents))
    return make_delcarative_linear_transformation(items)



def write_segment(seg):
    if isinstance(seg, SegmentGroup):
        ret = copy(seg._properties)
        ret['segmetns'] = [write_segment(subseg) for subseg in seg._segments]
        ret['transformation'] = write_transformation(seg._transformation)
    elif isinstance(seg, Segment):
        return {seg._function: seg._properties}
    else:
        raise RuntimeError(f'Tried to read object of type {type(seg)} as segment')

# simply copy and paste from read versions
# def write_element(elem):
#     seg_dict = {}
#     duration = data['duration']
#     for channel_id, channel_data in data['segments'].items():
#         if isinstance(channel_data, list):
#             segs = [read_segment(seg) for seg in channel_data]
#             seg = SegmentGroup(*segs, duration=duration)
#         else:
#             seg = read_segment(channel_data)
#         seg_dict[channel_id] = seg

#     transformation_yaml = data.get('transformation', None)
#     transformation = read_transformation(transformation_yaml)
#     return Element(segments=seg_dict,
#                    sequencing=data.get('sequencing', {}),
#                    local_context=data.get('local_context', {}),
#                    transformation=transformation)

# def write_transformation(data):
#         transformation = None
#         if data:
#             if data['type'] == 'declarative_linear_transformation':
#                 transformation = read_simple_transformation(data['data'])
#         return transformation

# def write_simple_transformation(data):
#     items = []
#     for item in data:
#         assigned, l = get_single_entry(item)
#         independents = [tuple(pair) for pair in l]
#         items.append((assigned, independents))
#     return make_delcarative_linear_transformation(items)
