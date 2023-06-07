# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/pyrnet/utils.ipynb.

# %% auto 0
__all__ = ['EPOCH_JD_2000_0', 'to_datetime64', 'read_json', 'pick', 'omit', 'get_var_attrs', 'get_attrs_enc', 'get_xy_coords',
           'pairwise_distance_matrix', 'gauss_fwin_fwhm', 'gauss_fwin', 'smooth_fwhm', 'smooth']

# %% ../../nbs/pyrnet/utils.ipynb 2
from numpy.typing import ArrayLike, NDArray
import numpy as np
from scipy.signal.windows import gaussian
import jstyleson as json
from addict import Dict as adict
from operator import itemgetter
from toolz import keyfilter

# python -m pip install git+https://github.com/hdeneke/trosat-base.git#egg=trosat-base
import trosat.sunpos as sp

# %% ../../nbs/pyrnet/utils.ipynb 5
EPOCH_JD_2000_0 = np.datetime64("2000-01-01T12:00")
def to_datetime64(time, epoch=EPOCH_JD_2000_0):
    """
    Convert various representations of time to datetime64.

    Parameters
    ----------
    time : list, ndarray, or scalar of type float, datetime or datetime64
        A representation of time. If float, interpreted as Julian date.
    epoch : np.datetime64, default JD2000.0
        The epoch to use for the calculation

    Returns
    -------
    datetime64 or ndarray of datetime64
    """
    jd = sp.to_julday(time, epoch=epoch)
    jdms = np.int64(86_400_000*jd)
    return epoch + jdms.astype('timedelta64[ms]')

# %% ../../nbs/pyrnet/utils.ipynb 8
def read_json(fpath: str, *, object_hook: type = adict, cls = None) -> dict:
    """ Parse json file to python dict.
    """
    with open(fpath,"r") as f:
        js = json.load(f, object_hook=object_hook, cls=cls)
        return js

def pick(whitelist: list[str], d: dict) -> dict:
    """ Keep only whitelisted keys from input dict.
    """
    return keyfilter(lambda k: k in whitelist, d)

def omit(blacklist: list[str], d: dict) -> dict:
    """ Omit blacklisted keys from input dict.
    """
    return keyfilter(lambda k: k not in blacklist, d)

def get_var_attrs(d: dict) -> dict:
    """
    Parse cf-compliance dictionary.

    Parameters
    ----------
    d: dict
        Dict parsed from cf-meta json.

    Returns
    -------
    dict
        Dict with netcdf attributes for each variable.
    """
    get_vars = itemgetter("variables")
    get_attrs = itemgetter("attributes")
    vattrs = {k: get_attrs(v) for k,v in get_vars(d).items()}
    for k,v in get_vars(d).items():
        vattrs[k].update({
            "dtype": v["type"],
            "gzip":True,
            "complevel":6
        })
    return vattrs

def get_attrs_enc(d : dict) -> (dict,dict):
    """ Split variable attributes in attributes and encoding-attributes.
    """
    _enc_attrs = {
        "scale_factor",
        "add_offset",
        "_FillValue",
        "dtype",
        "zlib",
        "gzip",
        "complevel",
        "calendar",
    }
    # extract variable attributes
    vattrs = {k: omit(_enc_attrs, v) for k, v in d.items()}
    # extract variable encoding
    vencode = {k: pick(_enc_attrs, v) for k, v in d.items()}
    return vattrs, vencode

# %% ../../nbs/pyrnet/utils.ipynb 13
def get_xy_coords(lon, lat, lonc=None, latc=None):
    """
    Calculate Cartesian coordinates of network stations, relative to the mean
    lon/lat of the stations
    """
    n  = len(lon)
    if lonc is None:
        lonc = lon.mean()
    if latc is None:
        latc = lat.mean()

    az, _, d = np.array([GEOD.inv(lonc, latc, lon[i], lat[i]) for i in range(n)]).T
    x = d*np.sin(np.deg2rad(az))
    y = d*np.cos(np.deg2rad(az))
    return x,y

# %% ../../nbs/pyrnet/utils.ipynb 14
def pairwise_distance_matrix( x: ArrayLike, y: ArrayLike ) -> NDArray:
    """
    Get square matrix with Euclidian distances of stations

    Parameters
    ----------
    x: array_like
        X coordinates
    y: array_like
        Y coordinates

    Returns
    -------
    ndarray
        A square matrix with Euclidian distances of stations
    """
    x = np.array(x)
    y = np.array(y)
    return np.sqrt( (x[None,:]-x[:,None])**2+(y[None,:]-y[:,None])**2 )

# %% ../../nbs/pyrnet/utils.ipynb 20
def gauss_fwin_fwhm(fwhm: float, N: int = 86400) -> NDArray:
    """
    Convert scale parameter to FWHM of Normal distribution see
    [https://en.wikipedia.org/wiki/Full_width_at_half_maximum#Normal_distribution]

    Parameters
    ----------
    fwhm: float
        FWHM of the gaussian distribution
    N: int
        Number of points in the output window. If zero, an empty array is returned. An exception is thrown when it is negative.
        The default is 86400 (seconds per day).

    Returns
    -------
    ndarray
        Frequency response of the gaussian window
    """
    f = 2.0*np.sqrt(2*np.log(2))
    sig = fwhm/f
    g  = gaussian(N, sig, sym=False)/np.sqrt(2*np.pi)/sig
    return np.fft.fft(np.roll(g, np.floor_divide(N, 2)))

def gauss_fwin(J: float, N: int=86400) -> NDArray:
    """
    Convert scale parameter to FWHM of Normal distribution see
    [https://en.wikipedia.org/wiki/Full_width_at_half_maximum#Normal_distribution]

    Parameters
    ----------
    J: float
        scale parameter for FWHM, with FWHM=60*2**J
    N: int
        Number of points in the output window. If zero, an empty array is returned. An exception is thrown when it is negative.
        The default is 86400 (seconds per day).

    Returns
    -------
    ndarray
        Frequency response of the gaussian window
    """
    fwhm = 60.*2**J
    return gauss_fwin_fwhm(fwhm, N=N)



# %% ../../nbs/pyrnet/utils.ipynb 22
def smooth_fwhm(y: ArrayLike, fwhm: float, axis: int = 0) -> NDArray:
    """
    Smooth data with gaussian window by convolution

    Parameters
    ----------
    y: array_like
        Input array.
    fwhm: float
        FWHM of the gaussian window to be convolved with the input array.
    axis: int, optional
        Axis over which to smoothing is applied.

    Returns
    -------
    ndarray
        Smoothed array of the same shape as the input array `y`.
    """
    Y = np.fft.fft(y, axis=axis)
    W = gauss_fwin_fwhm(fwhm, y.shape[axis])
    if y.ndim > 1:
        W = np.expand_dims(W, axis=axis).T
    return np.fft.ifft(Y * W, axis=axis).real

def smooth(y: ArrayLike, J: float, axis: int = 0) -> NDArray:
    """
    Smooth data with gaussian window by convolution

    Parameters
    ----------
    y: array_like
        Input array.
    J: float
        Scale parameter for the FWHM (FWHM=60*2**J) of the
        gaussian window to be convolved with the input array.
    axis: int, optional
        Axis over which to smoothing is applied.

    Returns
    -------
    ndarray
        Smoothed array of the same shape as the input array `y`.
    """
    fwhm = 60.*2**J
    return smooth_fwhm(y, fwhm, axis=axis)

