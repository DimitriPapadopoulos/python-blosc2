#######################################################################
# Copyright (c) 2019-present, Blosc Development Team <blosc@blosc.org>
# All rights reserved.
#
# This source code is licensed under a BSD-style license (found in the
# LICENSE file in the root directory of this source tree)
#######################################################################

# Benchmark for computing a fancy index of a blosc2 array

import numpy as np
import ndindex
import blosc2
import time
import matplotlib.pyplot as plt
import zarr
import h5py
import pickle
import os

plt.rcParams.update({'text.usetex':False,'font.serif': ['cm'],'font.size':16})
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rc('text', usetex=False)
plt.rc('font',**{'serif':['cm']})
plt.style.use('seaborn-v0_8-paper')

NUMPY = True
BLOSC = True
ZARR = True
HDF5 = True
SPARSE = True

if HDF5:
    SPARSE = True # HDF5 takes too long for non-sparse indexing

def genarray(r, verbose=True):
    d = int((r*2**30/8))
    shape = (d,)
    chunks = (d // 4,)
    blocks = (max(d // 10, 1),)
    t = time.time()
    arr = blosc2.linspace(0, 1000, num=np.prod(shape), shape=shape, dtype=np.float64, urlpath=f'linspace{r}1D.b2nd', mode='w')
    t = time.time() - t
    arrsize = np.prod(arr.shape) * arr.dtype.itemsize / 2 ** 30
    if verbose:
        print(f"Array shape: {arr.shape}")
        print(f"Array size: {arrsize:.6f} GB")
        print(f"Time to create array: {t:.6f} seconds")
    return arr, arrsize


target_sizes = np.float64(np.array([.2, .5, 1, 2, 5, 10]))
rng = np.random.default_rng()
blosctimes = []
nptimes = []
zarrtimes = []
h5pytimes = []
genuine_sizes = []
for d in target_sizes:
    arr, arrsize = genarray(d)
    genuine_sizes += [arrsize]
    idx = rng.integers(low=0, high=arr.shape[0], size=(1000,)) if SPARSE else rng.integers(low=0, high=arr.shape[0], size=(arr.shape[0]//4,))
    sorted_idx = np.unique(np.sort(idx))
    ## Test fancy indexing for different use cases
    def timer(arr):
        time_list = []
        if not (HDF5 or ZARR):
             b = arr[[[sorted_idx], [idx]]]
             time_list += [time.time() - t]
             t = time.time()
        t = time.time()
        b = arr[sorted_idx] if HDF5 else arr[idx]
        time_list += [time.time() - t]
        return np.array(time_list)

    nparr = arr[:]
    if BLOSC:
        blosctimes += [timer(arr)]
    if NUMPY:
        nptimes += [timer(nparr)]
    if ZARR:
        z_test = zarr.create_array(store='data/example.zarr', shape=arr.shape, chunks=arr.chunks,
                                   dtype=nparr.dtype, overwrite=True)
        z_test[:] = nparr
        zarrtimes += [timer(z_test)]
    if HDF5:
        with h5py.File('my_hdf5_file.h5', 'w') as f:
            dset = f.create_dataset("init", data=nparr, chunks=arr.chunks)
            h5pytimes += [timer(dset)]

blosctimes = np.array(blosctimes)
nptimes = np.array(nptimes)
zarrtimes = np.array(zarrtimes)
h5pytimes = np.array(h5pytimes)
labs=''
width = 0.2
result_tuple = (
    ["Numpy", nptimes, -2 * width],
    ["Blosc2", blosctimes, -width],
    ["Zarr", zarrtimes, 0],
    ["HDF5", h5pytimes, width]
)

x = np.arange(len(genuine_sizes))
# Create barplot for Numpy vs Blosc vs Zarr vs H5py
for i, r in enumerate(result_tuple):
    if r[1].shape != (0,):
        label, times, w = r
        c = ['b', 'r', 'g', 'm'][i]
        mean = times.mean(axis=1)
        err = (mean - times.min(axis=1), times.max(axis=1)-mean)
        plt.bar(x + w, mean, width, color=c, label=label, yerr=err, capsize=5, ecolor='k',
        error_kw=dict(lw=2, capthick=2, ecolor='k'))
        labs+=label

filename = f"results{labs}1Dsparse" if SPARSE else f"results{labs}1D"
with open(filename+".pkl", 'wb') as f:
    pickle.dump({'times':result_tuple, 'sizes':genuine_sizes}, f)

plt.xlabel('Array size (GB)')
plt.legend()
plt.xticks(x-width, np.round(genuine_sizes, 2))
plt.ylabel("Time (s)")
plt.title(f"Fancy indexing performance comparison, 1D {' sparse' if SPARSE else ''}")
plt.gca().set_yscale('log')
plt.savefig(f'plots/{filename}.png', format="png")
plt.show()

print("Finished everything!")
