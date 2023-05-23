# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/pyrnet/reports.ipynb.

# %% auto 0
__all__ = ['get_responses', 'read_logbook', 'parse_legacy_logbook', 'parse_report', 'get_qcflag']

# %% ../../nbs/pyrnet/reports.ipynb 2
import pandas as pd
from pandas._typing import (
    FilePath,
    ReadCsvBuffer,
)
import datetime as dt
import numpy as np
from toolz import assoc_in

from . import utils

# %% ../../nbs/pyrnet/reports.ipynb 7
def get_responses(
        *,
        fn: FilePath | ReadCsvBuffer[bytes] | ReadCsvBuffer[str]|None = None,
        online: dict|None = None
) -> pd.DataFrame:
    """
    Get LimeSurvey responses as pandas Dataframe providing a file or online download information.

    Parameters
    ----------
    fn: str, path object or file-like object
        Any pandas readable representation of the LimeSurvey response export file
        (.csv, sep=;, answer and question codes).
    online: dict
        Dictionary of information required to download the responses via limepy:
            * base_url -> limesurvey remote_control url
            * user_name -> account name
            * password
            * user_id -> ID of account user (usually 1)
            * sid -> Survey ID

        Minimal information stored in *online* is the base_url, other information will then be filled via user input promt.

    Returns
    -------
    pd.Dataframe
        parsed responses csv file
    """
    if fn is not None:
        # legacy support:
        if fn.endswith(".xls") or fn.endswith(".xlsx"):
            return parse_legacy_logbook(fn)
        filepath_or_buffer = fn
    elif online is not None:
        import limepy
        import getpass
        from io import StringIO
        if "base_url" not in online:
            raise ValueError
        if "user_name" not in online:
            online.update({'user_name': input("LimeSurvey Account Name: ")})
        if "password" not in online:
            online.update({'password': getpass.getpass("LimeSurvey Password: ")})
        if "user_id" not in online:
            online.update({"user_id": input("LimeSurvey User ID: ")})
        if "sid" not in online:
            online.update({'sid': input("LimeSurvey Survey ID: ")})

        csv = limepy.download.get_responses(**online)
        filepath_or_buffer = StringIO(csv)
    else:
        raise ValueError
    df = pd.read_csv(filepath_or_buffer, sep=';')
    df = df.fillna("None")
    return df

# %% ../../nbs/pyrnet/reports.ipynb 10
def read_logbook(lfile):
    '''
    Load logbook file and store it as dictionary of rec arrays with stID keys.

    Parameters
    ----------
    cfile: string
        path and filename of loogbook file -> should be .xls file
        each sheet represent a maintenance periode.
        First row of .xls file have to include column names:
            box,date,clean,clean_tilt,level,level_tilt,Hangle,Vangle,notes

    Returns
    -------
    logbook: dict{<stID>:recarray(dtype_log)}
        dict of recarray for each station ID including quality flags from each
        maintenance cicle.
    '''
    dtype_log =[
        ('box',         np.uint8),
        ('site',        'U50'),
        ('serial_pyr',  'U50'),
        ('serial_pyr_tilt', 'U50'),
        ('user',          'U50'),
        ('campaign',    'U50'),
        ('date',        'datetime64[ms]' ),
        ('clean',       np.uint8),
        ('clean_tilt',  np.uint8),
        ('level',       np.uint8),
        ('level_tilt',  np.uint8),
        ('Hangle',      'f8'),
        ('Vangle',      'f8'),
        ('notes',       'U50')
    ]
    def _parse_name(name):
        key=name.lower().strip()
        if key in ['date']:
            return 'date'
        elif key in ['clean','cleanliness','clean(pyr1)','clean1']:
            return 'clean'
        elif key in ['clean_tilt','clean2','clean(pyr2)']:
            return 'clean_tilt'
        elif key in ['level','level(pyr1)','level1']:
            return 'level'
        elif key in ['level_tilt','level(pyr2)','level2']:
            return 'level_tilt'
        elif key in ['box','station','id','pyrbox','pyranometerbox']:
            return 'box'
        elif key in ['hangle','azimuth','azi','horizontal_angle']:
            return 'Hangle'
        elif key in ['vangle','zenith','zen','vertical_angle']:
            return 'Vangle'
        elif key in ['notes','note','description']:
            return 'notes'
        elif key in ['serial','serial1','serial_pyr','pyranometerID','pyrID']:
            return 'serial_pyr'
        elif key in ['serial2','serial_pyr2','serial_pyr_tilt']:
            return 'serial_pyr_tilt'
        elif key in ['site','location']:
            return 'site'
        elif key in ['user','author']:
            return 'user'
        elif key in ['campaign']:
            return 'campaign'
        elif key == 'index':
            return False
        else:
            return False
    def _hstack2(arrays):
        return arrays[0].__array_wrap__(np.hstack(arrays))

    logbook={}
    df=pd.read_excel(lfile,sheet_name=None)#,engine='openpyxl')
    for sheet in df.keys():# read all sheets from xls file
        sh = df[sheet].dropna(axis=0,how='all',subset=['date']) #remove empty lines
        sh = sh.dropna(axis=1,how='all') # remove empty columns
        for row in sh.itertuples(index=True,name='Pandas'):
            A=np.zeros(1,dtype=dtype_log).view(np.recarray)
            for name,value in row._asdict().items():
                key=_parse_name(name)
                if key:
                    if dict(dtype_log)[key]==np.uint8 and np.isnan(value):
                        value=9
                    A[key]=value
            if str(A.box[0]) in logbook.keys():
                logbook.update({str(A.box[0]):_hstack2([logbook[str(A.box[0])],A])})
            else:
                logbook.update({str(A.box[0]):A})
    return logbook

# %% ../../nbs/pyrnet/reports.ipynb 11
def parse_legacy_logbook(fn):
    df = None
    lb = read_logbook(fn)
    for box in lb:
        lbb = lb[box]
        N = lbb['date'].shape[0]
        faccept = [1,2,3,4]
        dfb = pd.DataFrame(
            {"datestamp": lbb['date'],
             "Q00": box,
             "Q01": lbb['notes'],
             "MainQ01[comment]": np.repeat("",N),
             "MainQ02[comment]": np.repeat("",N),
             "ExtraQ01[comment]": np.repeat("",N),
             "ExtraQ02[comment]": np.repeat("",N),
             "MainQ01": [f"AO0{f}" if f in faccept else "None" for f in lbb['clean']],
             "MainQ02": [f"AO0{f}" if f in faccept else "None" for f in lbb['level']],
             "ExtraQ01": [f"AO0{f}" if f in faccept else "None" for f in lbb['clean_tilt']],
             "ExtraQ02": [f"AO0{f}" if f in faccept else "None" for f in lbb['level_tilt']],
             }
        )
        if df is None:
            df = dfb.copy()
        else:
            df = pd.concat((df,dfb),ignore_index=True)
    df = df.fillna("None")
    return df

# %% ../../nbs/pyrnet/reports.ipynb 15
_pollution_marks = {
    "None":4,
    "AO01":0,
    "AO02":1,
    "AO03":2,
    "AO04":3,
}
_alignment_marks = {
    "None":4,
    "AO01":0,
    "AO02":1,
    "AO03":2,
}
_note_keys = {
    "note_general": "Q01",
    "note_align": "MainQ01[comment]",
    "note_clean": "MainQ02[comment]",
    "note_align2": "ExtraQ01[comment]",
    "note_clean2": "ExtraQ02[comment]",
}
_mark_keys = {
    "clean": "MainQ01",
    "align": "MainQ02",
    "clean2": "ExtraQ01",
    "align2": "ExtraQ02",
}

def parse_report(
        df:  pd.DataFrame,
        date_of_maintenance: float | dt.datetime | np.datetime64 | None,
) -> dict:
    """
    Use pandas.read_csv (sep=;) to parse the survey report.

    Parameters
    ----------
    df: Dataframe
        LimeSurvey response parsed as pandas Dataframe.
    date_of_maintenance: float, datetime, datetime64 or None
        A rough date of maintenance (at least day resolution).
        If float, interpreted as Julian day from 2000-01-01T12:00.
        If None, the most recent logbook entries will be parsed.

    Returns
    -------
    dict
        Dictionary storing maintenance flags and notes by PyrNet box number.
    """
    if date_of_maintenance is not None:
        date_of_maintenance = utils.to_datetime64(date_of_maintenance)

    results = {}
    for i in range(df.shape[0]):
        box = int(df["Q00"].values[i])
        key = f"{box:03d}"

        # consider only reports +-2 days around date of maintenance
        mdate = pd.to_datetime(df['datestamp'][i])
        if date_of_maintenance is None:
            dtime = np.abs(mdate - np.max(df['datestamp']))
        else:
            dtime = np.abs(mdate - date_of_maintenance)

        if dtime > np.timedelta64(2,'D'):
            continue

        # store report in dictionary

        if key not in results:
            # initialize marks
            for mkey in _mark_keys:
                results = assoc_in(results, [key,mkey], 4)
            # initialize notes
            for nkey in _note_keys:
                results = assoc_in(results, [key,nkey], "")

        # merge notes if multiple reports exist
        for nkey in _note_keys:
            new_note = df[_note_keys[nkey]].values[i]
            update_note = (results[key][nkey]+'; '+new_note).strip('; ')
            results = assoc_in(results, [key,nkey], update_note)

        # update marks with most recent report if not None
        for mkey in _mark_keys:
            new_mark = df[_mark_keys[mkey]][i]
            if new_mark=="None":
                continue
            if mkey.startswith("clean"):
                new_mark = _pollution_marks[new_mark]
            else:
                new_mark = _alignment_marks[new_mark]
            results = assoc_in(results, [key,mkey], new_mark)
    return results


# %% ../../nbs/pyrnet/reports.ipynb 19
def get_qcflag(qc_clean, qc_level):
    """
    Aggregate quality flags.

    Parameters
    ----------
    qc_clean: int
        [0,1,2,3] [clean, slight-, moderate-, strong covered]
    qc_level: int
        [0,1,2] [good, slight misalignment, strong misalignment]

    Returns
    -------
    int
        aggregated quality flagg [0-11]
    """
    qc = (qc_level<<2) + qc_clean
    return qc

