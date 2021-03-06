# Authors: Alexandre Gramfort <gramfort@nmr.mgh.harvard.edu>
#          Matti Hamalainen <msh@nmr.mgh.harvard.edu>
#
# License: BSD (3-clause)

import numpy as np

from .open import fiff_open
from .tree import dir_tree_find, copy_tree
from .constants import FIFF
from .tag import read_tag
from .proj import read_proj, write_proj
from .ctf import read_ctf_comp, write_ctf_comp
from .channels import _read_bad_channels

from .write import start_block, end_block, \
                   write_float, write_int, write_coord_trans, write_ch_info, \
                   write_dig_point, write_name_list


def read_meas_info(fid, tree):
    """Read the measurement info

    Parameters
    ----------
    fid: file
        Open file descriptor

    tree: tree
        FIF tree structure

    Returns
    -------
    info: dict
       Info on dataset

    meas: dict
        Node in tree that contains the info.

    """
    #   Find the desired blocks
    meas = dir_tree_find(tree, FIFF.FIFFB_MEAS)
    if len(meas) == 0:
        raise ValueError('Could not find measurement data')
    if len(meas) > 1:
        raise ValueError('Cannot read more that 1 measurement data')
    meas = meas[0]

    meas_info = dir_tree_find(meas, FIFF.FIFFB_MEAS_INFO)
    if len(meas_info) == 0:
        raise ValueError('Could not find measurement info')
    if len(meas_info) > 1:
        raise ValueError('Cannot read more that 1 measurement info')
    meas_info = meas_info[0]

    #   Read measurement info
    dev_head_t = None
    ctf_head_t = None
    meas_date = None
    highpass = None
    lowpass = None
    nchan = None
    sfreq = None
    chs = []
    p = 0
    for k in range(meas_info.nent):
        kind = meas_info.directory[k].kind
        pos = meas_info.directory[k].pos
        if kind == FIFF.FIFF_NCHAN:
            tag = read_tag(fid, pos)
            nchan = int(tag.data)
        elif kind == FIFF.FIFF_SFREQ:
            tag = read_tag(fid, pos)
            sfreq = tag.data
        elif kind == FIFF.FIFF_CH_INFO:
            tag = read_tag(fid, pos)
            chs.append(tag.data)
            p += 1
        elif kind == FIFF.FIFF_LOWPASS:
            tag = read_tag(fid, pos)
            lowpass = tag.data
        elif kind == FIFF.FIFF_HIGHPASS:
            tag = read_tag(fid, pos)
            highpass = tag.data
        elif kind == FIFF.FIFF_MEAS_DATE:
            tag = read_tag(fid, pos)
            meas_date = tag.data
        elif kind == FIFF.FIFF_COORD_TRANS:
            tag = read_tag(fid, pos)
            cand = tag.data
            if cand['from'] == FIFF.FIFFV_COORD_DEVICE and \
                                cand['to'] == FIFF.FIFFV_COORD_HEAD:
                dev_head_t = cand
            elif cand['from'] == FIFF.FIFFV_MNE_COORD_CTF_HEAD and \
                                cand['to'] == FIFF.FIFFV_COORD_HEAD:
                ctf_head_t = cand

    # Check that we have everything we need
    if nchan is None:
        raise ValueError('Number of channels in not defined')

    if sfreq is None:
        raise ValueError('Sampling frequency is not defined')

    if len(chs) == 0:
        raise ValueError('Channel information not defined')

    if len(chs) != nchan:
        raise ValueError('Incorrect number of channel definitions found')

    if dev_head_t is None or ctf_head_t is None:
        hpi_result = dir_tree_find(meas_info, FIFF.FIFFB_HPI_RESULT)
        if len(hpi_result) == 1:
            hpi_result = hpi_result[0]
            for k in range(hpi_result.nent):
                kind = hpi_result.directory[k].kind
                pos = hpi_result.directory[k].pos
                if kind == FIFF.FIFF_COORD_TRANS:
                    tag = read_tag(fid, pos)
                    cand = tag.data
                    if cand['from'] == FIFF.FIFFV_COORD_DEVICE and \
                                cand['to'] == FIFF.FIFFV_COORD_HEAD:
                        dev_head_t = cand
                    elif cand['from'] == FIFF.FIFFV_MNE_COORD_CTF_HEAD and \
                                cand['to'] == FIFF.FIFFV_COORD_HEAD:
                        ctf_head_t = cand

    #   Locate the Polhemus data
    isotrak = dir_tree_find(meas_info, FIFF.FIFFB_ISOTRAK)
    if len(isotrak):
        isotrak = isotrak[0]
    else:
        if len(isotrak) == 0:
            raise ValueError('Isotrak not found')
        if len(isotrak) > 1:
            raise ValueError('Multiple Isotrak found')

    dig = []
    if len(isotrak) == 1:
        for k in range(isotrak.nent):
            kind = isotrak.directory[k].kind
            pos = isotrak.directory[k].pos
            if kind == FIFF.FIFF_DIG_POINT:
                tag = read_tag(fid, pos)
                dig.append(tag.data)
                dig[-1]['coord_frame'] = FIFF.FIFFV_COORD_HEAD

    #   Locate the acquisition information
    acqpars = dir_tree_find(meas_info, FIFF.FIFFB_DACQ_PARS)
    acq_pars = None
    acq_stim = None
    if len(acqpars) == 1:
        acqpars = acqpars[0]
        for k in range(acqpars.nent):
            kind = acqpars.directory[k].kind
            pos = acqpars.directory[k].pos
            if kind == FIFF.FIFF_DACQ_PARS:
                tag = read_tag(fid, pos)
                acq_pars = tag.data
            elif kind == FIFF.FIFF_DACQ_STIM:
                tag = read_tag(fid, pos)
                acq_stim = tag.data

    #   Load the SSP data
    projs = read_proj(fid, meas_info)

    #   Load the CTF compensation data
    comps = read_ctf_comp(fid, meas_info, chs)

    #   Load the bad channel list
    bads = _read_bad_channels(fid, meas_info)

    #
    #   Put the data together
    #
    if tree.id is not None:
        info = dict(file_id=tree.id)
    else:
        info = dict(file_id=None)

    #  Make the most appropriate selection for the measurement id
    if meas_info.parent_id is None:
        if meas_info.id is None:
            if meas.id is None:
                if meas.parent_id is None:
                    info['meas_id'] = info.file_id
                else:
                    info['meas_id'] = meas.parent_id
            else:
                info['meas_id'] = meas.id
        else:
            info['meas_id'] = meas_info.id
    else:
        info['meas_id'] = meas_info.parent_id

    if meas_date is None:
        info['meas_date'] = [info['meas_id']['secs'], info['meas_id']['usecs']]
    else:
        info['meas_date'] = meas_date

    info['nchan'] = nchan
    info['sfreq'] = sfreq
    info['highpass'] = highpass if highpass is not None else 0
    info['lowpass'] = lowpass if lowpass is not None else info['sfreq'] / 2.0

    #   Add the channel information and make a list of channel names
    #   for convenience
    info['chs'] = chs
    info['ch_names'] = [ch.ch_name for ch in chs]

    #
    #  Add the coordinate transformations
    #
    info['dev_head_t'] = dev_head_t
    info['ctf_head_t'] = ctf_head_t
    if dev_head_t is not None and ctf_head_t is not None:
        info['dev_ctf_t'] = info['dev_head_t']
        info['dev_ctf_t']['to'] = info['ctf_head_t']['from']
        info['dev_ctf_t']['trans'] = np.dot(np.inv(ctf_head_t['trans']),
                                        info['dev_ctf_t']['trans'])
    else:
        info['dev_ctf_t'] = []

    #   All kinds of auxliary stuff
    info['dig'] = dig
    info['bads'] = bads
    info['projs'] = projs
    info['comps'] = comps
    info['acq_pars'] = acq_pars
    info['acq_stim'] = acq_stim

    return info, meas


def write_meas_info(fid, info):
    """Write measurement info in fif file."""

    # Measurement info
    start_block(fid, FIFF.FIFFB_MEAS_INFO)

    # Blocks from the original
    blocks = [FIFF.FIFFB_SUBJECT, FIFF.FIFFB_HPI_MEAS, FIFF.FIFFB_HPI_RESULT,
              FIFF.FIFFB_ISOTRAK, FIFF.FIFFB_PROCESSING_HISTORY]

    have_hpi_result = False
    have_isotrak = False

    if len(blocks) > 0 and 'filename' in info and \
            info['filename'] is not None:
        fid2, tree, _ = fiff_open(info['filename'])
        for block in blocks:
            nodes = dir_tree_find(tree, block)
            copy_tree(fid2, tree['id'], nodes, fid)
            if block == FIFF.FIFFB_HPI_RESULT and len(nodes) > 0:
                have_hpi_result = True
            if block == FIFF.FIFFB_ISOTRAK and len(nodes) > 0:
                have_isotrak = True
        fid2.close()

    #   General
    write_float(fid, FIFF.FIFF_SFREQ, info['sfreq'])
    write_float(fid, FIFF.FIFF_HIGHPASS, info['highpass'])
    write_float(fid, FIFF.FIFF_LOWPASS, info['lowpass'])
    write_int(fid, FIFF.FIFF_NCHAN, info['nchan'])
    if info['meas_date'] is not None:
        write_int(fid, FIFF.FIFF_MEAS_DATE, info['meas_date'])

    #   Coordinate transformations if the HPI result block was not there
    if not have_hpi_result:
        if info['dev_head_t'] is not None:
            write_coord_trans(fid, info['dev_head_t'])

        if info['ctf_head_t'] is not None:
            write_coord_trans(fid, info['ctf_head_t'])

    #  Channel information
    for k in range(info['nchan']):
        #   Scan numbers may have been messed up
        info['chs'][k]['scanno'] = k + 1
        write_ch_info(fid, info['chs'][k])

    #   Polhemus data
    if info['dig'] is not None and not have_isotrak:
        start_block(fid, FIFF.FIFFB_ISOTRAK)
        for d in info['dig']:
            write_dig_point(fid, d)

        end_block(fid, FIFF.FIFFB_ISOTRAK)

    #   Projectors
    write_proj(fid, info['projs'])

    #   CTF compensation info
    write_ctf_comp(fid, info['comps'])

    #   Bad channels
    if len(info['bads']) > 0:
        start_block(fid, FIFF.FIFFB_MNE_BAD_CHANNELS)
        write_name_list(fid, FIFF.FIFF_MNE_CH_NAME_LIST, info['bads'])
        end_block(fid, FIFF.FIFFB_MNE_BAD_CHANNELS)

    end_block(fid, FIFF.FIFFB_MEAS_INFO)
