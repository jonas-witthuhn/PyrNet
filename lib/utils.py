# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/lib_utils.ipynb.

# %% auto 0
__all__ = ['pairwise_distance_matrix', 'gauss_fwin_fwhm', 'gauss_fwin', 'smooth_fwhm', 'smooth']

# %% ../nbs/lib_utils.ipynb 1
from numpy.typing import ArrayLike, NDArray
import numpy as np
from scipy.signal.windows import gaussian

# %% ../nbs/lib_utils.ipynb 4
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

# %% ../nbs/lib_utils.ipynb 10
def gauss_fwin_fwhm(fwhm, N=86400):
    """
    # convert scale parameter to FWHM of Normal distribution
    # see https://en.wikipedia.org/wiki/Full_width_at_half_maximum#Normal_distribution
    Parameters
    ----------
    fwhm: float
        FWHM of the gaussian distribution
    N: int
        Number of points in the output window. If zero, an empty array is returned. An exception is thrown when it is negative.
        The default is 86400 (seconds per day).

    Returns
    -------
    w: ndarray
        Frequency response of the gaussian window
    """
    f = 2.0*np.sqrt(2*np.log(2))
    sig = fwhm/f
    g  = gaussian(N, sig, sym=False)/np.sqrt(2*np.pi)/sig
    return np.fft.fft(np.roll(g, np.floor_divide(N, 2)))

def gauss_fwin(J, N=86400):
    """
    # convert scale parameter to FWHM of Normal distribution
    # see https://en.wikipedia.org/wiki/Full_width_at_half_maximum#Normal_distribution
    Parameters
    ----------
    J: float
        scale parameter for FWHM, with FWHM=60*2**J
    N: int
        Number of points in the output window. If zero, an empty array is returned. An exception is thrown when it is negative.
        The default is 86400 (seconds per day).

    Returns
    -------
    w: ndarray
        Frequency response of the gaussian window
    """
    fwhm = 60.*2**J
    return gauss_fwin_fwhm(fwhm, N=N)



# %% ../nbs/lib_utils.ipynb 12
def smooth_fwhm(y, fwhm, axis=0):
    # smooth data with gaussian window by convolution
    Y = np.fft.fft(y, axis=axis)
    W = gauss_fwin_fwhm(fwhm, y.shape[axis])
    if y.ndim > 1:
        W = np.expand_dims(W, axis=axis).T
    return np.fft.ifft(Y * W, axis=axis).real

def smooth(y, J, axis=0):
    # smooth data with gaussian window by convolution
    fwhm = 60.*2**J
    return smooth_fwhm(y, fwhm, axis=axis)

