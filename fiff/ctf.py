import numpy as np

from .constants import FIFF
from .tag import find_tag, has_tag, read_tag
from .tree import dir_tree_find


def hex2dec(s):
    return int(s, 16)


def read_named_matrix(fid, node, matkind):
    """
    %
    % [mat] = fiff_read_named_matrix(fid,node)
    %
    % Read named matrix from the given node
    %
    """

    #   Descend one level if necessary
    if node.block != FIFF.FIFFB_MNE_NAMED_MATRIX:
        for k in range(node.nchild):
            if node.children(k).block == FIFF.FIFFB_MNE_NAMED_MATRIX:
                if has_tag(node.children(k), matkind):
                    node = node.children(k);
                    break;
        else:
            raise ValueError, 'Desired named matrix (kind = %d) not available' % matkind

    else:
       if not has_tag(node,matkind):
          raise 'Desired named matrix (kind = %d) not available' % matkind

    #   Read everything we need
    tag = find_tag(fid, node, matkind)
    if tag is None:
       raise ValueError, 'Matrix data missing'
    else:
       data = tag.data;

    nrow, ncol = data.shape
    tag = find_tag(fid, node, FIFF.FIFF_MNE_NROW)
    if tag is not None:
       if tag.data != nrow:
          raise ValueError, 'Number of rows in matrix data and FIFF_MNE_NROW tag do not match'

    tag = find_tag(fid, node, FIFF.FIFF_MNE_NCOL)
    if tag is not None:
       if tag.data != ncol:
          raise ValueError, 'Number of columns in matrix data and FIFF_MNE_NCOL tag do not match'

    tag = find_tag(fid, node, FIFF.FIFF_MNE_ROW_NAMES)
    if tag is not None:
        row_names = tag.data;
    else:
        row_names = None

    tag = find_tag(fid, node, FIFF.FIFF_MNE_COL_NAMES)
    if tag is not None:
        col_names = tag.data;
    else:
        col_names = None

    #   Put it together
    mat = dict(nrow=nrow, ncol=ncol)
    if row_names is not None:
        mat['row_names'] = row_names.split(':')
    else:
        mat['row_names'] = None

    if col_names is not None:
        mat['col_names'] = col_names.split(':')
    else:
        mat['col_names'] = None

    mat['data'] = data;
    return mat


def read_ctf_comp(fid, node, chs):
    """
    %
    % [ compdata ] = fiff_read_ctf_comp(fid,node,chs)
    %
    % Read the CTF software compensation data from the given node
    %
    """

    compdata = []
    comps = dir_tree_find(node, FIFF.FIFFB_MNE_CTF_COMP_DATA)

    for node in comps:

        #   Read the data we need
        mat  = read_named_matrix(fid, node, FIFF.FIFF_MNE_CTF_COMP_DATA)
        for p in range(node.nent):
            kind = node.dir[p].kind
            pos  = node.dir[p].pos
            if kind == FIFF.FIFF_MNE_CTF_COMP_KIND:
                tag = read_tag(fid,pos)
                break
        else:
            raise ValueError, 'Compensation type not found'

        #   Get the compensation kind and map it to a simple number
        one = dict(ctfkind=tag.data, kind=-1)
        del tag

        if one.ctfkind == hex2dec('47314252'):
            one.kind = 1
        elif one.ctfkind == hex2dec('47324252'):
            one.kind = 2
        elif one.ctfkind == hex2dec('47334252'):
            one.kind = 3
        else:
            one.kind = one.ctfkind

        for p in range(node.nent):
            kind = node.dir[p].kind
            pos  = node.dir[p].pos
            if kind == FIFF.FIFF_MNE_CTF_COMP_CALIBRATED:
                tag = read_tag(fid,pos)
                calibrated = tag.data
                break
        else:
            calibrated = False

        one['save_calibrated'] = calibrated;
        one['rowcals'] = np.ones(1, mat.shape[0])
        one['colcals'] = np.ones(1, mat.shape[1])
        if not calibrated:
            #
            #   Calibrate...
            #
            #   Do the columns first
            #
            ch_names = []
            for p in range(len(chs)):
                ch_names.append(chs[p].ch_name)

            col_cals = np.zeros(mat.data.shape[1])
            for col in range(mat.data.shape[1]):
                p = ch_names.count(mat.col_names[col])
                if p == 0:
                    raise ValueError, 'Channel %s is not available in data' % mat.col_names[col]
                elif p > 1:
                    raise ValueError, 'Ambiguous channel %s' % mat.col_names[col]

                col_cals[col] = 1.0 / (chs[p].range * chs[p].cal)

            #    Then the rows
            row_cals = np.zeros(mat.data.shape[0])
            for row in range(mat.data.shape[0]):
                p = ch_names.count(mat.row_names[row])
                if p == 0:
                    raise ValueError, 'Channel %s is not available in data', mat.row_names[row]
                elif p > 1:
                    raise ValueError, 'Ambiguous channel %s' % mat.row_names[row]

                row_cals[row] = chs[p].range * chs[p].cal

            mat.data = np.dot(np.diag(row_cals), np.dot(mat.data, np.diag(col_cals)))
            one.rowcals = row_cals
            one.colcals = col_cals

        one.data = mat
        compdata.append(one)
        del row_cals
        del col_cals

    if len(compdata) > 0:
        print '\tRead %d compensation matrices\n' % len(compdata)

    return compdata