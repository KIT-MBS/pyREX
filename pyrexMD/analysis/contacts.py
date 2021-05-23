# @Author: Arthur Voronin
# @Date:   07.05.2021
# @Filename: contacts.py
# @Last modified by:   arthur
# @Last modified time: 24.05.2021

"""
This module contains functions related to native contact and bias contact analyses.


Example:
--------

.. code-block:: python

    import MDAnalysis as mda
    import pyrexMD.analysis.contacts as con

    ref = mda.Universe("<pdb_file>")
    mobile = mda.Universe("<tpr_file>", "<xtc_file>")

    # get and plot native contacts
    con.get_Native_Contacts(ref, sel="protein")
    con.plot_Contact_Map(ref, sel="protein")

    # compare contact map for n bias contacts
    n = 50
    con.plot_Contact_Map(ref, DCA_fin="path/to/bias/contacts", n_DCA=n)

    # check true positive rate for n bias contacts
    n = 50
    con.plot_DCA_TPR(ref, DCA_fin="path/to/bias/contacts", n_DCA=n)

Module contents:
----------------
"""

import pyrexMD.analysis.analysis as _ana
import pyrexMD.misc as _misc
import pyrexMD.topology as _top
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import MDAnalysis as mda
from MDAnalysis.analysis import contacts as _contacts, distances as _distances
import operator


def get_Native_Contacts(ref, d_cutoff=6.0, sel="protein", **kwargs):
    """
    Get list of unique RES pairs and list of detailed RES pairs with native contacts.

    Note:
        len(NC) < len(NC_d) because NC contains only unique RES pairs
        whereas NC_d contains each ATOM pair.

    Args:
        ref (str, universe, atomgrp): reference structure
        d_cutoff (float): cutoff distance for native contacts
        sel (str): selection string

    Keyword Args:
        method (str):
          | '1' or 'Contact_Matrix': mda.contact_matrix() with d_cutoff
          | '2' or 'Shadow_Map' #TODO
        norm (bool): apply topology.norm_universe()
        ignh (bool): ignore hydrogen
        save_as (None, str):
          | save RES pairs and ATOM pairs of native contacts to a log file.
          | selection is hardcoded to "protein and name CA" for proteins
          | and "name N1 or name N3" for RNA/DNA.

    Returns:
        NC (list)
            list with unique RES pairs
        NC_d (list)
            detailed list of NCs containing (RES pairs), (ATOM numbers), (ATOM names)
    """
    default = {"method": "1",
               "norm": True,
               "ignh": True,
               "save_as": None}
    cfg = _misc.CONFIG(default, **kwargs)
    ############################################################################
    if type(cfg.method) is int:
        cfg.method = str(cfg.method)

    # load universe
    if type(ref) is str:
        u = mda.Universe(ref)
    else:
        u = ref
    if cfg.norm:
        _top.norm_universe(u)
    if cfg.ignh:
        a = _top.true_select_atoms(u, sel, ignh=cfg.ignh, norm=cfg.norm)
    else:
        a = u.select_atoms(sel)

    NC = []     # list with unique NC pairs
    NC_d = []   # detailed list with NCs containing (RES pairs), (ATOM pairs), (NAME pairs)

    if cfg.method in ['1', 'Contact_Matrix', 'contact_matrix']:
        RES = a.resids
        IDS = a.ids
        NAMES = a.names

        CM = _distances.contact_matrix(a.positions, cutoff=d_cutoff)
        for i in range(len(CM)):
            for j in range(i + 1, len(CM)):  # no double count/reduce computing time
                if RES[j] - RES[i] > 3 and CM[i][j] == True and (RES[i], RES[j]) not in NC:
                    NC.append((RES[i], RES[j]))
                    NC_d.append([(RES[i], RES[j]), (IDS[i], IDS[j]), (NAMES[i], NAMES[j])])

    elif cfg.method in ['2', 'Shadow_Map', 'shadow_map']:
        # TODO method 2: SHADOWMAP
        pass

    # sort
    NC = sorted(NC)
    NC_d = sorted(NC_d)

    if cfg.save_as != None:
        cfg.save_as = _misc.realpath(cfg.save_as)
        _misc.cprint(f"Saved file as: {cfg.save_as}")
        if len(a.select_atoms("nucleic")) == 0:
            # hardcoded protein selection
            resid, resname, id, name = _top.parsePDB(u.filename, sel="protein and name CA")
        else:
            # hardcoded nucleic selection
            resid, resname, id, name = _top.parsePDB(u.filename, sel="name N1 or name N3")
        with open(cfg.save_as, "w") as fout:
            fout.write("#RESi\tRESj\tATOMi\tATOMj\n")
            for IJ in NC:
                fout.write(f"{IJ[0]}\t{IJ[1]}\t{id[resid.index(IJ[0])]}\t{id[resid.index(IJ[1])]}\n")

    return(NC, NC_d)


def plot_Contact_Map(ref, DCA_fin=None, n_DCA=None, d_cutoff=6.0,
                     sel='protein', pdbid='pdbid', **kwargs):
    """
    Create contact map based on the reference pdb structure.
    If DCA file is passed, correct/wrong contacts are visualized in green/red.

    Args:
        ref (str, universe, atomgrp): reference path or structure
        DCA_fin (None, str): DCA input file
        n_DCA (None, int): number of used DCA contacts
        d_cutoff (float): cutoff distance for native contacts
        sel (str): selection string
        pdbid (str): pdbid which is used for plot title

    Keyword Args:
        DCA_cols (tuple): columns containing the RES pairs in DCA_fin
        DCA_skiprows (int):
          | skip header rows of DCA_fin
          | -1 or "auto": auto detect
        filter_DCA (bool):
          | True: ignore DCA pairs with abs(i-j) < 3.
          | False: use all DCA pairs w/o applying filter.
        RES_range (None, list):
          | include RES only within [RES_min, RES_max] range
          | None: do not narrow down RES range
        ignh (bool): ignore hydrogen (mass < 1.2)
        norm (bool): apply topology.norm_universe()
        save_plot (bool)

    .. hint:: Args and Keyword Args of misc.figure() are also valid.

    Returns:
        fig (class)
            matplotlib.figure.Figure
        ax (class, list)
            ax or list of axes ~ matplotlib.axes._subplots.Axes
    """
    default = {"DCA_cols": (0, 1),
               "DCA_skiprows": "auto",
               "filter_DCA": True,
               "RES_range": [None, None],
               "ignh": True,
               "norm": True,
               "save_plot": False}
    cfg = _misc.CONFIG(default, **kwargs)
    # init values
    if "figsize" not in kwargs:
        kwargs = {"figsize": (7, 7)}

    # load universe
    if pdbid == 'pdbid':
        pdbid = _misc.get_PDBid(ref)
    if type(ref) is str:
        u = mda.Universe(ref)
    else:
        u = ref
    if cfg.norm:
        _top.norm_universe(u)
    if cfg.ignh:
        a = _top.true_select_atoms(u, sel, ignh=True, norm=cfg.norm)
    else:
        a = u.select_atoms(sel)
    res_min = min(a.resids)
    res_max = max(a.resids)

    # calculate nat. contacts for ref structure
    NC, NC_details = get_Native_Contacts(a, d_cutoff=d_cutoff, sel=sel, norm=cfg.norm)

    # PLOT
    fig, ax = _misc.figure(**kwargs)
    ax.set_aspect('equal')

    # conditions for markersize
    print("Plotting native contacts...")
    for item in NC:
        if res_max - res_min < 100:
            plt.scatter(item[0], item[1], color="silver", marker="s", s=16)
        else:
            plt.scatter(item[0], item[1], color="silver", marker="s", s=4)

    # find matching contacts ij
    if DCA_fin is not None:
        DCA, _ = _misc.read_DCA_file(DCA_fin, n_DCA, usecols=cfg.DCA_cols, skiprows=cfg.DCA_skiprows, filter_DCA=cfg.filter_DCA, RES_range=cfg.RES_range)

        if res_max - res_min < 100:
            for item in DCA:     # if item is in both lists plot it green otherwise red
                if item in NC:
                    plt.plot(item[0], item[1], color="green", marker="s", ms=4)
                else:
                    plt.plot(item[0], item[1], color="red", marker="s", ms=4)
        else:
            for item in DCA:     # if item is in both lists plot it green otherwise red
                if item in NC:
                    plt.plot(item[0], item[1], color="green", marker="s", ms=2)
                else:
                    plt.plot(item[0], item[1], color="red", marker="s", ms=2)

    # plt.legend(loc="upper left", numpoints=1)
    if res_max - res_min < 30:
        xmin, xmax = _misc.round_down(res_min, 2), _misc.round_up(res_max + 1, 2)
        ymin, ymax = _misc.round_down(res_min, 2), _misc.round_up(res_max + 1, 2)
        loc = matplotlib.ticker.MultipleLocator(base=5)  # this locator puts ticks at regular intervals
        ax.xaxis.set_major_locator(loc)
        ax.yaxis.set_major_locator(loc)
    else:
        xmin, xmax = _misc.round_down(res_min, 5), _misc.round_up(res_max + 1, 5)
        ymin, ymax = _misc.round_down(res_min, 5), _misc.round_up(res_max + 1, 5)
    plt.xlim(xmin, xmax)
    plt.ylim(ymin, ymax)
    plt.xlabel(r"Residue i", fontweight="bold")
    plt.ylabel(r"Residue j", fontweight="bold")
    plt.title(f"Contact Map of {pdbid}", fontweight="bold")
    plt.tight_layout()
    if cfg.save_plot:
        _misc.savefig(filename=f"{pdbid}_Fig_Contact_Map.png", filedir="./plots")
    plt.show()
    return fig, ax


def plot_DCA_TPR(ref, DCA_fin, n_DCA, d_cutoff=6.0, sel='protein', pdbid='pdbid', **kwargs):
    """
    Plots true positive rate for number of used DCA contacts.

    - calculates shortest RES distance of the selection (only heavy atoms if ignh is True)
    - if distance is below threshold: DCA contact is True

    Args:
        ref (str): reference path
        ref (universe, atomgrp): reference structure
        DCA_fin (str): DCA input file (path)
        n_DCA (int): number of used DCA contacts
        d_cutoff (float): cutoff distance for native contacts
        sel (str): selection string
        pdbid (str): pdbid; used for plot title and figure name

    Keyword Args:
        DCA_cols (tuple, list): columns containing the RES pairs in DCA_fin
        DCA_skiprows (int):
          | skip header rows of DCA_fin
          | -1 or "auto": auto detect
        filter_DCA (bool):
          | True: ignore DCA pairs with abs(i-j) < 4
          | False: use all DCA pairs w/o applying filter
        RES_range (None):
          | [RES_min, RES_max] range. Ignore invalid RES ids
          | None: do not narrow down RES range
        ignh (bool): ignore hydrogen (mass < 1.2)
        norm (bool): apply topology.norm_universe()
        TPR_layer (str):
          | plot TPR curve in foreground or background layer
          | "fg", "foreground", "bg", "background"
        color (str)
        shade_area (bool): shade area between L/2 and L ranked contacts
        shade_color (str)
        shade_alpha (float)
        hline_color (None, str): color of 75p threshold (horizontal line)
        hline_ls (str): linestyle of hline (default: "-")
        nDCA_opt_color (None, str):
          | color of optimal/recommended nDCA threshold
          | nDCA_opt = misc.round_up(3/4*len(ref.residues), base=5))
          | (vertical line ~ nDCA_opt)
          | (horizontal line ~ TPR(nDCA_opt))
        nDCA_opt_ls (str): linestyle of nDCA_opt (default: "--")
        save_plot (bool)
        save_log (bool)
        figsize (tuple)
        marker (None, str): marker
        ms (int): markersize
        ls (str): linestyle
        alpha (float): alpha value

    Returns:
        fig (class)
            matplotlib.figure.Figure
        ax (class, list)
            ax or list of axes ~ matplotlib.axes._subplots.Axes
    """
    default = {"DCA_cols": (0, 1),
               "DCA_skiprows": "auto",
               "filter_DCA": True,
               "RES_range": [None, None],
               "ignh": True,
               "norm": True,
               "TPR_layer": "fg",
               "color": "blue",
               "shade_area": True,
               "shade_color": "orange",
               "shade_alpha": 0.2,
               "hline_color": "red",
               "hline_ls": "-",
               "nDCA_opt_color": "orange",
               "nDCA_opt_ls": "--",
               "save_plot": False,
               "save_log": False,
               "figsize": (8, 4.5),
               "marker": None,
               "ms": 1,
               "ls": "-",
               "alpha": 1.0}
    cfg = _misc.CONFIG(default, **kwargs)
    # load universe
    if pdbid == 'pdbid':
        pdbid = _misc.get_PDBid(ref)
    if isinstance(ref, str):
        u = mda.Universe(ref)
    else:
        u = ref
    if cfg.norm:
        _top.norm_universe(u)
    if cfg.ignh:
        a = _top.true_select_atoms(u, sel, ignh=True, norm=cfg.norm)
    else:
        a = u.select_atoms(sel)
    # read DCA and calculate TPR
    DCA, _ = _misc.read_DCA_file(DCA_fin, n_DCA, usecols=cfg.DCA_cols, skiprows=cfg.DCA_skiprows, filter_DCA=cfg.filter_DCA, RES_range=cfg.RES_range)
    DCA_TPR = []  # List with TPR of DCA contacts with d < d_cutoff
    SD = _ana.shortest_RES_distances(u=a, sel=sel)[0]
    RES_min = min(a.residues.resids)
    z = 0
    for index, item in enumerate(DCA):
        if SD[item[0] - RES_min][item[1] - RES_min] <= d_cutoff:  # shift RES ids to match matrix indices
            z += 1
        percent_value = _misc.percent(z, index + 1)
        DCA_TPR.append(percent_value)

    # LOG FILE
    # List with number of DCA contacts and TPR values
    DCA_TPR_sorted = [[i + 1, DCA_TPR[i]] for i in range(len(DCA_TPR))]
    DCA_TPR_sorted = sorted(DCA_TPR_sorted, key=operator.itemgetter(1), reverse=True)  # sort by TPR value

    # PLOT: find optimum for number of DCA contacts
    # x-axis: number of DCA contacts
    # y-axis: % of DCA contacts with d <= d_cuttoff
    with sns.axes_style('darkgrid'):
        fig, ax = plt.subplots(figsize=cfg.figsize)
        if cfg.TPR_layer.lower() == "bg" or cfg.TPR_layer.lower() == "background":
            plt.plot(range(1, n_DCA + 1), DCA_TPR, color=cfg.color, marker=cfg.marker, ms=cfg.ms, ls=cfg.ls)
            plt.plot(range(1, n_DCA + 1), DCA_TPR, color=cfg.color, alpha=0.2, lw=2)
        # plt.legend(loc="upper right", numpoints=1)
        plt.xlim(0, n_DCA + 1)
        plt.ylim(0, 105)
        # if min(DCA_TPR) < 50:
        #     plt.ylim(0, 105)  # full range for TPR
        # else:
        #     plt.ylim(50, 105) # smaller range for very good TPR
        if cfg.shade_area:
            L1 = _misc.round_down(u.residues.n_residues/2, base=1)
            L2 = u.residues.n_residues
            plt.axvspan(L1, L2, alpha=cfg.shade_alpha, color=cfg.shade_color)
            plt.text(L1-2, -5, "L/2", color=cfg.shade_color, alpha=1, fontweight="bold")
            plt.text(L2, -5, "L", color=cfg.shade_color, alpha=1, fontweight="bold")
        if cfg.hline_color is not None:
            plt.axhline(75, color=cfg.hline_color, ls=cfg.hline_ls)
            plt.text(-3, 73, "75", color=cfg.hline_color, fontweight="bold")
            #_misc.set_pad(ax, xpad=None, ypad=10) # set padding after tight_layout()
        if cfg.nDCA_opt_color is not None:
            nDCA_opt = int(_misc.round_to_base(3/4*len(u.residues), 5))
            nDCA_opt_TPR = int(DCA_TPR[nDCA_opt - 1])  # requires index shift by 1 to get correct value
            plt.axhline(nDCA_opt_TPR, color=cfg.nDCA_opt_color, ls=cfg.nDCA_opt_ls)
            plt.text(-3, nDCA_opt_TPR-2, nDCA_opt_TPR, color=cfg.nDCA_opt_color, fontweight="bold")
            plt.axvline(nDCA_opt, color=cfg.nDCA_opt_color, ls=cfg.nDCA_opt_ls)
            plt.text(nDCA_opt-1.3, -5, nDCA_opt, color=cfg.nDCA_opt_color, fontweight="bold")
            #_misc.set_pad(ax, xpad=10, ypad=10)  # set padding after tight_layout()
        plt.xlabel("Number of ranked contacts")
        plt.ylabel("True Positive Rate (%)")
        plt.title(f"TPR of {pdbid}", fontweight="bold")
        sns.despine(offset=0)
        if cfg.TPR_layer.lower() == "fg" or cfg.TPR_layer.lower() == "foreground":
            plt.plot(range(1, n_DCA + 1), DCA_TPR, color=cfg.color, marker=cfg.marker, ms=cfg.ms, ls=cfg.ls)
            plt.plot(range(1, n_DCA + 1), DCA_TPR, color=cfg.color, alpha=0.2, lw=2)
        plt.tight_layout()
        if cfg.hline_color is not None:
            _misc.set_pad(ax, xpad=None, ypad=10)  # set padding after tight_layout()
        if cfg.nDCA_opt_color is not None:
            _misc.set_pad(ax, xpad=10, ypad=10)    # set padding after tight_layout()

        if cfg.save_plot:
            _misc.savefig(filename=f"{pdbid}_Fig_DCA_TPR.png", filedir="./plots")
        if cfg.save_log:
            save_dir = _misc.mkdir("./logs")
            file_dir = save_dir + f"/{pdbid}_DCA_TPR.log"
            with open(file_dir, "w") as fout:
                fout.write("Format:\n")
                fout.write("Number of DCA Contacts \t True Positive Rate (%)\n\n")
                fout.write("10 Best values (100% excluded):\n")
                count = 0
                for i in range(len(DCA_TPR_sorted)):
                    if count < 10 and DCA_TPR_sorted[i][1] < 100.0:
                        fout.write(f"{DCA_TPR_sorted[i][0]}\t{DCA_TPR_sorted[i][1]}\n")
                        count += 1
                fout.write("\nFull list:\n")
                fout.write(f"{0}\t{0.0}\n")
                for i in range(len(DCA_TPR)):
                    fout.write(f"{i+1}\t{DCA_TPR[i]}\n")
                print(f"Saved log as: {file_dir}")
    return fig, ax


def get_Qnative(mobile, ref, sel="protein and name CA", sss=[None, None, None],
                d_cutoff=6.0, plot=True, verbose=True, **kwargs):
    """
    Get QValue for native contacts.

    - norms and aligns mobile to ref so that atomgroups have same resids
    - performs native contact analysis

    Args:
        mobile (universe): mobile structure with trajectory
        ref (universe): reference structure
        sel (str): selection string
        sss (list):
          | [start, stop, step]
          | start (None, int): start frame
          | stop (None, int): stop frame
          | step (None, int): step size
        d_cutoff (float): cutoff distance for native contacts
        plot (bool)
        verbose (bool)

    Keyword Arguments:
        sel1 (str): selection string for contacting group (1 to 1 mapping)
        sel2 (str): selection string for contacting group (1 to 1 mapping)
        method (str):
          | method for QValues calculation
          | 'radius_cut': native if d < d_cutoff
          | 'soft_cut': see help(MDAnalysis.analysis.contacts.soft_cut_q)
          | 'hardcut': native if d < d_ref
        start (None, int): start frame
        stop (None, int): stop frame
        step (None, int): step size
        color (str)
        save_plot (bool)
        save_as (str): "Qnative.png"

    .. Note:: sel (arg) is ignored if sel1 or sel2 (kwargs) are passed.

    Returns:
        FRAMES (list)
            list with frames
        QNATIVE (list)
            list with fraction of native contacts
    """
    default = {"sel1": None,
               "sel2": None,
               "method": "radius_cut",
               "start": sss[0],
               "stop": sss[1],
               "step": sss[2],
               "color": "r",
               "save_plot": False,
               "save_as": "Qnative.png"}
    cfg = _misc.CONFIG(default, **kwargs)
    if cfg.sel1 is None and cfg.sel2 is None:
        cfg.sel1 = sel
        cfg.sel2 = sel
    if cfg.sel1 == None or cfg.sel2 == None:
        _misc.Error("Set either sel (arg) or both sel1 and sel2 (kwargs).")
    #####################################################################
    _top.norm_and_align_universe(mobile, ref)

    ref1 = ref.select_atoms(cfg.sel1)  # reference group 1 in reference conformation
    ref2 = ref.select_atoms(cfg.sel2)  # reference group 2 in reference conformation

    results = _contacts.Contacts(mobile, select=(cfg.sel1, cfg.sel2), refgroup=(ref1, ref2),
                                 radius=d_cutoff, method=cfg.method)

    results.run(start=cfg.start, stop=cfg.stop, step=cfg.step, verbose=verbose)
    FRAMES = results.timeseries[:, 0]
    QNATIVE = results.timeseries[:, 1]

    if plot:
        _misc.cprint(f"average qnative value: {round(np.mean(QNATIVE), 3)}", "blue")

        fig, ax = _misc.figure()
        plt.plot(FRAMES, QNATIVE, color=cfg.color, alpha=1)
        #plt.plot(FRAMES, QNATIVE, color=cfg.color, alpha=0.3)
        plt.xlabel("frame", fontweight="bold")
        plt.ylabel("Qnative", fontweight="bold")
        plt.tight_layout()
    if cfg.save_plot:
        _misc.savefig(filename=cfg.save_as, create_dir=True)
    return FRAMES, QNATIVE


def get_Qbias(mobile, bc, sss=[None, None, None], d_cutoff=6.0, norm=True,
              plot=True, warn=True, verbose=True, **kwargs):
    """
    Get QValue for formed bias contacts.

    .. Note:: selection of get_Qbias() is hardcoded to sel='protein and name CA'.

      Reason: bias contacts are unique RES PAIRS and grow 'slowly', but going from
      sel='protein and name CA' to sel='protein' increases the atom count
      significantly. Most of them will count as non-native and thus make
      the Qbias value very low.

    .. Note :: MDAnalysis' qvalue algorithm includes selfcontacts. Comparison of
      both methods yields better results when the kwarg include_selfcontacts
      (bool) is set to True. However this improves the calculated Qbias value
      artificially (e.g. even when all used bias contacts are never formed,
      Qbias will not be zero due to the selfcontact counts)

    Args:
        mobile (universe): mobile structure with trajectory
        bc (list): list with bias contacts to analyze
        sss (list):
          | [start, stop, step]
          | start (None, int): start frame
          | stop (None, int): stop frame
          | step (None, int): step size
        d_cutoff (float): cutoff distance for native contacts
        norm (bool): norm universe before calculation.
        plot (bool)
        warn (bool): print important warnings about usage of this function.
        verbose (bool)

    Keyword Args:
        dtype (dtype): data type of returned contact matrix CM
        include_selfcontacts (bool):
          | sets norm of QBIAS. Default is False.
          | True: includes selfcontacts on main diagonal of CM (max count > len(bc))
          | False: ignores selfcontacts on main diagonal of CM (max count == len(bc))
        start (None, int): start frame
        stop (None, int): stop frame
        step (None, int): step size
        color (str)
        save_plot (bool)
        save_as (str): "Qbias.png"

    Returns:
        FRAMES (array)
            array with frame numbers
        QBIAS (array)
            array with fraction of formed bias contacts
        CM (array)
            array with distance matrices
    """
    default = {"dtype": bool,
               "include_selfcontacts": False,
               "start": sss[0],
               "stop": sss[1],
               "step": sss[2],
               "color": "r",
               "save_plot": False,
               "save_as": "Qbias.png"}
    cfg = _misc.CONFIG(default, **kwargs)
    sel = "protein and name CA"  # selection must be hardcoded (see print msg below)
    ################################################################################
    if warn:
        _misc.cprint("Note 1: selection of get_Qbias() is hardcoded to sel='protein and name CA'.", "red")
        _misc.cprint("Reason: bias contacts are unique RES PAIRS and grow 'slowly', but going from sel='protein and name CA' to sel='protein' increases the atom count significantly. Most of them will count as non-native and thus make the Qbias value very low.", "red")
        _misc.cprint("Note 2: MDAnalysis' qvalue algorithm includes selfcontacts. Comparison of both methods yields better results when include_selfcontacts (bool, see kwargs) is set to True. However this improves the calculated Qbias value artificially (e.g. even when all used bias contacts are never formed, Qbias will not be zero due to the selfcontact counts)", "red")

    if norm:
        _top.norm_universe(mobile)

    QBIAS = []  # QBias value (fraction of formed bias contacts)
    CM = []     # Contact Matrices

    DM = _ana.get_Distance_Matrices(mobile=mobile, sss=[cfg.start, cfg.stop, cfg.step], sel=sel)
    for dm in DM:
        cm = (dm <= d_cutoff)   # converts distance matrix to bool matrix -> use as contact matrix
        count = 0
        for item in bc:
            if cm[item[0]-1, item[1]-1] == True:
                count += 1

        if cfg.include_selfcontacts == False:
            # norm based on used bias contacts
            QBIAS.append(count/len(bc))
            CM.append(cm)
        else:
            # norm based on used bias contacts and selfcontacts
            QBIAS.append((count+len(cm))/(len(bc)+len(cm)))
            CM.append(cm)

    FRAMES = list(range(len(QBIAS)))

    if plot:
        if verbose:
            _misc.cprint(f"average qbias value: {np.mean(QBIAS)}", "blue")
        fig, ax = _misc.figure()
        plt.plot(FRAMES, QBIAS, color=cfg.color, alpha=1)
        #plt.plot(FRAMES, QBIAS, color=cfg.color, alpha=0.3)
        plt.xlabel("frame", fontweight="bold")
        plt.ylabel("Qbias", fontweight="bold")
        plt.tight_layout()
    if cfg.save_plot:
        _misc.savefig(filename=cfg.save_as, create_dir=True)
    return np.array(FRAMES), np.array(QBIAS), np.array(CM)


def get_formed_contactpairs(u, cm, sel="protein and name CA", norm=True, **kwargs):
    """
    get formed contact pairs by converting a contact matrix cm into a list with
    tuples (RESi,RESj).

    Args:
        u (universe): used to obtain topology information
        cm (array): single contact matrix of size (n_atoms, n_atoms)
        sel (str): selection string
        norm (bool): norm universe before obtaining topology information

    Keyword Args:
        include_selfcontacts (bool): include contacts on main diagonal of cm. Default is False.

    Returns:
        CP (list)
            list with contact pairs (RESi,RESj)
    """
    default = {"include_selfcontacts": False}
    cfg = _misc.CONFIG(default, **kwargs)
    ########################################################
    if norm:
        _top.norm_universe(u)
    RES = u.select_atoms(sel).resids   # get RESIDS information
    CP = []  # list with contact pairs

    ### test if input is single contact matrix
    if len(np.shape(cm)) == 3:
        raise _misc.Error("get_formed_contactpairs() expected contact map cm with size (n_atoms, n_atoms). You probably passed a contact map with size (n_frames, n_atoms, n_atoms)")

    ### calculate contact pairs
    if cfg.include_selfcontacts is False:
        # loop over upper triangle
        for i in range(len(cm)):
            for j in range(i+1, len(cm)):
                if cm[i][j] == True:
                    CP.append((RES[i], RES[j]))
    else:
        # loop over upper triangle including main diagonal
        for i in range(len(cm)):
            for j in range(i, len(cm)):
                if cm[i][j] == True:
                    CP.append((RES[i], RES[j]))
    return CP
