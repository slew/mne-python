"""
==============================================
Estimate covariance matrix from a raw FIF file
==============================================

"""
# Author: Alexandre Gramfort <gramfort@nmr.mgh.harvard.edu>
#
# License: BSD (3-clause)

print __doc__

import mne
from mne import fiff
from mne.datasets import sample

data_path = sample.data_path('.')
fname = data_path + '/MEG/sample/sample_audvis_raw.fif'

raw = fiff.Raw(fname)

# Set up pick list: MEG + STI 014 - bad channels
cov = mne.compute_raw_data_covariance(raw, reject=dict(eeg=40e-6, eog=150e-6))
print cov

###############################################################################
# Show covariance
import pylab as pl
pl.figure()
pl.imshow(cov.data, interpolation="nearest")
pl.title('Full covariance matrix')
pl.show()
