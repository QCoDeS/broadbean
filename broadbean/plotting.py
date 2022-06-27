# A little helper module for plotting of broadbean objects

from typing import Tuple, Union, Dict, List

import numpy as np
import matplotlib.pyplot as plt

from broadbean import Sequence, BluePrint, Element
from broadbean.sequence import SequenceConsistencyError

# The object we can/want to plot
BBObject = Union[Sequence, BluePrint, Element]


def getSIScalingAndPrefix(minmax: Tuple[float, float]) -> Tuple[float, str]:
    """
    Return the scaling exponent and unit prefix. E.g. (-2e-3, 1e-6) will
    return (1e3, 'm')

    Args:
        minmax: The (min, max) value of the signal

    Returns:
        A tuple of the scaling (inverse of the prefix) and the prefix
          string.

    """
    # due to https://github.com/python/mypy/issues/6697
    v_max: float = max(map(abs, minmax))  # type: ignore[arg-type, type-var, assignment]
    if v_max == 0:
        v_max = 1
    exponent = np.log10(v_max)
    prefix = ''
    scaling: float = 1

    if exponent < 0:
        prefix = 'm'
        scaling = 1e3
    if exponent < -3:
        prefix = 'micro '
        scaling = 1e6
    if exponent < -6:
        prefix = 'n'
        scaling = 1e9

    return (scaling, prefix)


def _plot_object_validator(obj_to_plot: BBObject) -> None:
    """
    Validate the object
    """
    if isinstance(obj_to_plot, Sequence):
        proceed = obj_to_plot.checkConsistency(verbose=True)
        if not proceed:
            raise SequenceConsistencyError

    elif isinstance(obj_to_plot, Element):
        obj_to_plot.validateDurations()

    elif isinstance(obj_to_plot, BluePrint):
        assert obj_to_plot.SR is not None


def _plot_object_forger(obj_to_plot: BBObject,
                        **forger_kwargs) -> Dict[int, Dict]:
    """
    Make a forged sequence out of any object.
    Returns a forged sequence.
    """

    if isinstance(obj_to_plot, BluePrint):
        elem = Element()
        elem.addBluePrint(1, obj_to_plot)
        seq = Sequence()
        seq.addElement(1, elem)
        seq.setSR(obj_to_plot.SR)

    elif isinstance(obj_to_plot, Element):
        seq = Sequence()
        seq.addElement(1, obj_to_plot)
        seq.setSR(obj_to_plot._meta['SR'])

    elif isinstance(obj_to_plot, Sequence):
        seq = obj_to_plot

    forged_seq = seq.forge(includetime=True, **forger_kwargs)

    return forged_seq


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

    # TODO: Take axes as input

    # strategy:
    # * Validate
    # * Forge
    # * Plot

    _plot_object_validator(obj_to_plot)

    seq = _plot_object_forger(obj_to_plot, **forger_kwargs)

    # Get the dimensions.
    chans = seq[1]['content'][1]['data'].keys()
    seqlen = len(seq.keys())

    def update_minmax(chanminmax, wfmdata, chanind):
        (thismin, thismax) = (wfmdata.min(), wfmdata.max())
        if thismin < chanminmax[chanind][0]:
            chanminmax[chanind] = [thismin, chanminmax[chanind][1]]
        if thismax > chanminmax[chanind][1]:
            chanminmax[chanind] = [chanminmax[chanind][0], thismax]
        return chanminmax

    # Then figure out the figure scalings
    minf: float = -np.inf
    inf: float = np.inf
    chanminmax: List[Tuple[float, float]] = [(inf, minf)]*len(chans)
    for chanind, chan in enumerate(chans):
        for pos in range(1, seqlen+1):
            if seq[pos]['type'] == 'element':
                wfmdata = (seq[pos]['content'][1]
                           ['data'][chan]['wfm'])
                chanminmax = update_minmax(chanminmax, wfmdata, chanind)
            elif seq[pos]['type'] == 'subsequence':
                for pos2 in seq[pos]['content'].keys():
                    elem = seq[pos]['content'][pos2]['data']
                    wfmdata = elem[chan]['wfm']
                    chanminmax = update_minmax(chanminmax,
                                               wfmdata, chanind)

    fig, axs = plt.subplots(len(chans), seqlen)

    # ...and do the plotting
    for chanind, chan in enumerate(chans):

        # figure out the channel voltage scaling
        # The entire channel shares a y-axis

        minmax: Tuple[float, float] = chanminmax[chanind]

        (voltagescaling, voltageprefix) = getSIScalingAndPrefix(minmax)
        voltageunit = voltageprefix + 'V'

        for pos in range(seqlen):
            # 1 by N arrays are indexed differently than M by N arrays
            # and 1 by 1 arrays are not arrays at all...
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

            if seq[pos+1]['type'] == 'element':
                content = seq[pos+1]['content'][1]['data'][chan]
                wfm = content['wfm']
                m1 = content.get('m1', np.zeros_like(wfm))
                m2 = content.get('m2', np.zeros_like(wfm))
                time = content['time']
                newdurs = content.get('newdurations', [])

            else:
                arr_dict = _plot_summariser(seq[pos+1]['content'])
                wfm = arr_dict[chan]['wfm']
                newdurs = []

                ax.annotate('SUBSEQ', xy=(0.5, 0.5),
                            xycoords='axes fraction',
                            horizontalalignment='center')
                time = np.linspace(0, 1, 2)  # needed for timeexponent

            # Figure out the axes' scaling
            timeexponent = np.log10(time.max())
            timeunit = 's'
            timescaling: float = 1.0
            if timeexponent < 0:
                timeunit = 'ms'
                timescaling = 1e3
            if timeexponent < -3:
                timeunit = 'micro s'
                timescaling = 1e6
            if timeexponent < -6:
                timeunit = 'ns'
                timescaling = 1e9

            if seq[pos+1]['type'] == 'element':
                ax.plot(timescaling*time, voltagescaling*wfm, lw=3,
                        color=(0.6, 0.4, 0.3), alpha=0.4)

            ymax = voltagescaling * chanminmax[chanind][1]
            ymin = voltagescaling * chanminmax[chanind][0]
            yrange = ymax - ymin
            ax.set_ylim([ymin-0.05*yrange, ymax+0.2*yrange])

            if seq[pos+1]['type'] == 'element':
                # TODO: make this work for more than two markers

                # marker1 (red, on top)
                y_m1 = ymax+0.15*yrange
                marker_on = np.ones_like(m1)
                marker_on[m1 == 0] = np.nan
                marker_off = np.ones_like(m1)
                ax.plot(timescaling*time, y_m1*marker_off,
                        color=(0.6, 0.1, 0.1), alpha=0.2, lw=2)
                ax.plot(timescaling*time, y_m1*marker_on,
                        color=(0.6, 0.1, 0.1), alpha=0.6, lw=2)

                # marker 2 (blue, below the red)
                y_m2 = ymax+0.10*yrange
                marker_on = np.ones_like(m2)
                marker_on[m2 == 0] = np.nan
                marker_off = np.ones_like(m2)
                ax.plot(timescaling*time, y_m2*marker_off,
                        color=(0.1, 0.1, 0.6), alpha=0.2, lw=2)
                ax.plot(timescaling*time, y_m2*marker_on,
                        color=(0.1, 0.1, 0.6), alpha=0.6, lw=2)

            # If subsequence, plot lines indicating min and max value
            if seq[pos+1]['type'] == 'subsequence':
                # min:
                ax.plot(time, np.ones_like(time)*wfm[0],
                        color=(0.12, 0.12, 0.12), alpha=0.2, lw=2)
                # max:
                ax.plot(time, np.ones_like(time)*wfm[1],
                        color=(0.12, 0.12, 0.12), alpha=0.2, lw=2)

                ax.set_xticks([])

            # time step lines
            for dur in np.cumsum(newdurs):
                ax.plot([timescaling*dur, timescaling*dur],
                        [ax.get_ylim()[0], ax.get_ylim()[1]],
                        color=(0.312, 0.2, 0.33),
                        alpha=0.3)

            # labels
            if pos == 0:
                ax.set_ylabel(f"({voltageunit})")
            if pos == seqlen - 1 and not (isinstance(obj_to_plot, BluePrint)):
                newax = ax.twinx()
                newax.set_yticks([])
                if isinstance(chan, int):
                    new_ylabel = f'Ch. {chan}'
                elif isinstance(chan, str):
                    new_ylabel = chan
                newax.set_ylabel(new_ylabel)

            if seq[pos+1]['type'] == 'subsequence':
                ax.set_xlabel('Time N/A')
            else:
                ax.set_xlabel(f"({timeunit})")

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
