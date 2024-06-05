#######################################################################
# Copyright (c) 2019-present, Blosc Development Team <blosc@blosc.org>
# All rights reserved.
#
# This source code is licensed under a BSD-style license (found in the
# LICENSE file in the root directory of this source tree)
#######################################################################

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import blosc2

import httpx


def _xget(url, params=None, headers=None, timeout=15, auth_cookie=None):
    if auth_cookie:
        headers = headers.copy() if headers else {}
        headers['Cookie'] = auth_cookie
    response = httpx.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response


def get(url, params=None, headers=None, timeout=15, model=None,
        auth_cookie=None):
    response = _xget(url, params, headers, timeout, auth_cookie)
    json = response.json()
    return json if model is None else model(**json)


def fetch_data(path, sub_url, params, auth_cookie=None):
    response = _xget(f'{sub_url}api/fetch/{path}', params=params,
                     auth_cookie=auth_cookie)
    data = response.content
    try:
        data = blosc2.decompress2(data)
    except (ValueError, RuntimeError):
        data = blosc2.ndarray_from_cframe(data)
        data = data[:] if data.ndim == 1 else data[()]
    return data


def slice_to_string(slice_):
    if slice_ is None or slice_ == () or slice_ == slice(None):
        return ''
    slice_parts = []
    if not isinstance(slice_, tuple):
        slice_ = (slice_,)
    for index in slice_:
        if isinstance(index, int):
            slice_parts.append(str(index))
        elif isinstance(index, slice):
            start = index.start or ''
            stop = index.stop or ''
            if index.step not in (1, None):
                raise IndexError('Only step=1 is supported')
            # step = index.step or ''
            slice_parts.append(f"{start}:{stop}")
    return ", ".join(slice_parts)


class C2Array(blosc2.Operand):
    def __init__(self, path, /,  sub_url, auth_cookie=None):
        """Create an instance of a remote NDArray.

        Parameters
        ----------
        path: str
            The path to the remote NDArray file (root + file name) as
            a posix path.
        sub_url: str
            The base URL (slash-terminated) of the subscriber to query.
        auth_cookie: str
            An optional cookie to authorize requests via HTTP.

        Returns
        -------
        out: C2Array

        """
        self.path = path
        self.sub_url = sub_url
        self.auth_cookie = auth_cookie
        self.meta = get(f'{sub_url}api/info/{self.path}',
                        auth_cookie=self.auth_cookie)

    def __getitem__(self, slice_: int | slice | Sequence[slice]) -> np.ndarray:
        """
        Get a slice of the array.

        Parameters
        ----------
        slice_ : int, slice, tuple of ints and slices, or None
            The slice to fetch.

        Returns
        -------
        out: numpy.ndarray
            A numpy.ndarray containing the data slice.
        """
        slice_ = slice_to_string(slice_)
        data = fetch_data(self.path, self.sub_url,
                          {'slice_': slice_},
                          auth_cookie=self.auth_cookie)
        return data

    @property
    def shape(self):
        """The shape of the remote array"""
        return tuple(self.meta['shape'])

    @property
    def chunks(self):
        """The chunks of the remote array"""
        return tuple(self.meta['chunks'])

    @property
    def blocks(self):
        """The blocks of the remote array"""
        return tuple(self.meta['blocks'])

    @property
    def dtype(self):
        """The dtype of the remote array"""
        return self.meta['dtype']

    @property
    def ext_shape(self):
        """The ext_shape of the remote array"""
        return tuple(self.meta['ext_shape'])