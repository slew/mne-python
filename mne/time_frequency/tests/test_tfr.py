import numpy as np
import os.path as op
from numpy.testing import assert_array_almost_equal

import mne
from mne import fiff
from mne.time_frequency import induced_power, single_trial_power
from mne.time_frequency.tfr import cwt_morlet

raw_fname = op.join(op.dirname(__file__), '..', '..', 'fiff', 'tests', 'data',
                'test_raw.fif')
event_fname = op.join(op.dirname(__file__), '..', '..', 'fiff', 'tests', 'data',
                'test-eve.fif')

def test_time_frequency():
    """Test time frequency transform (PSD and phase lock)
    """
    # Set parameters
    event_id = 1
    tmin = -0.2
    tmax = 0.5

    # Setup for reading the raw data
    raw = fiff.Raw(raw_fname)
    events = mne.read_events(event_fname)

    include = []
    exclude = raw.info['bads'] + ['MEG 2443', 'EEG 053'] # bads + 2 more

    # picks MEG gradiometers
    picks = fiff.pick_types(raw.info, meg='grad', eeg=False,
                                    stim=False, include=include, exclude=exclude)

    picks = picks[:2]
    epochs = mne.Epochs(raw, events, event_id, tmin, tmax, picks=picks,
                        baseline=(None, 0))
    data = epochs.get_data()
    times = epochs.times

    frequencies = np.arange(6, 20, 5) # define frequencies of interest
    Fs = raw.info['sfreq'] # sampling in Hz
    power, phase_lock = induced_power(data, Fs=Fs, frequencies=frequencies,
                                       n_cycles=2, use_fft=True)

    assert power.shape == (len(picks), len(frequencies), len(times))
    assert power.shape == phase_lock.shape
    assert np.sum(phase_lock >= 1) == 0
    assert np.sum(phase_lock <= 0) == 0

    power, phase_lock = induced_power(data, Fs=Fs, frequencies=frequencies,
                                       n_cycles=2, use_fft=False)

    assert power.shape == (len(picks), len(frequencies), len(times))
    assert power.shape == phase_lock.shape
    assert np.sum(phase_lock >= 1) == 0
    assert np.sum(phase_lock <= 0) == 0

    tfr = cwt_morlet(data[0], Fs, frequencies, use_fft=True, n_cycles=2)
    assert tfr.shape == (len(picks), len(frequencies), len(times))

    single_power = single_trial_power(data, Fs, frequencies, use_fft=False,
                                      n_cycles=2)

    assert_array_almost_equal(np.mean(single_power), power)

