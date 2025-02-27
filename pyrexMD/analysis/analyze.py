# @Author: Arthur Voronin
# @Date:   17.04.2021
# @Filename: analysis.py
# @Last modified by:   arthur
# @Last modified time: 08.04.2022

"""
.. hint:: This module contains various functions for basic trajectory analyses,
    e.g., calculating RMSDs, distances, etc.

Example:
--------

.. code-block:: python

    import MDAnalysis as mda
    import pyrexMD.topology as top
    import pyrexMD.analysis.analyze as ana

    ref = mda.Universe("path/to/pdb")
    mobile = mda.Universe("path/to/tpr", "path/to/xtc")

    # get RMSD
    top.norm_and_align_universe(mobile, ref)
    FRAME, TIME, RMSD = ana.get_RMSD(mobile, ref)

    # plot
    ana.PLOT(xdata=FRAME, ydata=RMSD, alpha=1, marker=None, xlabel="frame", ylabel=r"RMSD ($\AA$)")

Content:
--------
"""

import pyrexMD.misc as _misc
import pyrexMD.topology as _top
from pyrexMD.misc import get_PDBid
from tqdm.notebook import tqdm
from Bio.PDB import PDBParser, Polypeptide
from MDAnalysis.analysis import distances as _distances, rms as _rms, align as _align
import MDAnalysis as mda
import numpy as np
import seaborn as sns
import matplotlib
import matplotlib.pyplot as plt
import operator
import os
import glob
import logging
import warnings
logging.getLogger('matplotlib.font_manager').disabled = True

# global update for plots
cp = sns.color_palette()  # access seaborn colors via cp[0] - cp[9]


################################################################################
################################################################################
def get_time_conversion(u, **kwargs):
    """
    get/print time conversion of MDA universe <u>

    Args:
        u (universe)

    .. Hint:: Args and Keyword Args of misc.cprint() are valid Keyword Args.
    """
    if isinstance(u, mda.core.universe.Universe):
        dt = u.trajectory.dt
        tu = u.trajectory.units["time"]

        if tu == "ps":
            _misc.cprint(f"Time = Frame * {dt} {tu} = Frame * {0.001*dt} ns")
        elif tu == "ns":
            _misc.cprint(f"Time=Frame * {dt} {tu}")
    else:
        raise TypeError("type(u) must be MDAnalysis.core.universe.Universe.")
    return


def get_FASTA(pdb_file, verbose=True):
    """
    get FASTA sequence for each polypeptide of pdb_file

    Args:
        pdb_file (str): path to pdb_file
        verbose (bool): print sequences

    Returns:
        FASTA (list)
            list with FASTA sequences (one per polypeptide)
    """
    structure = PDBParser().get_structure("pdb_label", pdb_file)  # label not required
    ppb = Polypeptide.PPBuilder()

    FASTA = []
    for ndx, pp in enumerate(ppb.build_peptides(structure)):
        if verbose:
            print(f"Polypeptide {ndx+1} FASTA: {pp.get_sequence()}")
        FASTA.append("".join(pp.get_sequence()))
    return FASTA


################################################################################
################################################################################


def alignto(mobile, ref, sel1, sel2, weights='mass', tol_mass=0.1, strict=False):
    """
    Modified version of MDAnalysis.analysis.align.alignto() which works properly
    with two different selection strings.

    Description:
        Perform a spatial superposition by minimizing the RMSD.

        Spatially align the group of atoms `mobile` to `reference` by doing a
        RMSD fit on `sel1` of mobile atoms and `sel1` of referece atoms.

        The superposition is done in the following way:

        1. A rotation matrix is computed that minimizes the RMSD between
           the coordinates of `mobile.select_atoms(sel1)` and
           `reference.select_atoms(sel2)`; before the rotation, `mobile` is
           translated so that its center of geometry (or center of mass)
           coincides with the one of `reference`. (See below for explanation of
           how *sel1* and *sel2* are derived from `select`.)
        2. All atoms in :class:`~MDAnalysis.core.universe.Universe` that
           contain `mobile` are shifted and rotated. (See below for how
           to change this behavior through the `subselection` keyword.)

    Args:
        mobile (universe): mobile structure
        ref (universe): reference structure
        sel1 (str): selection string of mobile structure
        sel2 (str): selection string of reference structure
        weights (None, str, array):
          | None: weigh each atom equally
          | "mass": weigh atoms based on mass
          | array: If a float array of the same length as `mobile` is provided,
            use each element of the `array_like` as a weight for the corresponding
            atom in `mobile`.
        tol_mass (float): Reject match if the atomic masses for matched atoms
            differ by more than `tol_mass`, default [0.1]
        strict (bool):
          | True: Will raise :exc:`SelectionError` if a single atom does not
            match between the two selections.
          | False:  Will try to prepare a matching selection by dropping residues
            with non-matching atoms.

    Returns:
        old_rmsd (float)
            RMSD before spatial alignment
        new_rmsd (float)
            RMSD after spatial alignment
    """
    mobile_atoms = mobile.select_atoms(sel1)
    ref_atoms = ref.select_atoms(sel2)
    mobile_atoms, ref_atoms = _align.get_matching_atoms(mobile_atoms, ref_atoms,
                                                        tol_mass=tol_mass,
                                                        strict=strict)

    weights = _align.get_weights(ref_atoms, weights)
    mobile_com = mobile_atoms.center(weights)
    ref_com = ref_atoms.center(weights)

    mobile_coordinates = mobile_atoms.positions - mobile_com
    ref_coordinates = ref_atoms.positions - ref_com

    old_rmsd = _rms.rmsd(mobile_coordinates, ref_coordinates, weights)
    # _fit_to DOES subtract center of mass, will provide proper min_rmsd
    mobile_atoms, new_rmsd = _align._fit_to(mobile_coordinates, ref_coordinates,
                                            mobile_atoms, mobile_com, ref_com,
                                            weights=weights)
    return old_rmsd, new_rmsd


def get_rmsd(mobile, ref, sel1, sel2, prec=3, weights='mass', superposition=True):
    """
    Returns rmsd for single frame.

    Args:
        mobile (universe, atomgrp): mobile structure
        ref (universe, atomgrp): reference structure
        sel1 (str): selection string of mobile structure
        sel2 (str): selection string of reference structure
        prec (None, int): rounding precission
        weights (bool, str, array_like):
          | weights during superposition of mobile and reference
          | None: no weights
          | "mass": atom masses as weights
          | array_like: If a float array of the same length as "mobile" is
            provided, use each element of the "array_like" as a weight for the
            corresponding atom in "mobile".
        superposition (bool)

    Returns:
        rmsd (float)
            rmsd value in Å
    """
    mobile_atoms = mobile.select_atoms(sel1)
    ref_atoms = ref.select_atoms(sel2)
    rmsd = _rms.rmsd(mobile_atoms.positions, ref_atoms.positions, superposition=superposition)
    return round(rmsd, prec)


def get_RMSD(mobile, ref, sel1, sel2, sss=[None, None, None], prec=3,
             weights='mass', superposition=True, plot=False, verbose=True, **kwargs):
    """
    Returns rmsd for multiple frames.

    Args:
        mobile (universe, atomgrp): mobile structure
        ref (universe, atomgrp): reference structure
        sel1 (str): selection string of mobile structure
        sel2 (str): selection string of reference structure
        sss (list):
          | [start, stop, step]
          | start (None, int): start frame
          | stop (None, int): stop frame
          | step (None, int): step size
        prec (None, int): rounding precission
        weights (bool, str, array_like):
          | weights during superposition of mobile and reference
          | None: no weights
          | "mass": atom masses as weights
          | array_like: If a float array of the same length as "mobile" is
            provided, use each element of the "array_like" as a weight for the
            corresponding atom in "mobile".
        superposition (bool)
        plot (bool)

    .. Hint:: Args and Keyword Args of analysis.PLOT() are valid Keyword Args.

    Returns:
        FRAME (array)
            frame array
        TIME (array)
            time array in ps
        RMSD (array)
            rmsd array in Å
    """
    default = {"start": sss[0],
               "stop": sss[1],
               "step": sss[2]}
    cfg = _misc.CONFIG(default, **kwargs)
    ############################################################################
    FRAME, TIME, RMSD = [], [], []
    for ts in tqdm(mobile.trajectory[cfg.start:cfg.stop:cfg.step], disable=not verbose):
        FRAME.append(ts.frame)
        TIME.append(ts.time)
        RMSD.append(get_rmsd(mobile, ref, sel1=sel1, sel2=sel2, prec=prec, weights=weights, superposition=superposition))

    FRAME, TIME, RMSD = np.array(FRAME), np.array(TIME), np.array(RMSD)

    if plot:
        #PLOT(xdata=FRAME, ydata=RMSD, xlabel='Frame', ylabel=f'RMSD ($\AA$)', **kwargs)
        PLOT(xdata=TIME, ydata=RMSD, xlabel='Time (ps)', ylabel=f'RMSD ($\AA$)', **kwargs)
    return FRAME, TIME, RMSD


def get_RMSF(mobile, sel='protein and name CA', plot=False, **kwargs):
    """
    Calculates the RMSF of mobile. Alias function of MDAnalysis.analysis.rms.RMSF.
    See help(MDAnalysis.analysis.rms.get_RMSF) for more information.

    Args:
        mobile (universe, atomgrp): mobile structure
        sel (str): selection string
        plot (bool): create plot

    Returns:
        RMSF (array)
            array with RMSD values
    """
    ############################################################################
    default = {"xlabel": "RESID",
               "ylabel": r"RMSF ($\AA$)",
               }
    cfg = _misc.CONFIG(default, **kwargs)
    ############################################################################
    if not isinstance(mobile, (mda.core.universe.Universe, mda.core.groups.AtomGroup)):
        raise TypeError(f'''{get_RMSF.__module__}.{get_RMSF.__name__}():\
        \nmobile be MDA universe or atomgrp!''')

    else:
        RMSF = _rms.RMSF(mobile.select_atoms(sel))
        RMSF.run()
        rmsf = RMSF.rmsf

    if plot:
        if 'name CA' in sel:
            PLOT(xdata=mobile.select_atoms(sel).resids, ydata=rmsf, **cfg)

        else:
            cfg.xlabel = "Atom ID"
            PLOT(xdata=mobile.select_atoms(sel).ids, ydata=rmsf, **cfg)

    return rmsf


def _HELP_sss_None2int(obj, cfg):
    """
    Converts None entries of the config keys to integers:
        sss = [None, None, None] -> [0, max frame of MDA universe, 1]
        start = None ->  0
        stop = None ->  max frame of u
        step = None ->  1

    Note:
        this function is (probably) required when a custom function uses either
        a MDA universe or (distance)matrix and a misc.CONFIG class with the keys
        "sss", "start", "stop", "step".

    Reason:
        slicing: aList[None:None:None] is equal to aList[::]
        get item: aList[None] does not exist

    Args:
        obj (universe, matrix): MDA universe or distance(matrix)
        cfg (misc.CONFIG class)

    Returns:
        cfg (misc.CONFIG class)
    """
    if isinstance(obj, mda.core.universe.Universe):
        if "sss" in cfg.keys():
            if cfg.sss[0] == None:
                cfg.sss[0] = 0
            if cfg.sss[1] == None:
                cfg.sss[1] = obj.trajectory.n_frames
            if cfg.sss[2] == None:
                cfg.sss[2] = 1

        if "start" in cfg.keys() or "stop" in cfg.keys() or "step" in cfg.keys():
            if cfg.start == None:
                cfg.start = 0
            if cfg.stop == None:
                cfg.stop = obj.trajectory.n_frames
            if cfg.step == None:
                cfg.step = 1

    elif isinstance(obj, (np.ndarray, list)):
        if "sss" in cfg.keys():
            if cfg.sss[0] == None:
                cfg.sss[0] = 0
            if cfg.sss[1] == None:
                cfg.sss[1] = len(obj)
            if cfg.sss[2] == None:
                cfg.sss[2] = 1

        if "start" in cfg.keys() or "stop" in cfg.keys() or "step" in cfg.keys():
            if cfg.start == None:
                cfg.start = 0
            if cfg.stop == None:
                cfg.stop = len(obj)
            if cfg.step == None:
                cfg.step = 1
    return cfg


def get_Distance_Matrices(mobile, sel="protein and name CA", sss=[None, None, None],
                          flatten=False, verbose=True, **kwargs):
    """
    Calculate distance matrices for mobile and return them.

    Args:
        mobile (universe, list):
          | (MDA universe): structure with trajectory
          | (list): list with paths to structure files (.pdb)
        sel (str): selection string
        sss (list):
          | [start, stop, step]
          | start (None, int): start frame
          | stop (None, int): stop frame
          | step (None, int): step size
        flatten (bool): return flattened distance matrices
        verbose (bool): show progress bar

    Keyword Args:
        dtype (dtype): float (default)
        start (None, int): start frame
        stop (None, int): stop frame
        step (None, int): step size

    Returns:
        DM (array)
            array of distance matrices
    """
    ############################################################################
    default = {"dtype": float,
               "start": sss[0],
               "stop": sss[1],
               "step": sss[2]
               }
    cfg = _misc.CONFIG(default, **kwargs)
    cfg = _HELP_sss_None2int(mobile, cfg)  # convert None values of they keys sss, start, stop, step to integers
    ############################################################################
    # mobile is MDA universe
    if isinstance(mobile, mda.Universe):
        a = mobile.select_atoms(sel)
        DM = np.empty((len(mobile.trajectory[cfg.start:cfg.stop:cfg.step]),
                       a.n_atoms*a.n_atoms), dtype=cfg.dtype)  # tuple args: length, size (of flattened array)

        for i, ts in enumerate(tqdm(mobile.trajectory[cfg.start:cfg.stop:cfg.step], disable=not verbose)):
            DM[i] = mda.analysis.distances.distance_array(a.positions, a.positions).flatten()
        if not flatten:
            DM = DM.reshape((len(mobile.trajectory[cfg.start:cfg.stop:cfg.step]),
                             a.n_atoms, a.n_atoms))  # tuple args: length, N_CA, N_CA

    # mobile is list with pdb files
    elif isinstance(mobile, list):
        for pdb_file in mobile:
            if _misc.get_extension(pdb_file) != ".pdb":
                print(f"Extension test of: {pdb_file}")
                raise TypeError('<mobile> is passed as list but does not contain .pdb file paths.')
        u = mda.Universe(mobile[0])
        a = u.select_atoms(sel)
        DM = np.empty((len(mobile), a.n_atoms*a.n_atoms), dtype=cfg.dtype)  # tuple args: length, size (of flattened array)

        for i, pdb_file in enumerate(tqdm(mobile, disable=not verbose)):
            u = mda.Universe(pdb_file)
            a = u.select_atoms(sel)
            DM[i] = mda.analysis.distances.distance_array(a.positions, a.positions).flatten()
        if not flatten:
            DM = DM.reshape((len(mobile), a.n_atoms, a.n_atoms))  # tuple args: length, N_CA, N_CA
    return DM
################################################################################
################################################################################


def get_shortest_RES_distances(u, sel):
    """
    Calculates shortest RES distances (current frame) for selection of universe u.

    .. Attention:: Displayed RES ids always start with 1

    Args:
        u (universe, str): structure universe or pdb path
        sel (str): selection string

    Returns:
        SD (arrray)
          | NxN Matrix with shortest RES distances
          | i.e.: SD[0][0] is shortest distance RES0-RES0
          |       SD[0][1] is shortest distance RES0-RES1
          |       SD[0][2] is shortest distance RES0-RES2
          | etc.
        SD_d (array, dtype=object)
            detailed List with [d_min, (RES_pair), (ATM_pair), (ATM_names)]
    """
    if isinstance(u, str):
        # uc: universe copy
        uc = mda.Universe(u)
    elif isinstance(u, mda.Universe):
        # uc: universe copy
        uc = u.copy()
    elif isinstance(u, mda.AtomGroup):
        uc = u.universe.copy()
    _top.norm_resids(uc, verbose=True)
    a = _top.true_select_atoms(uc, sel)
    dim = len(a.residues.resids)
    SD = np.zeros(shape=(dim, dim))
    SD_d = []

    for i in range(dim):
        for j in range(i + 1, dim):
            DA = _distances.distance_array(a.residues[i].atoms.positions, a.residues[j].atoms.positions)
            d_min = np.min(DA)
            d_min_index = np.unravel_index(np.argmin(DA), DA.shape)  # atom indices

            # write values to list
            RES_pair = (a.residues[i].resid, a.residues[j].resid)
            ATM_pair = (a.residues[i].atoms[d_min_index[0]].id,
                        a.residues[j].atoms[d_min_index[1]].id)
            ATM_names = (a.residues[i].atoms.names[d_min_index[0]],
                         a.residues[j].atoms.names[d_min_index[1]])

            SD[i][j] = d_min
            SD_d.append([d_min, RES_pair, ATM_pair, ATM_names])

        # SD contains only half of the distances (double for loop w/o double counting RES pairs )
        SD_t = np.transpose(SD)    # -> transpose SD
        SD = np.maximum(SD, SD_t)  # -> take element-wise maximum

    # convert to array with dtype=object since array contains lists, tuples and sequences
    SD_d = np.array(SD_d, dtype=object)
    return(SD, SD_d)


################################################################################
################################################################################
### analysis.py plot functions


def get_trendline(xdata, ydata, compress=10):
    """
    Reduces <xdata, ydata> by <compress> factor and returns trendline data.
    (Trendline: sum and normalize each <compress> elements of input data)

    Args:
        xdata (list, array)
        ydata (list, array)
        compress (int): compress factor (sum and normalize <compress> elements)

    Returns:
        trend_xdata (list, array)
            reduced xdata
        trend_ydata (list, array)
            reduced ydata
    """
    if len(xdata) != len(ydata):
        raise ValueError("xdata and ydata have unequal length.")

    trend_xdata = np.add.reduceat(xdata, np.arange(0, len(xdata), compress))/float(compress)
    trend_ydata = np.add.reduceat(ydata, np.arange(0, len(ydata), compress))/float(compress)
    trend_xdata = trend_xdata.tolist()
    trend_ydata = trend_ydata.tolist()

    # fix normalization of last element if data is not fully divisible by compress (ie remainder exists)
    remainder = len(xdata) % compress
    if remainder != 0:
        trend_xdata = trend_xdata[: -1] + [sum(xdata[-remainder:])/float(remainder)]
        trend_ydata = trend_ydata[: -1] + [sum(ydata[-remainder:])/float(remainder)]

    if isinstance(xdata, np.ndarray):
        trend_xdata = np.array(trend_xdata)
    if isinstance(ydata, np.ndarray):
        trend_ydata = np.array(trend_ydata)
    return trend_xdata, trend_ydata


def plot_trendline(xdata, ydata, compress=10, fig=None, remove_previous=True, **kwargs):
    """
    Plot trendline of <xdata, ydata> and return trendline object

    .. Hint:: trendline can be removed via trendline.remove()

    Args:
        xdata (list, array)
        ydata (list, array)
        compress (int): compress factor (sum and normalize <compress> elements)
        fig (int): figure number (get with plt.gcf().number)
        remove_previous (bool): remove previous trendline data

    Keyword Args:
        "alpha": 1.0
        "color": "black"
        "ls": "-"
        "lw": 2.0
        "ms": 1
        "marker" : "."

    Returns:
        trendline (matplotlib.lines.Line2D)
            "trendline" object
    """
    default = {"alpha": 1.0,
               "color": "black",
               "label": None,
               "ls": "-",
               "lw": 2.0,
               "ms": 1,
               "marker": "."}
    cfg = _misc.CONFIG(default, **kwargs)
    #####################################
    # get trendline data
    trend_xdata, trend_ydata = get_trendline(xdata, ydata, compress=compress)

    # use existing figure
    if isinstance(fig, int):
        fig = plt.figure(num=fig)
    elif isinstance(fig, matplotlib.figure.Figure):
        fig = plt.figure(num=fig.number)
    else:
        fig = plt.gcf()

    # remove existing trendline
    if remove_previous:
        try:
            fig.trendline.remove()
            del fig.trendline
        except AttributeError:
            pass  # no trendline found -> do nothing

    # plot new trendline
    trendline = plt.plot(trend_xdata, trend_ydata,
                         alpha=cfg.alpha, color=cfg.color, label=cfg.label,
                         ls=cfg.ls, lw=cfg.lw, ms=cfg.ms, marker=cfg.marker)

    fig.trendline = trendline[0]
    return fig.trendline


def remove_trendline(trendline=None, fig=None):
    """
    remove trendline of figure.

    Args:
        trendline (None, obj): "trendline object"
        fig (None, obj): figure object
    """
    if trendline is not None:
        trendline.remove()
        del trendline
        return
    elif fig is not None:
        fig.trendline.remove()
        del fig.trendline
        return
    elif trendline is None and fig is None:
        fig = plt.gcf()
    try:
        fig.trendline.remove()
        del fig.trendline
    except AttributeError:
        print("Figure has no trendline object.")
    return


def PLOT(xdata, ydata, xlabel='', ylabel='', title='', xlim=None, ylim=None, **kwargs):
    """
    General plot function for analysis.py

    Args:
        xdata (array, list)
        ydata (array, list)
        xlabel (str)
        ylabel (str)
        title (None, str)
        xlim (None, list)
        ylim (None, list)

    Keyword Args:
        alpha (float): 1.0
        color (str): "r"
        lw (float): 1.5
        ms (int): 1
        marker (None, str): None

    .. Hint:: Args and Keyword Args of misc.figure() are also valid.

    Returns:
        fig (class)
            matplotlib.figure.Figure
        ax (class, list)
            ax or list of axes ~ matplotlib.axes._subplots.Axes

    Example:
        | >> PLOT(TIME, RMSD, xlabel="time (ns)", ylabel=r"RMSD ($\AA$)",
        |         title="RMSD plot", xlim=[50, 500], ylim=[0, 20])
    """
    # init CONFIG object with default parameter and overwrite them if kwargs contain the same keywords.
    default = {"alpha": 1.0,
               "color": "r",
               "lw": 1.5,
               "ms": 1,
               "marker": None}
    cfg = _misc.CONFIG(default, **kwargs)
    #####################################
    if isinstance(xdata, range):
        xdata = list(xdata)
    if isinstance(ydata, range):
        ydata = list(ydata)

    fig, ax = _misc.figure(**kwargs)
    cp = sns.color_palette(None)

    _dim_xdata = len(np.shape(xdata))
    if _dim_xdata == 1:
        plt.plot(xdata, ydata, color=cfg.color, ls="", marker=cfg.marker, ms=cfg.ms)
        plt.plot(xdata, ydata, color=cfg.color, lw=cfg.lw, alpha=cfg.alpha)
    else:
        for i in range(len(xdata)):
            j = i % 10  # sns color_palette has usually 10 colors
            plt.plot(xdata[i], ydata[i], color=cp[j], ls="", marker=cfg.marker, ms=cfg.ms)
            plt.plot(xdata[i], ydata[i], color=cp[j], lw=cfg.lw, alpha=cfg.alpha)

    plt.xlabel(xlabel, fontweight="bold")
    plt.ylabel(ylabel, fontweight="bold")
    if title != "" or title != None:
        plt.title(title, fontweight='bold')

    if xlim is not None:
        plt.xlim(xlim[0], xlim[1])
    if ylim is not None:
        plt.ylim(ylim[0], ylim[1])
    plt.tight_layout()
    plt.show()

    return(fig, ax)


def plot_RMSD(RMSD_file, sss=[None, None, None], verbose=None, save_as="", **kwargs):
    """
    plot RMSD curve

    Args:
        RMSD_file (str): path to RMSD file
        sss (list):
          | [start, stop, step]
          | start (None, int): start frame
          | stop (None, int): stop frame
          | step (None, int): step size
        verbose (None, bool):
          | None: print step to user (as a reminder)
          | True: print start, step, stop to user
          | False: no print
        save_as (str): save name or realpath to save file

    Keyword Args:
        alpha (float)
        color (str)
        cut_min (None, int, float): min value for cutoff
        cut_max (None ,int, float): max value for cutoff
        start (None ,int): start frame
        stop (None ,int): stop frame
        step (None ,int): step size
        filedir (str): default directory where to save figure
        title (None/str)

    .. Hint:: Args and Keyword Args of misc.figure() are also valid.

    Returns:
        fig (class)
            matplotlib.figure.Figure
        ax (class, list)
            ax or list of axes ~ matplotlib.axes._subplots.Axes
    """
    #######################################
    # init CONFIG object with default parameter and overwrite them if kwargs contain the same keywords.
    default = {"alpha": 0.3,
               "color": "r",
               "lw": 1.5,
               "ms": 4,
               "marker": ".",
               "start": sss[0],
               "stop": sss[1],
               "step": sss[2],
               "cut_min": None,
               "cut_max": None,
               "title": None}
    cfg = _misc.CONFIG(default, **kwargs)

    if verbose == None:
        print("Plottinig data with stepsize of", cfg.step)
    elif verbose == True:
        print("Plotting data with parameter values:")
        print("\tstart:", cfg.start)
        print("\tstop:", cfg.stop)
        print("\tstep:", cfg.step)
    header = _misc.autodetect_header(RMSD_file)

    TIME = np.loadtxt(RMSD_file, skiprows=header, usecols=(0,))
    TIME = [round(x, 3) for x in TIME[cfg.start:cfg.stop:cfg.step]]
    RMSD = np.loadtxt(RMSD_file, skiprows=header, usecols=(1,))
    RMSD = RMSD[cfg.start: cfg.stop: cfg.step]

    # apply cutoff and force same dimensions by tracking indices
    if cfg.cut_min is not None or cfg.cut_max is not None:
        RMSD, RMSD_ndx = _misc.get_cutoff_array(RMSD, cfg.cut_min, cfg.cut_max)
        TIME = _misc.get_subarray(TIME, RMSD_ndx)

    # plot
    fig, ax = _misc.figure(**cfg)
    plt.plot(TIME, RMSD,
             color=cfg.color, ls="", marker=cfg.marker, ms=cfg.ms)
    plt.plot(TIME, RMSD,
             color=cfg.color, lw=cfg.lw, alpha=cfg.alpha)

    if cfg.title is not None:
        plt.title(cfg.title, fontweight='bold')

    plt.tight_layout()
    plt.show()

    if save_as != "":
        if "filedir" in kwargs:
            _misc.savefig(filename=save_as, filedir=kwargs["filedir"])
        else:
            _misc.savefig(filename=save_as)
        plt.savefig(save_as, dpi=300)

    return(fig, ax)


def _HELP_setup_bins(data, vmin=None, vmax=None, vbase=1, bins=None, n_bins=200, n_bins_autoadd=1):
    """
    HELP function to setup bins for histogram. Returns a dictionary to update
    important cfg parameter, such as vmin, vmax.

    Args:
        data (array, list)
        vmin (None, int, float): min value of histogram/bins
        vmax (None, int, float): max value of histogram/bins
        vbase (int): r
          | rounding base of vmin, vmax.
          | look up misc.round_down(number,base) or misc.round_up(number,base)
        bins (None, list): use bins if passed, else construct bins based on
          n_bins, vmin, vmax, vbase
        n_bins (int): number of bins
        n_bins_autoadd (int): autocorrect n_bins (default: 1), because hist
          usually require 1 extra bin

    Returns
        bins (list)
            list with bins
        bins_step (int, float)
            bins step size
        cfg (dict)
            | dictionary containing the current values of:
            | vmin, vmax, vbase, bins, n_bins, n_bins_autoadd
    """
    # init CONFIG object with default parameter and overwrite them if kwargs contain the same keywords.
    default = dict(vmin=vmin, vmax=vmax, vbase=vbase,
                   bins=bins, n_bins=n_bins, n_bins_autoadd=n_bins_autoadd)
    cfg = _misc.CONFIG(default)

    if cfg.vmin is None:
        min_ = min(_misc.flatten_array(data))
        cfg.vmin = _misc.round_down(min_, cfg.vbase)
    if cfg.vmax is None:
        max_ = max(_misc.flatten_array(data))
        cfg.vmax = _misc.round_up(max_, cfg.vbase)
    if cfg.bins is None:
        cfg.bins = np.linspace(cfg.vmin, cfg.vmax, cfg.n_bins+cfg.n_bins_autoadd)
        bins = cfg.bins
        bins_step = cfg.bins[1]-cfg.bins[0]
    else:
        bins = cfg.bins
        bins_step = cfg.bins[1]-cfg.bins[0]
        cfg.n_bins = len(bins)-1
    return(bins, bins_step, cfg)


def plot_hist(data, sss=[None, None, None], save_as=None, **kwargs):
    """
    plot histogram

    Args:
        data (list, array, list of lists): input data. Dimensions of each list
          must be equal if multiple lists are provided.
        sss (list):
          | [start, stop, step]
          | start (None, int): start frame
          | stop (None, int): stop frame
          | step (None, int): step size
        save_as (str): save name or realpath to save file

    Keyword Args:
        start (None, int): start frame
        stop (None, int): stop frame
        step (None, int): step size
        cut_min (None, int, float): min value for cutoff
        cut_max (None, int, float): max value for cutoff
        apply_cut_limits (bool):
          | apply plt.xlim(cut_min, cut_max) if orientation is "vertical"
          | apply plt.ylim(cut_min, cut_max) if orientation is "horizontal"
        align_bins (str): 'center', 'edge' (default, left edge alignment)
        bins (None, list): use bins if passed, else construct bins based on
          n_bins, vmin, vmax, vbase
        n_bins (int): number of bins
        n_bins_autoadd (int): autocorrect n_bins (default: 1), because code
          requires 1 extra bin.
        vmin (None, int, float): min value of histogram/bins
        vmax (None, int, float): max value of histogram/bins
        vbase (int):
          | rounding base of vmin, vmax.
          | look up misc.round_down(number,base) or misc.round_up(number,base)
        logscale (bool): apply logscale on the "count" axis
        minorticks (bool): turns minorticks (~logscale) for hist figure on/off
        norm (bool): normalize histogram
        orientation (str): "vertical", "horizontal"
        alpha (int, float)
        colors (list of str/sns.colorpalette)
        ec (None, str): edge color
        title (None, str)

    .. Hint:: Args and Keyword Args of misc.figure() are also valid.

    Returns:
        fig (class)
            matplotlib.figure.Figure
        ax (class, list)
            ax or list of axes ~ matplotlib.axes._subplots.Axes
        hist (tuple, list)
            (n, bins, patches) or list of (n, bins, patches)
    """
    # init CONFIG object with default parameter and overwrite them if kwargs contain the same keywords.
    default = {"start": sss[0],
               "stop": sss[1],
               "step": sss[2],
               "cut_min": None,
               "cut_max": None,
               "apply_cut_limits": False,

               "align_bins": "edge",
               "bins": None,
               "n_bins": 100,
               "n_bins_autoadd": 1,
               "vmin": None,
               "vmax": None,
               "vbase": 1,

               "orientation": "vertical",
               "norm": False,
               "logscale": False,
               "minorticks": False,

               "alpha": 0.5,
               "colors": ["red", "grey"],
               "ec": "white",
               "title": None,
               "xlabel": None,
               "ylabel": None}
    cfg = _misc.CONFIG(default, **kwargs)
    # edge color has to be a string, so None will result into white edge color; fix:
    if cfg.ec is None:
        cfg.ec = "None"
    ##############################################################
    ### detect if data is single or multiple arrays
    # single array
    if len(np.shape(data)) == 1:
        if isinstance(data, (list, tuple, np.ndarray)):
            data_length = 1

    # multiple arrays
    else:
        if isinstance(data[0], (list, tuple, np.ndarray)):
            data_length = len(data)
        elif isinstance(data[0], type(str)):
            data_length = len(data)
        if data_length > 2:
            cfg.colors = sns.color_palette(None, data_length)

    # apply cutoff if specified
    if data_length == 1:
        data, _ = _misc.get_cutoff_array(data[cfg.start: cfg.stop: cfg.step],
                                         cfg.cut_min, cfg.cut_max)
    else:
        data_temp = list(data)
        data = []
        for item in data_temp:
            cutoff_data, _ = _misc.get_cutoff_array(item[cfg.start: cfg.stop: cfg.step],
                                                    cfg.cut_min, cfg.cut_max)
            data.append(cutoff_data)

    ##############################################################
    ########################  histogram  #########################
    ##############################################################
    # setup bins
    bins, bins_step, sub_cfg = _HELP_setup_bins(data=data, vmin=cfg.vmin, vmax=cfg.vmax, vbase=cfg.vbase,
                                                bins=cfg.bins, n_bins=cfg.n_bins, n_bins_autoadd=cfg.n_bins_autoadd)
    cfg.update_config(**sub_cfg)

    if "ax" in cfg.keys():
        plt.sca(cfg["ax"])
        fig = plt.gcf()
    else:
        fig, ax = _misc.figure(**cfg)
    # plt.hist version
    if data_length == 1:
        hist = plt.hist(data, bins=bins,
                        density=cfg.norm, log=cfg.logscale,
                        orientation=cfg.orientation, stacked=True,
                        alpha=cfg.alpha, ec=cfg.ec, histtype="barstacked")

    else:
        HIST = []
        for ndx, item in enumerate(data):
            hist = plt.hist(item, bins=bins,
                            density=cfg.norm, log=cfg.logscale,
                            orientation=cfg.orientation, stacked=True,
                            alpha=cfg.alpha, ec=cfg.ec, histtype="barstacked")
            HIST.append(hist)

    # plt.bar/plt.barh version (redraw -> needed for pickle functions)
    if "num" in cfg.keys():
        del cfg["num"]
    fig, ax = _misc.figure(num=fig.number, **cfg)
    if data_length == 1:
        if cfg.orientation == "vertical":
            h = hist[0]
            w = bins_step
            plt.bar(bins[: -1], height=h, width=w, align=cfg.align_bins,
                    color=cfg.colors[0], alpha=cfg.alpha, ec=cfg.ec, log=cfg.logscale)
        if cfg.orientation == "horizontal":
            h = bins_step
            w = hist[0]
            plt.barh(bins[: -1], height=h, width=w, align=cfg.align_bins,
                     color=cfg.colors[0], alpha=cfg.alpha, ec=cfg.ec, log=cfg.logscale)

    else:
        for ndx, item in enumerate(data):
            if cfg.orientation == "vertical":
                h = HIST[ndx][0]
                w = bins_step
                plt.bar(bins[: -1], height=h, width=w, align=cfg.align_bins,
                        color=cfg.colors[ndx], alpha=cfg.alpha, ec=cfg.ec, log=cfg.logscale)
            if cfg.orientation == "horizontal":
                h = bins_step
                w = HIST[ndx][0]
                plt.barh(bins[: -1], height=h, width=w, align=cfg.align_bins,
                         color=cfg.colors[ndx], alpha=cfg.alpha, ec=cfg.ec, log=cfg.logscale)

    if cfg.orientation == "vertical":
        if cfg.apply_cut_limits:
            plt.xlim([cfg.cut_min, cfg.cut_max])
        else:
            plt.xlim([cfg.vmin, cfg.vmax])
    elif cfg.orientation == "horizontal":
        if cfg.apply_cut_limits:
            plt.ylim([cfg.cut_min, cfg.cut_max])
        else:
            plt.ylim([cfg.vmin, cfg.vmax])
    if cfg.minorticks == False:
        plt.minorticks_off()

    if cfg.title is not None:
        plt.title(cfg.title, fontweight='bold')
    if cfg.xlabel is not None:
        plt.xlabel(cfg.xlabel, fontweight='bold')
    if cfg.ylabel is not None:
        plt.ylabel(cfg.ylabel, fontweight='bold')
    if save_as is not None:
        _misc.savefig(save_as)

    plt.tight_layout()

    if data_length == 1:
        return(fig, ax, hist)
    else:
        return(fig, ax, HIST)


def plot_deltahist(RMSD_file, RMSD_ref, sss=[None, None, None],
                   show_all_hist=False, save_as="", **kwargs):
    """
    plot delta histogram (i.e. delta = RMSD_file - RMSD_ref)

    Args:
        RMSD_file (str): path to RMSD file
        RMSD_ref (str): path to RMSD reference file
        sss (list):
          | [start, stop, step]
          | start (None, int): start frame
          | stop (None, int): stop frame
          | step (None, int): step size
        show_all_hist (bool):
          | True:  show ref hist, non-ref hist and delta hist
          | False: show only delta hist
        title (str)
        save_as (str): save name or realpath to save file

    Keyword Args:
        alpha (float)
        colors (list): two strings in list describing color_positive and
         color_negative, e.g. ["g", "r"]
        color_positive (str)
        color_negative (str)
        ec (None, str): edge color
        start (None, int): start frame
        stop (None, int): stop frame
        step (None, int): step size
        cut_min (None, int, float): min value for cutoff (here: alias of vmin)
        cut_max (None, int, float): max value for cutoff (here: alias of vmax)
        apply_cut_limits (bool):
          | apply plt.xlim(cut_min, cut_max) if orientation is "vertical"
          | apply plt.ylim(cut_min, cut_max) if orientation is "horizontal"
        bins (None, list): use bins if passed, else construct bins based on
          n_bins, vmin, vmax, vbase
        n_bins (int): number of bins
        n_bins_autoadd (int): autocorrect n_bins (default: 1), because code
          requires 1 extra bin.
        vmin (None, int, float): min value of histogram/bins
        vmax (None, int, float): max value of histogram/bins
        vbase (int):
          | rounding base of vmin, vmax.
          | look up misc.round_down(number,base) or misc.round_up(number,base)
        logscale (bool): apply logscale on the "count" axis
        minorticks (bool): turns minorticks (~logscale) for hist figure on/off
        norm (bool): normalize histogram
        orientation (str): "vertical", "horizontal"
        title (None, str)

    .. Hint:: Args and Keyword Args of misc.figure() are also valid.

    Returns:
        fig (class)
            matplotlib.figure.Figure
        ax (class, list)
            ax or list of axes ~ matplotlib.axes._subplots.Axes
    """
    # init CONFIG object with default parameter and overwrite them if kwargs contain the same keywords.
    default = {"start": sss[0],
               "stop": sss[1],
               "step": sss[2],
               "cut_min": None,
               "cut_max": None,
               "apply_cut_limits": False,

               "bins": None,
               "n_bins": 200,
               "n_bins_autoadd": 1,
               "vmin": None,
               "vmax": None,
               "vbase": 0.2,

               "logscale": True,
               "minorticks": False,
               "norm": False,
               "orientation": "horizontal",

               "alpha": 0.8,
               "colors": ["g", "r"],
               "ec": "None",
               "title": None}
    cfg = _misc.CONFIG(default, **kwargs)
    cfg.update_by_alias(alias="color_positive", key="colors", key_ndx=0, **kwargs)
    cfg.update_by_alias(alias="color_negative", key="colors", key_ndx=1, **kwargs)
    cfg.update_by_alias(alias="cut_min", key="vmin", **kwargs)
    cfg.update_by_alias(alias="cut_max", key="vmax", **kwargs)

    header = _misc.autodetect_header(RMSD_ref)
    RMSD = np.loadtxt(RMSD_file, skiprows=header, usecols=(1,))
    RMSD_ref = np.loadtxt(RMSD_ref, skiprows=header, usecols=(1,))

    if [cfg.start, cfg.stop, cfg.step] != [0, -1, 1]:
        RMSD = RMSD[cfg.start: cfg.stop: cfg.step]
        RMSD_ref = RMSD_ref[cfg.start: cfg.stop: cfg.step]
    ##############################################################
    ################# ref and non-ref histogram ##################
    ##############################################################
    # setup bins
    bins, bins_step, sub_cfg = _HELP_setup_bins(data=RMSD_ref, vmin=cfg.vmin, vmax=cfg.vmax, vbase=cfg.vbase,
                                                bins=cfg.bins, n_bins=cfg.n_bins, n_bins_autoadd=cfg.n_bins_autoadd)
    cfg.update_config(**sub_cfg)

    fig, ax = _misc.figure(grid=[2, 1], **cfg)
    plt.sca(ax[0])
    plt.title("ref histogram")
    hist_ref = plt.hist(RMSD_ref, bins,
                        density=cfg.norm, log=cfg.logscale, orientation=cfg.orientation,
                        alpha=cfg.alpha, ec=cfg.ec, histtype="barstacked", stacked=True)
    plt.sca(ax[1])
    plt.title("non-ref histogram")
    hist = plt.hist(RMSD, bins,
                    density=cfg.norm, log=cfg.logscale, orientation=cfg.orientation,
                    alpha=cfg.alpha, ec=cfg.ec, histtype="barstacked", stacked=True)
    plt.tight_layout()
    ##############################################################
    ###################### delta histogram #######################
    ##############################################################
    diff = (hist[0]-hist_ref[0])  # difference of ref and non-ref hist
    positive = [i if i > 0 else 0 for i in diff]  # positive subset including zeros
    negative = [i if i < 0 else 0 for i in diff]  # negative subset including zeros
    if cfg.logscale:
        abs_negative = [abs(i) for i in negative]   # absolute negative subset including zeros

    if show_all_hist:
        fig, ax = _misc.figure(**kwargs)
    else:
        if "num" not in kwargs:
            fig, ax = _misc.figure(num=fig.number, **kwargs)  # reuse canvas by passing fig number
        else:
            fig, ax = _misc.figure(**kwargs)

    if cfg.orientation == "horizontal":
        if cfg.logscale:
            # positive delta ~ green; fix dim by ignoring last element
            plt.barh(bins[: -1], width=positive, height=bins_step,
                     color=cfg.colors[0], ec=cfg.ec, alpha=cfg.alpha, log=True)
            # negative delta ~ red; fix dim by ignoring last element
            plt.barh(bins[: -1], width=abs_negative, height=bins_step,
                     color=cfg.colors[1], ec=cfg.ec, alpha=cfg.alpha, log=True)
        else:
            # positive delta ~ green; fix dim by ignoring last element
            plt.barh(bins[: -1], width=positive, height=bins_step,
                     color=cfg.colors[0], ec='None', alpha=cfg.alpha, log=False)
            # negative delta ~ red; fix dim by ignoring last element
            plt.barh(bins[: -1], width=negative, height=bins_step,
                     color=cfg.colors[1], ec='None', alpha=cfg.alpha, log=False)
        if cfg.apply_cut_limits:
            plt.ylim(cfg.vmin, cfg.vmax)  # here: vmin/vmax alias of cut_min/cut_max
    elif cfg.orientation == "vertical":
        if cfg.logscale:
            # positive delta ~ green; fix dim by ignoring last element
            plt.bar(bins[: -1], height=positive, width=bins_step,
                    color=cfg.colors[0], ec=cfg.ec, alpha=cfg.alpha, log=True)
            # negative delta ~ red; fix dim by ignoring last element
            plt.bar(bins[: -1], height=abs_negative, width=bins_step,
                    color=cfg.colors[1], ec=cfg.ec, alpha=cfg.alpha, log=True)
        else:
            # positive delta ~ green; fix dim by ignoring last element
            plt.bar(bins[: -1], height=positive, width=bins_step,
                    color=cfg.colors[0], ec=cfg.ec, alpha=cfg.alpha, log=False)
            # negative delta ~ red; fix dim by ignoring last element
            plt.bar(bins[: -1], height=negative, width=bins_step,
                    color=cfg.colors[1], ec=cfg.ec, alpha=cfg.alpha, log=False)
        if cfg.apply_cut_limits:
            plt.xlim(cfg.vmin, cfg.vmax)  # here: vmin/vmax alias of cut_min/cut_max

    if cfg.minorticks == False:
        plt.minorticks_off()

    if cfg.title != None:
        plt.title(cfg.title, fontweight='bold')
    if save_as != "":
        _misc.savefig(save_as)
    plt.tight_layout()
    return(fig, ax)


def _HELP_convert_RMSD_nm2angstrom(RMSD_nm):
    """
    Helpfunction for plot_HEATMAP_REX_RMSD():
    convert RMSD values: RMSD_nm -> RMSD_anstrom

    Args:
        RMSD_nm (list): rmsd values in nm

    Returns:
        RMSD (list)
            rmsd values in angstrom
    """
    RMSD = [x*10 for x in RMSD_nm]
    return RMSD


def _HELP_convert_xticks_frame2time(ax, delta_t=0.002):
    """
    Helpfunction for plot_HEATMAP_REX_RMSD():
    convert ax xticks: frame -> time (ns)

    Args:
        ax (matplotlib.axes._subplots.Axes)

    Returns:
        xticks_time (list)
    """
    xticks_time = []
    for item in ax.get_xticklabels():
        xticks_time.append(item.get_text())
    xticks_time = [float(x)*delta_t for x in xticks_time]
    xticks_time = [int(x) if x.is_integer() else x for x in xticks_time]
    return xticks_time


def plot_HEATMAP(data, **kwargs):
    """
    plot heatmap

    .. Note:: if data is incomplete: use min/max values or np.nan for missing
      values and the Keyword Arg annot=True or annot=False

    Args:
        data (arrays)
        save_as (str): save name or realpath to save file

    Keyword Args:
        annot (bool, list): toggle annotation within the heatmap squares. If a
          list is provided, annotates the list content.
        cmap (str): color map string
        n_colors (None, int)
        cbar_min/vmin (None, int, float): min value of colorbar and heatmap
        cbar_max/vmax (None, int, float): max value of colorbar and heatmap
        cbar_label (None, str)
        title (None, str)
        xlabel (None, str)
        ylabel (None, str)
        xticklabels (None, list)
        yticklabels (None, list)
        show_ticks (bool): toggle (label) ticks
        save_as (None, str)

    .. Hint:: Args and Keyword Args of misc.figure() are also valid.

    Returns:
        fig (class)
            matplotlib.figure.Figure
        ax (class, list)
            ax or list of axes ~ matplotlib.axes._subplots.Axes
    """
    default = {"figsize": (6.5, 4),
               "vmin": None,
               "vmax": None,

               "annot": True,
               "cmap": "RdBu_r",
               "n_colors": 50,
               "cbar_min": None,
               "cbar_max": None,
               "cbar_label": None,

               "title": None,
               "xlabel": None,
               "ylabel": None,
               "xticklabels": None,
               "yticklabels": None,
               "show_ticks": False,
               "save_as": None}
    cfg = _misc.CONFIG(default, **kwargs)
    cfg.update_by_alias(alias="cbar_min", key="vmin", **kwargs)
    cfg.update_by_alias(alias="cbar_max", key="vmax", **kwargs)

    if cfg.xticklabels is None:
        ydim, xdim = np.shape(data)
        cfg.xticklabels = range(xdim)
    if cfg.yticklabels is None:
        ydim, xdim = np.shape(data)
        cfg.yticklabels = range(ydim)

    fig, ax = _misc.figure(**cfg)
    # settings
    cmap = sns.color_palette(cfg.cmap, cfg.n_colors)  # Red Blue reversed, 50 colors
    hm = sns.heatmap(data, cmap=cmap, vmin=cfg.vmin, vmax=cfg.vmax,
                     linewidth=0, annot=cfg.annot,
                     xticklabels=cfg.xticklabels, yticklabels=cfg.yticklabels)

    if cfg.xlabel is not None:
        plt.xlabel(cfg.xlabel, fontweight='bold')
    if cfg.ylabel is not None:
        plt.ylabel(cfg.ylabel, fontweight='bold')
    if cfg.show_ticks == False:
        ax.tick_params(left=False, bottom=False)
        locs = ax.get_yticks()
        ax.set_yticks(locs-0.1)
    #####################################################
    # set cbar label
    cbar = hm.collections[0].colorbar
    if cfg.cbar_label is not None:
        cbar.set_label(cfg.cbar_label, fontweight='bold')
    #####################################################
    if cfg.title is not None:
        plt.title(cfg.title, fontweight='bold')

    plt.tight_layout()

    if cfg.save_as != None:
        if ".pdf" in cfg.save_as:
            print("""Too much data within the heatmap to save it as a .pdf file.
    (vector graphic ~ number of objects too high)
    Saving figure as .png with 300 dpi instead...""")
            save_as = f"{os.path.dirname(os.path.realpath((cfg.save_as)))}/{_misc.get_base(cfg.save_as)}.png"
        _misc.savefig(filename=save_as)

    return(fig, ax)


def plot_HEATMAP_REX_RMSD(REX_RMSD_dir, cps=["RdBu_r", 50, 0, 8], auto_convert=True, save_as="", **kwargs):
    """
    plot heatmap with REX RMSDs. This function uses a directory with RMSD files as input.

    Args:
        REX_RMSD_dir (str): directory to REX_RMSD files
        cps (list):
          | color_palette_settings
          | cps[0]: color_palette name (str)
          | cps[1]: n_colors (int)
          | cps[2]: heatmap vmin (int, float)
          | cps[3]: heatmap vmax (int, float)
        auto_convert (bool):
          | convert "displayed" RMSD and xticks for plot. Returned values stay unconverted
          | True: convert RMSD (nm) -> RMSD (angstrom)
          |       convert frame -> time (ns)
        save_as (str): save name or realpath to save file

    Keyword Args:
        title (None, str)

    .. Hint:: Args and Keyword Args of misc.figure() are also valid.

    Returns:
        TIME (list)
            time values taken from first REX_RMSD file
        RMSD (list of arrays)
            RMSD values of each REX_RMSD file
    """
    ### setup default kwargs if not passed
    default = {"figsize": (7.5, 6),
               "title": None}
    cfg = _misc.CONFIG(default, **kwargs)

    RMSD_FILES = []
    for file in sorted(glob.glob(os.path.join(REX_RMSD_dir, '*.xvg'))):
        RMSD_FILES.append(file)
    TIME = np.loadtxt(RMSD_FILES[0], skiprows=_misc.autodetect_header(file), usecols=(0,))
    TIME = [round(x, 3) for x in TIME]
    RMSD = [np.loadtxt(file, skiprows=_misc.autodetect_header(file), usecols=(1,)) for file in RMSD_FILES]

    fig, ax = _misc.figure(**cfg)
    # settings
    cmap = sns.color_palette(cps[0], cps[1])  # Red Blue reversed, 50 colors
    vmin = cps[2]
    vmax = cps[3]
    xticklabels = 25000  # show every 25k label
    yticklabels = 10     # show every 10 label

    if auto_convert:
        RMSD_temp = _HELP_convert_RMSD_nm2angstrom(RMSD)
        RMSD_max = np.amax(RMSD_temp)
        hm = sns.heatmap(RMSD_temp, cmap=cmap, vmin=vmin, vmax=vmax, linewidth=0,
                         xticklabels=xticklabels, yticklabels=yticklabels,
                         cbar_kws=dict(ticks=np.arange(vmin, vmax+1, 2)))  # set custom cbar ticks
        ax.set_xticklabels(_HELP_convert_xticks_frame2time(ax))  # convert time ticks
        plt.xlabel('Time (ns)', fontweight='bold')
    else:
        RMSD_max = np.amax(RMSD)
        hm = sns.heatmap(RMSD, cmap=cmap, vmin=vmin, vmax=vmax, linewidth=0,
                         xticklabels=xticklabels, yticklabels=yticklabels,
                         cbar_kws=dict(ticks=np.arange(vmin, vmax+1, 2)))  # set custom cbar ticks
        plt.xlabel('Frame Number', fontweight='bold')

    plt.ylabel('Replica Number', fontweight='bold')
    ax.invert_yaxis()  # (sns.heatmap() plots array values from top to bottom) -> reverse axis
    #####################################################
    # set cbar label
    cbar = hm.collections[0].colorbar
    if RMSD_max < 5.0:
        cbar.set_label('RMSD (nm)', fontweight='bold')
    else:
        cbar.set_label('RMSD ($\AA$)', fontweight='bold')
    #####################################################
    if cfg.title is not None:
        plt.title(cfg.title, fontweight='bold')

    plt.tight_layout()
    plt.tight_layout()
    plt.show()

    if save_as != "":
        if ".pdf" in save_as:
            print("""Too much data within the heatmap to save it as a .pdf file.
    (vector graphic ~ number of objects too high)
    Saving figure as .png with 300 dpi instead...""")
            save_as = f"{_misc.get_base(save_as)}.png"
        _misc.savefig(filename=save_as)

    return(TIME, RMSD)
