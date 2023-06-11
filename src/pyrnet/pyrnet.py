# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/pyrnet/pyrnet.ipynb.

# %% auto 0
__all__ = ['campaign_pfx', 'DATA_URL', 'FNAME_FMT_HDCP2', 'SOLCONST', 'MAX_MISSING', 'MIN_GOOD', 'get_elements',
           'parse_thredds_catalog', 'lookup_fnames', 'read_hdcp2', 'read_thredds', 'read_pyrnet', 'read_calibration',
           'get_pyrnet_mapping', 'meta_lookup']

# %% ../../nbs/pyrnet/pyrnet.ipynb 2
from collections.abc import Iterable
from xml.dom import minidom
from urllib.request import urlopen
import parse
import os
import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import interp1d
from toolz import valfilter, cons, merge, merge_with
import pkg_resources as pkg_res

# python -m pip install git+https://github.com/hdeneke/trosat-base.git#egg=trosat-base
from trosat import sunpos as sp

from . import utils as pyrutils

# %% ../../nbs/pyrnet/pyrnet.ipynb 5
# campaign file name map for hdcp2 data
campaign_pfx = {
    'eifel': 'hope',
    'hope_juelich': 'hope',
    'hope_melpitz': 'hopm',
    'lindenberg': 'ioprao',
    'melcol': 'mcol',
}

# TROPOS thredds urls templates
DATA_URL = "https://tds.tropos.de/thredds/dodsC/scccJher/{dt:%Y}_{campaign}/"
FNAME_FMT_HDCP2 = '{campaign_pfx}_trop_pyrnet00_l1_rsds_v00_{dt:%Y%m%d}000000.nc'

# configuration constants
SOLCONST = 1359.0 # Solar constant in Wm-2
MAX_MISSING = 1000 # Maximum allowed number of missing records
MIN_GOOD = 85400 # Minimum allowed number of good records


# %% ../../nbs/pyrnet/pyrnet.ipynb 7
def get_elements(url, tag_name='dataset', attribute_name='urlPath'):
  """Get elements from an XML file"""
  # usock = urllib2.urlopen(url)
  usock = urlopen(url)
  xmldoc = minidom.parse(usock)
  usock.close()
  tags = xmldoc.getElementsByTagName(tag_name)
  attributes=[]
  for tag in tags:
    attribute = tag.getAttribute(attribute_name)
    attributes.append(attribute)
  return attributes

def parse_thredds_catalog(url, fname_format):
    """Parse Thredds server catalog and return pd.Dataframe of file name format variables."""
    fname_format = fname_format.replace("%Y-%m-%d","ti")
    tfiles = get_elements(url)
    results = False
    for fn in tfiles:
        fn = os.path.basename(fn)
        res = parse.parse(fname_format, fn)
        if res is None:
            continue
        if not results:
            results = {k:[v] for k,v in res.named.items()}
        else:
            results = merge_with(lambda x: list(cons(x[1],x[0])), results, res.named)
    return pd.DataFrame.from_dict(results)

def lookup_fnames(date, *, station, lvl, campaign, collection):
    """Parse Thredds server files and return list of filenames matching the date, station, campaign and collection configuration."""
    date = pyrutils.to_datetime64(date)

    if not isinstance(station, Iterable):
        station=[station]

    fn = pkg_res.resource_filename("pyrnet", "share/pyrnet_config.json")
    pyrcfg = pyrutils.read_json(fn)

    # construct catalog url
    catalog_url = DATA_URL.format(dt=pd.to_datetime(date),campaign=campaign)
    catalog_url = catalog_url.replace("dodsC","catalog")
    catalog_url += f"{lvl}/catalog.xml"
    catalog = parse_thredds_catalog(catalog_url, pyrcfg[f"output_{lvl}"])

    # file name blueprint
    fname = DATA_URL + f"{lvl}/"+ pyrcfg[f"output_{lvl}"]

    fnames = []
    for st in station:
        if collection is None:
            c = catalog.query(f'station=={st}')
            col = np.nanmax(c['collection'])
        else:
            col = collection

        if lvl=='l1a':
            c = catalog.query(f'station=={st} & collection=={col}').reset_index()
            startdts = c["startdt"]
            enddts = c["enddt"]
            # get file index with maintenance interaval including date
            idate_start = np.sum(date>=startdts)-1
            idate_end = np.sum(date>enddts)
            if (idate_start==-1) or (idate_end==enddts.size):
                raise ValueError(f"File of level {lvl} at date {date} does not exist.")

            fnames.append(
                pyrcfg[f"output_{lvl}"].format(
                    startdt=pd.to_datetime(startdts[idate_end]),
                    enddt=pd.to_datetime(enddts[idate_end]),
                    campaign=campaign,
                    station=st,
                    collection=col,
                    sfx="nc"
                )
            )
            if idate_end!=idate_start: # date is on a maintenance day -> combine two datasets
                fnames.append(
                    pyrcfg[f"output_{lvl}"].format(
                        startdt=pd.to_datetime(startdts[idate_start]),
                        enddt=pd.to_datetime(enddts[idate_start]),
                        campaign=campaign,
                        station=st,
                        collection=col,
                        sfx="nc"
                    )
                )

        else:
            fnames.append(
                pyrcfg[f"output_{lvl}"].format(
                    dt=pd.to_datetime(date),
                    campaign=campaign,
                    station=st,
                    collection=col,
                    sfx="nc"
                )
            )
    return fnames

# %% ../../nbs/pyrnet/pyrnet.ipynb 12
def read_hdcp2( dt, fill_gaps=True, campaign='hope_juelich'):
    """
    Read HDCP2-formatted datafiles from the pyranometer network

    Parameters
    ----------
    dt: datetime.date
        The date of the data to read
    fill_gaps: bool
        A flag indicating whether gaps should be filled by interpolation
    campaign: str
        specify campaign ['eifel','hope_juelich','hope_melpitz','lindenberg','melcol']

    Returns
    -------
    dataset : xarray.Dataset
        The pyranometer network observations
    """
    # load dataset
    fname = DATA_URL + "old/nc/"+ FNAME_FMT_HDCP2
    fname = fname.format(dt=dt,
                         campaign=campaign,
                         campaign_pfx=campaign_pfx[campaign])
    ds = xr.open_dataset(fname, mask_and_scale=False)

    # select good stations
    igood = (np.sum(ds.rsds.data<-900.0,axis=0)<MAX_MISSING)&(np.sum(ds.rsds_flag==1,axis=0)>MIN_GOOD)
    ds = ds.isel(nstations=igood)

    # fill gaps if requested
    if fill_gaps==True:
        x = (ds.time-ds.time[0])/np.timedelta64(1,'s')
        for i in np.arange(ds.dims['nstations']):
            y = ds.rsds.data[:,i]
            m = y>-990.0
            if not np.all(m):
                f = interp1d(x[m],y[m],'linear',bounds_error=False,fill_value='extrapolate')
                ds.rsds[~m,i]=f(x[~m])
    # add additional DataArrays
    jd = (ds.time.data-np.datetime64(sp.EPOCH_JD2000_0))/np.timedelta64(1,'D')
    ds['esd'] = sp.earth_sun_distance(jd[0]+0.5)
    szen = sp.sun_angles(jd[:,None],ds.lat.data[None,:],ds.lon.data[None,:])[0]
    ds['szen']    = xr.DataArray(szen,dims=('time','nstations'),coords={'time':ds.time.data})
    ds['mu0']     = np.cos(np.deg2rad(ds.szen))
    ds['gtrans']  = ds.rsds/ds.esd**2/SOLCONST/ds['mu0']
    return ds.rename({'rsds_flag':'qaflag','rsds':'ghi'})

# %% ../../nbs/pyrnet/pyrnet.ipynb 14
def read_thredds(dates, *, stations, campaign, lvl='l1b', collection=None):
    """
    Read PyrNet data (processed with pyrnet package) from the TROPOS thredds server. Returns one xarray Dataset merged to match the dates and stations input.
    Parameters
    ----------
    dates: list, ndarray, or scalar of type float, datetime or datetime64
        A representation of time. If float, interpreted as Julian date.
    stations: list, ndarray, or scalar of type int
        PyrNet station numbers.
    campaign: str
        Campaign identifier.
    lvl: str
        Data processing level -> 'l1a', 'l1b'. The default is 'l1b'.
    collection: int or None
        Collection number. If None, the latest available collection is looked up. The default is None.

    Returns
    -------
    xarray.Dataset
        Merged Dataset including all dates and stations specified by the input.
    """

    if not isinstance(dates,Iterable):
        dates = [dates]

    fnames = []
    for date in dates:
        fnames.extend(
            lookup_fnames(
                date=date,
                station=stations,
                lvl=lvl,
                campaign=campaign,
                collection=collection
            )
        )
    fnames = np.unique(fnames)

    url = DATA_URL.format(dt=pd.to_datetime(dates[0]), campaign=campaign)
    url += f"{lvl}/"
    urls = [url+fn for fn in fnames]

    ds = xr.open_dataset(urls[0])
    for url in urls[1:]:
        ds = xr.merge((ds,xr.open_dataset(url)))
    return ds

# %% ../../nbs/pyrnet/pyrnet.ipynb 17
# read pyrnet data and add coordinates
def read_pyrnet(date, campaign):
    """ Read pyrnet data and add coordinates
    """
    pyr = read_hdcp2(date, campaign=campaign)
    x,y = pyrutils.get_xy_coords(pyr.lon,pyr.lat)
    pyr['x'] = xr.DataArray(x,dims=('nstations'))
    pyr['y'] = xr.DataArray(y,dims=('nstations'))
    return pyr

# %% ../../nbs/pyrnet/pyrnet.ipynb 27
def read_calibration(cfile:str, cdate):
    """
    Parse calibration json file

    Parameters
    ----------
    cfile: str
        Path of the calibration.json
    cdate: list, ndarray, or scalar of type float, datetime or datetime64
        A representation of time. If float, interpreted as Julian date.
    Returns
    -------
    dict
        Calibration dictionary sorted by box number.
    """
    cdate = pyrutils.to_datetime64(cdate)
    calib = pyrutils.read_json(cfile)
    # parse calibration dates
    cdates = pd.to_datetime(list(calib.keys()), yearfirst=True).values

    # sort calib keys beginning with nearest
    # skeys = np.array(list(calib.keys()))[np.argsort(np.abs(cdate - cdates))][::-1]
    # lookup most recent key
    isort = np.argsort(cdates)
    skeys = np.array(list(calib.keys()))[isort][:np.sum(cdate>cdates)]
    # lookup calibration factors
    for i, key in enumerate(skeys):
        if i==0:
            c = calib[key].copy()
            continue
        isNone = lambda x: np.any([xi is None for xi in x])
        isNotNone = lambda x: np.all([xi is not None for xi in x])
        # update with newer calibrations which not include None values
        c.update(valfilter(isNotNone, calib[key]))
        # update only not None values
        for k,v in valfilter(isNone, calib[key]).items():
            newv = [c[k][i] if vi is None else vi for i,vi in enumerate(v)]
            c.update({k:newv})
    return c

# %% ../../nbs/pyrnet/pyrnet.ipynb 33
def get_pyrnet_mapping(fn:str, date):
    """
    Parse box - serial number mapping  json file

    Parameters
    ----------
    fn: str
        Path of the mapping.json
    date: list, ndarray, or scalar of type float, datetime or datetime64
        A representation of time. If float, interpreted as Julian date.
    Returns
    -------
    dict
        Calibration dictionary sorted by box number.
    """
    date = pyrutils.to_datetime64(date)
    pyrnetmap = pyrutils.read_json(fn)
    # parse key dates
    # require sort for lookup later
    cdates = pd.to_datetime(list(pyrnetmap.keys()), yearfirst=True).values
    isort = np.argsort(cdates)

    # lookup most recent key
    skeys = np.array(list(pyrnetmap.keys()))[isort][:np.sum(date>cdates)]

    # merge and update with the most recent map
    return  merge([pyrnetmap[key] for key in skeys])

# %% ../../nbs/pyrnet/pyrnet.ipynb 35
def meta_lookup(date,*,serial=None,box=None,cfile=None, mapfile=None):
    if cfile is None:
        cfile = pkg_res.resource_filename("pyrnet", "share/pyrnet_calibration.json")
    if mapfile is None:
        mapfile = pkg_res.resource_filename("pyrnet", "share/pyrnet_station_map.json")

    map = get_pyrnet_mapping(mapfile,date)
    calib = read_calibration(cfile,date)

    if serial is None and box is not None:
        box=int(box)
        return f"{box:03d}", map[f"{box:03d}"], calib[f"{box:03d}"]
    elif serial is not None and box is None:
        res = valfilter(lambda x: serial in x, map)
        box = list(res.keys())[0]
        serial = res[box]
        return box,serial,calib[box]
    else:
        raise ValueError("At least one of [station,box] have to be specified.")
