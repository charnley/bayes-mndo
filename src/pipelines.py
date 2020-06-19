
import json
import multiprocessing as mp
import os
import shutil
import subprocess
from functools import partial

import numpy as np
from tqdm import tqdm

from chemhelp import mndo


def set_params(param_list, param_keys, mean_params, scale_params, scr="./"):
    """

    Translate from RhysJanosh format to Jimmy dictionary and write to disk.

    """

    # Create new param dict
    params = {key[0]: {} for key in param_keys}

    for (atom_type, prop), param in zip(param_keys, param_list):
        params[atom_type][prop] = param

    for atomtype in params:
        p, s, d = params[atomtype], scale_params[atomtype], mean_params[atomtype]

        for key in p:
            val = p[key] * s[key] + d[key]
            params[atom_type][key] = val

    mndo.set_params(params, scr=scr)

    return


def calculate(binary, filename, scr=None):
    """
    Collect sets of lines for each molecule as they become availiable
    and then call a parser to extract the dictionary of properties.
    """
    calculations = mndo.calculate_file(filename, scr=scr, mndo_cmd=binary)

    props_list = []

    for mol_lines in calculations:
        try:
            props = mndo.get_properties(mol_lines)
        except:
            props = dict()
            props["energy"] = np.float("nan")
        props_list.append(props)

    return props_list


def calculate_parallel(
    params_joblist,
    param_keys,
    mean_params,
    scale_params,
    filename,
    binary,
    n_procs=2,
    mndo_input=None,
    scr="_tmp_mndo_",
    **kwargs,
):


    worker_kwargs = {
        "scr": scr,
        "filename": filename,
        "param_keys": param_keys,
        "mean_params": mean_params,
        "scale_params": scale_params,
        "binary": binary,
    }

    mapfunc = partial(worker, **worker_kwargs)

    p = mp.Pool(n_procs)
    # results = p.map(mapfunc, params_joblist)
    results = list(tqdm(p.imap(mapfunc, params_joblist), total=len(params_joblist)))

    return results


def worker(*args, **kwargs):
    """
    """
    scr = kwargs["scr"]
    filename = kwargs["filename"]
    param_keys = kwargs["param_keys"]
    mean_params = kwargs["mean_params"]
    scale_params = kwargs["scale_params"]
    binary = kwargs["binary"]

    # Ensure unique directory for this worker in scratch directory
    pid = os.getpid()
    cwd = os.path.join(scr, str(pid))

    if not os.path.exists(cwd):
        os.mkdir(cwd)

    if not os.path.exists(os.path.join(cwd, filename)):
        shutil.copy2(os.path.join(scr,filename), os.path.join(cwd,filename))

    # Set params in worker dir
    param_list = args[0]
    set_params(param_list, param_keys, mean_params, scale_params, scr=cwd)

    # Calculate properties
    properties_list = calculate(binary, filename, scr=cwd)

    shutil.rmtree(cwd)

    return properties_list
