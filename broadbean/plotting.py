# A little helper module for plotting of broadbean objects

from typing import Tuple, Union, Dict, List

import numpy as np
import matplotlib.pyplot as plt

from broadbean import Sequence, Element, Segment, _BaseSegment
from broadbean.sequence import Sequence as SimpleSequence
from broadbean.tools import is_subsequence, forged_sequence_dict_to_list

# The object we can/want to plot
BBObject = Union[Sequence, Element, _BaseSegment]


# def getSIScalingAndPrefix(minmax: Tuple[float, float]) -> Tuple[float, str]:
def getSIScalingAndPrefix(v: float) -> Tuple[float, str]:
    """
    Return the scaling exponent and unit prefix. E.g. 2e-3 will
    return (1e3, 'm')

    Args:
        minmax: The value of the signal

    Returns:
        A tuple of the scaling (inverse of the prefix) and the prefix
          string.

    """
    if v == 0:
        v = 1  # type: ignore
    exponent = np.log10(v)
    prefix = ''
    scaling: float = 1

    if exponent < 0:
        prefix = 'm'
        scaling = 1e3
    elif exponent < -3:
        prefix = 'micro '
        scaling = 1e6
    elif exponent < -6:
        prefix = 'n'
        scaling = 1e9

    return (scaling, prefix)


def _plot_object_validator(obj_to_plot: BBObject) -> None:
    """
    Validate the object
    """
    if isinstance(obj_to_plot, Sequence):
        # TODO: implement sequence validation
        proceed = True

    elif isinstance(obj_to_plot, Element):
        # TODO: implement sequence validation
        proceed = True

    elif isinstance(obj_to_plot, _BaseSegment):
        # TODO: implement sequence validation
        proceed = True
        # obj_to_plot.validateDurations()


def _plot_object_forger(obj_to_plot: BBObject,
                        **forger_kwargs) -> Dict[int, Dict]:
    """
    Make a forged sequence out of any object.
    Returns a forged sequence.
    """
    if isinstance(obj_to_plot, list) or isinstance(obj_to_plot, dict):
        # TODO: validate forged sequence
        return obj_to_plot
    if isinstance(obj_to_plot, Sequence):
        seq = obj_to_plot
    elif isinstance(obj_to_plot, Element):
        seq = Sequence([obj_to_plot])
    elif isinstance(obj_to_plot, _BaseSegment):
        elem = Element({'wfm': obj_to_plot})
        seq = Sequence([elem])
    else:
        raise RuntimeWarning('Unexpected argument {obj_to_plot}')

    return seq.forge(**forger_kwargs)

def _plot_summariser(seq: Dict[int, Dict]) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Return a plotting summary of a subsequence.

        Args:
            seq: The 'content' value of a forged sequence where a
                subsequence resides

        Returns:
            A dict that looks like a forged element, but all waveforms
            are just two points, np.array([min, max])
        """

        output = {}

        # we assume correctness, all postions specify the same channels
        chans = seq[1]['data'].keys()

        minmax = dict(zip(chans, [(0, 0)]*len(chans)))

        for element in seq.values():

            arr_dict = element['data']

            for chan in chans:
                wfm = arr_dict[chan]['wfm']
                if wfm.min() < minmax[chan][0]:
                    minmax[chan] = (wfm.min(), minmax[chan][1])
                if wfm.max() > minmax[chan][1]:
                    minmax[chan] = (minmax[chan][0], wfm.max())
                output[chan] = {'wfm': np.array(minmax[chan]),
                                'm1': np.zeros(2),
                                'm2': np.zeros(2),
                                'time': np.linspace(0, 1, 2)}

        return output


# the Grand Unified Plotter
def plotter(obj_to_plot: BBObject, **forger_kwargs) -> None:
    """
    The one plot function to be called. Turns whatever it gets
    into a sequence, forges it, and plots that.
    """

    # TODO:
    # - Take axes as input
    # - Auto calculate SR based on durations and dpi

    _plot_object_validator(obj_to_plot)
    seq = _plot_object_forger(obj_to_plot, **forger_kwargs)
    SR = forger_kwargs['SR']
    # TODO: this is only for compatibilty
    seq = forged_sequence_dict_to_list(seq)
    # Get the dimensions.
    chans = seq[0]['content'][0]['data'].keys()
    seqlen = len(seq)

    # Then figure out the figure scalings
    chanminmax: Dict[Tuple[float, float]] = {}
    for chan in chans:
        minmax = [np.inf, -np.inf]
        for elem in seq:
            if is_subsequence(elem):
                for subelem in elem['content']:
                    wfmdata = subelem['data'][chan]
                    minmax = [min(minmax[0], wfmdata.min()),
                              max(minmax[1], wfmdata.max())]
            else:
                wfmdata = elem['content'][0]['data'][chan]
                minmax = [min(minmax[0], wfmdata.min()),
                          max(minmax[1], wfmdata.max())]
        chanminmax[chan] = minmax

    fig, axs = plt.subplots(len(chans), seqlen)

    # ...and do the plotting
    for chanind, chan in enumerate(chans):
        # figure out the channel voltage scaling
        # The entire channel shares a y-axis

        minmax: Tuple[float, float] = chanminmax[chan]
        v_max = max(map(abs, minmax))  # type: ignore
        (voltagescaling, voltageprefix) = getSIScalingAndPrefix(v_max)
        voltageunit = voltageprefix + 'V'

        for pos, elem in enumerate(seq):
        # for pos in range(seqlen):
            # axes is np.ndarray.
            # 1 by N arrays are indexed differently than M by N arrays
            # and 1 by 1 arrays are not arrays at all...
            # that is plt.subplots(10,1) returns array of shape (10,) and not (10,1)
            if len(chans) == 1 and seqlen > 1:
                ax = axs[pos]
            if len(chans) > 1 and seqlen == 1:
                ax = axs[chanind]
            if len(chans) == 1 and seqlen == 1:
                ax = axs
            if len(chans) > 1 and seqlen > 1:
                ax = axs[chanind, pos]

            # reduce the tickmark density (must be called before scaling)
            ax.locator_params(tight=True, nbins=4, prune='lower')

            if is_subsequence(elem):
                arr_dict = _plot_summariser(elem['content'])
                wfm = arr_dict[chan]['wfm']
                newdurs = []

                ax.annotate('SUBSEQ', xy=(0.5, 0.5),
                            xycoords='axes fraction',
                            horizontalalignment='center')
                time = np.linspace(0, 1, 2)  # needed for timeexponent
            else:
                wfm = elem['content'][0]['data'][chan]
                # TODO: add support for markers
                # m1 = content.get('m1', np.zeros_like(wfm))
                # m2 = content.get('m2', np.zeros_like(wfm))
                # TODO: is this correct?
                npts = wfm.size
                duration = npts/SR
                time = np.linspace(0, duration, npts, endpoint=False)
                # where do these come from? not used in this file
                # newdurs = content.get('newdurations', [])
                newdurs = []

            # Figure out the axes' scaling
            (timescaling, prefix) = getSIScalingAndPrefix(time.max())
            timeunit = prefix + 's'

            if not is_subsequence(elem):
                ax.plot(timescaling*time, voltagescaling*wfm, lw=3,
                        color=(0.6, 0.4, 0.3), alpha=0.4)

            ymax = voltagescaling * chanminmax[chan][1]
            ymin = voltagescaling * chanminmax[chan][0]
            yrange = ymax - ymin
            ax.set_ylim([ymin-0.05*yrange, ymax+0.2*yrange])

            # TODO: add support for markers, make loops to not repeat code
            # markers
            # if not is_subsequence(elem):
            #     # TODO: make this work for more than two markers

            #     # marker1 (red, on top)
            #     y_m1 = ymax+0.15*yrange
            #     marker_on = np.ones_like(m1)
            #     marker_on[m1 == 0] = np.nan
            #     marker_off = np.ones_like(m1)
            #     ax.plot(timescaling*time, y_m1*marker_off,
            #             color=(0.6, 0.1, 0.1), alpha=0.2, lw=2)
            #     ax.plot(timescaling*time, y_m1*marker_on,
            #             color=(0.6, 0.1, 0.1), alpha=0.6, lw=2)

            #     # marker 2 (blue, below the red)
            #     y_m2 = ymax+0.10*yrange
            #     marker_on = np.ones_like(m2)
            #     marker_on[m2 == 0] = np.nan
            #     marker_off = np.ones_like(m2)
            #     ax.plot(timescaling*time, y_m2*marker_off,
            #             color=(0.1, 0.1, 0.6), alpha=0.2, lw=2)
            #     ax.plot(timescaling*time, y_m2*marker_on,
            #             color=(0.1, 0.1, 0.6), alpha=0.6, lw=2)

            # # If subsequence, plot lines indicating min and max value
            # else:
            #     # min:
            #     ax.plot(time, np.ones_like(time)*wfm[0],
            #             color=(0.12, 0.12, 0.12), alpha=0.2, lw=2)
            #     # max:
            #     ax.plot(time, np.ones_like(time)*wfm[1],
            #             color=(0.12, 0.12, 0.12), alpha=0.2, lw=2)

            #     ax.set_xticks([])



            # time step lines
            for dur in np.cumsum(newdurs):
                ax.plot([timescaling*dur, timescaling*dur],
                        [ax.get_ylim()[0], ax.get_ylim()[1]],
                        color=(0.312, 0.2, 0.33),
                        alpha=0.3)

            # labels
            if pos == 0:
                ax.set_ylabel('({})'.format(voltageunit))
            if pos == seqlen - 1 and not(isinstance(obj_to_plot, _BaseSegment)):
                newax = ax.twinx()
                newax.set_yticks([])

                if isinstance(chan, int):
                    new_ylabel = f'Ch. {chan}'
                elif isinstance(chan, str):
                    new_ylabel = chan
                newax.set_ylabel(new_ylabel)

            if is_subsequence(elem):
                ax.set_xlabel('Time N/A')
            else:
                ax.set_xlabel('({})'.format(timeunit))

            # remove excess space from the plot
            if not chanind+1 == len(chans):
                ax.set_xticks([])
            if not pos == 0:
                ax.set_yticks([])
            fig.subplots_adjust(hspace=0, wspace=0)

            # display sequencer information
            if chanind == 0 and isinstance(obj_to_plot, Sequence):
                seq_info = seq[pos+1]['sequencing']
                titlestring = ''
                if seq_info['twait'] == 1:  # trigger wait
                    titlestring += 'T '
                if seq_info['nrep'] > 1:  # nreps
                    titlestring += '\u21BB{} '.format(seq_info['nrep'])
                if seq_info['nrep'] == 0:
                    titlestring += '\u221E '
                if seq_info['jump_input'] != 0:
                    if seq_info['jump_input'] == -1:
                        titlestring += 'E\u2192 '
                    else:
                        titlestring += 'E{} '.format(seq_info['jump_input'])
                if seq_info['goto'] > 0:
                    titlestring += '\u21b1{}'.format(seq_info['goto'])

                ax.set_title(titlestring)
