import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parent
LOCAL_APPDATA=Path(os.environ.get('LOCALAPPDATA',str(ROOT)))
DTNA_ROOT=LOCAL_APPDATA/'DiehlDTNAManual'/'data'
CACHE=DTNA_ROOT/'output'/'dtna_sales_orders.xlsx'
SYNC=ROOT/'dtna_runtime.py'
RESULT=Path(os.environ.get('DIEHL_RESULT_FILE',str(ROOT/'vin-results.json')))
VINS=[x.strip().upper() for x in os.environ.get('DIEHL_VINS','').splitlines() if x.strip()]


def fresh_cache():
    return CACHE.exists() and time.time()-CACHE.stat().st_mtime < 600


def sync_if_needed():
    if fresh_cache():return
    if not SYNC.exists():raise RuntimeError('DTNA sync automation is not installed')
    python=ROOT/'.venv'/'Scripts'/'python.exe'
    completed=subprocess.run([str(python if python.exists() else sys.executable),str(SYNC)],cwd=str(ROOT),check=False)
    if completed.returncode!=0:
        raise RuntimeError('DTNA refresh failed before VIN lookup. Check the DTNA window for the exact error.')


def pick(row,*names):
    for name in names:
        if name in row and pd.notna(row[name]) and str(row[name]).strip():return str(row[name]).strip()
    return ''


def main():
    if not VINS:
        RESULT.write_text('{}',encoding='utf-8');return
    sync_if_needed()
    if not CACHE.exists():raise RuntimeError('DTNA AUTO VIN output was not created')
    df=pd.read_excel(CACHE,dtype=str).fillna('')
    cols={str(c).strip().lower():c for c in df.columns}
    vin_col=cols.get('vin')
    if not vin_col:raise RuntimeError('DTNA AUTO VIN output has no VIN column')
    wanted=set(VINS);out={}
    for _,series in df.iterrows():
        vin=str(series.get(vin_col,'')).strip().upper()
        if vin not in wanted:continue
        row=series.to_dict()
        out[vin]={
            'vin':vin,
            'verificationStatus':'Verified',
            'inServiceStatus':'In Service' if pick(row,'inServiceDate','In-Service Date','In Service Date') else '',
            'inServiceDate':pick(row,'inServiceDate','In-Service Date','In Service Date'),
            'customerName':pick(row,'customer','Customer','customerName','Customer Name'),
            'orderedCustomerName':pick(row,'customer','Customer'),
            'model':pick(row,'baseMdl','Base Model','model'),
            'serialNo':pick(row,'serialNo','Serial Number','leadSerialNo'),
        }
    RESULT.write_text(json.dumps(out,indent=2),encoding='utf-8')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        RESULT.write_text(json.dumps({'_error':str(exc)}),encoding='utf-8')
        raise
