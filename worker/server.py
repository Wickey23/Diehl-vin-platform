import json, os, re, socket, sqlite3, subprocess, threading, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parent

def load_env():
    p=ROOT/'worker.env'
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1); os.environ.setdefault(k.strip(),os.path.expandvars(v.strip().strip('"')))
load_env()

PORT=int(os.environ.get('PORT','8765'))
ACCESS_KEY=os.environ.get('WORKER_ACCESS_KEY','change-me')
WORKBOOK=Path(os.path.expandvars(os.environ.get('MASTER_WORKBOOK',r'C:\Users\sameer\OneDrive - Diehl\'s Truck World\Documents\VIN In-Service Checker\VIN_Master_Data.xlsx')))
DB=ROOT/'worker_state.db'
ALLOWED=[x.strip() for x in os.environ.get('ALLOWED_ORIGINS','https://diehl-vin-platform.vercel.app,http://localhost:3000').split(',') if x.strip()]
app=FastAPI(title='Diehl VIN Worker',version='2.0')
app.add_middleware(CORSMiddleware,allow_origins=ALLOWED,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
excel_lock=threading.Lock(); scheduler_lock=threading.Lock(); stop_event=threading.Event()

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db(); c.executescript('''
    create table if not exists batches(id text primary key,status text,total_vins integer,lookup_mode text,options text,created_at text,started_at text,completed_at text);
    create table if not exists items(id text primary key,batch_id text,vin text,queue_position integer,status text,attempts integer default 0,result text,error_message text,started_at text,completed_at text);
    create index if not exists items_batch on items(batch_id,queue_position);
    create table if not exists events(id integer primary key autoincrement,kind text,payload text,created_at text);
    '''); c.commit(); c.close()
init_db()

def auth(x_worker_key:str|None):
    if not ACCESS_KEY or ACCESS_KEY=='change-me' or x_worker_key!=ACCESS_KEY: raise HTTPException(401,'Invalid worker access key')

def proc_running(*names):
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            n=(p.info.get('name') or '').lower()
            if any(x.lower() in n for x in names): return True
    except Exception: pass
    return False

def workbook_status():
    return {'exists':WORKBOOK.exists(),'path':str(WORKBOOK),'size':WORKBOOK.stat().st_size if WORKBOOK.exists() else 0,'modified':datetime.fromtimestamp(WORKBOOK.stat().st_mtime).isoformat() if WORKBOOK.exists() else None}

def header_map(ws): return {str(c.value or '').strip():i for i,c in enumerate(next(ws.iter_rows()))}
def serializable(v): return v.isoformat() if hasattr(v,'isoformat') else v

def read_master(vins:set[str]):
    out={}
    if not WORKBOOK.exists(): return out
    with excel_lock:
        wb=load_workbook(WORKBOOK,read_only=True,data_only=True); ws=wb['VIN Data'] if 'VIN Data' in wb.sheetnames else wb.active
        headers=[str(c.value or '').strip() for c in next(ws.iter_rows())]; idx={h:i for i,h in enumerate(headers)}; vi=idx.get('VIN',0)
        for row in ws.iter_rows(values_only=True):
            vin=str(row[vi] or '').strip().upper()
            if vin in vins:
                out[vin]={headers[i]:serializable(row[i]) for i in range(min(len(headers),len(row))) if headers[i] and row[i] not in (None,'')}
                if len(out)==len(vins): break
        wb.close()
    return out

def normalize(vin,row):
    def g(*names):
        for n in names:
            if row.get(n) not in (None,''): return row[n]
    return {'vin':vin,'verificationStatus':g('Verification Status'),'inServiceStatus':g('In-Service Status'),'inServiceDate':g('In-Service Date'),'mileage':g('Mileage'),'customerResult':g('Customer Result'),'customerName':g('Customer Name'),'registeredCustomerName':g('Registered Customer Name'),'registeredCustomerAccount':g('Registered Customer Account'),'orderedCustomerName':g('Ordered Customer Name'),'raw':row}

def ensure_columns(ws,cols):
    headers=[str(c.value or '').strip() for c in ws[1]]; idx={h:i+1 for i,h in enumerate(headers) if h}
    for col in cols:
        if col not in idx:
            ws.cell(1,len(headers)+1,col); headers.append(col); idx[col]=len(headers)
    return idx

def write_result_to_excel(vin,result):
    if not WORKBOOK.exists(): return
    with excel_lock:
        wb=load_workbook(WORKBOOK); ws=wb['VIN Data'] if 'VIN Data' in wb.sheetnames else wb.active
        idx=ensure_columns(ws,['VIN','Verification Status','In-Service Status','In-Service Date','Mileage','Customer Result','Customer Name','Registered Customer Name','Registered Customer Account','Ordered Customer Name'])
        rownum=None
        for r in range(2,ws.max_row+1):
            if str(ws.cell(r,idx['VIN']).value or '').strip().upper()==vin: rownum=r; break
        if rownum is None: rownum=ws.max_row+1; ws.cell(rownum,idx['VIN'],vin)
        mapping={'verificationStatus':'Verification Status','inServiceStatus':'In-Service Status','inServiceDate':'In-Service Date','mileage':'Mileage','customerResult':'Customer Result','customerName':'Customer Name','registeredCustomerName':'Registered Customer Name','registeredCustomerAccount':'Registered Customer Account','orderedCustomerName':'Ordered Customer Name'}
        for key,col in mapping.items():
            if result.get(key) not in (None,''): ws.cell(rownum,idx[col],result[key])
        if 'Lookup Log' in wb.sheetnames:
            log=wb['Lookup Log']; lidx=ensure_columns(log,['Checked At','VIN','Verification Status','In-Service Status','In-Service Date','Mileage','Customer Name']); rr=log.max_row+1
            vals={'Checked At':now(),'VIN':vin,'Verification Status':result.get('verificationStatus'),'In-Service Status':result.get('inServiceStatus'),'In-Service Date':result.get('inServiceDate'),'Mileage':result.get('mileage'),'Customer Name':result.get('customerName')}
            for k,v in vals.items(): log.cell(rr,lidx[k],v)
        tmp=WORKBOOK.with_suffix('.worker.tmp.xlsx'); wb.save(tmp); wb.close(); os.replace(tmp,WORKBOOK)

def run_command(name,vins,slot=1):
    cmd=os.environ.get(name,'').strip()
    if not cmd: return {}
    result_file=ROOT/f'results-slot-{slot}.json'; result_file.unlink(missing_ok=True)
    env=os.environ.copy(); env['DIEHL_VINS']='\n'.join(vins); env['DIEHL_RESULT_FILE']=str(result_file); env['DIEHL_WORKER_SLOT']=str(slot); env['DIEHL_BROWSER_PROFILE']=str(ROOT/'browser_profiles'/f'worker-{slot}')
    subprocess.run(cmd,shell=True,env=env,cwd=str(ROOT),check=False)
    if result_file.exists():
        try:
            raw=json.loads(result_file.read_text(encoding='utf-8')); return raw if isinstance(raw,dict) else {x.get('vin','').upper():x for x in raw if isinstance(x,dict) and x.get('vin')}
        except Exception: return {}
    return {}

def process_item(item,lookup_mode,slot):
    vin=item['vin']; found=read_master({vin})
    if vin in found: return normalize(vin,found[vin]),None
    run_command('DTNA_SYNC_COMMAND',[vin],slot)
    found=read_master({vin})
    if vin in found: return normalize(vin,found[vin]),None
    looked=run_command('VIN_LOOKUP_COMMAND',[vin],slot)
    result=looked.get(vin) if isinstance(looked,dict) else None
    if result:
        result.setdefault('vin',vin); write_result_to_excel(vin,result); return result,None
    return None,'VIN not found in VIN_Master_Data.xlsx and no local lookup result was produced'

def scheduler():
    while not stop_event.is_set():
        try:
            c=db(); batch=c.execute("select * from batches where status in ('queued','running') order by created_at limit 1").fetchone()
            if not batch: c.close(); time.sleep(1); continue
            opts=json.loads(batch['options'] or '{}'); workers=max(1,min(8,int(opts.get('workers',1)))); c.execute("update batches set status='running',started_at=coalesce(started_at,?) where id=?",(now(),batch['id'])); c.commit()
            pending=c.execute("select * from items where batch_id=? and status in ('queued','retry') order by queue_position limit ?",(batch['id'],workers)).fetchall()
            if not pending:
                remaining=c.execute("select count(*) n from items where batch_id=? and status in ('queued','retry','running')",(batch['id'],)).fetchone()['n']
                if remaining==0: c.execute("update batches set status='complete',completed_at=? where id=?",(now(),batch['id'])); c.commit()
                c.close(); time.sleep(.5); continue
            for i,it in enumerate(pending): c.execute("update items set status='running',started_at=?,attempts=attempts+1 where id=?",(now(),it['id']))
            c.commit(); c.close()
            threads=[]
            def one(it,slot):
                result,err=process_item(dict(it),batch['lookup_mode'],slot); cc=db()
                if result: cc.execute("update items set status='complete',result=?,error_message=null,completed_at=? where id=?",(json.dumps(result,default=str),now(),it['id']))
                else: cc.execute("update items set status='error',error_message=?,completed_at=? where id=?",(err,now(),it['id']))
                cc.commit(); cc.close()
            for i,it in enumerate(pending):
                t=threading.Thread(target=one,args=(it,i+1),daemon=True); t.start(); threads.append(t)
            for t in threads: t.join()
            time.sleep(float(opts.get('batchPause',.5)))
        except Exception as e:
            print('scheduler error',e); time.sleep(2)
threading.Thread(target=scheduler,daemon=True).start()

class BatchIn(BaseModel):
    vins: Any; lookupMode:str='in_service_customer'; workers:int=1; batchSize:int=100; retryRounds:int=3; batchPause:float=.5; retryPause:float=3

def clean_vins(v):
    raw='\n'.join(v) if isinstance(v,list) else str(v or '')
    return list(dict.fromkeys(x.upper() for x in re.split(r'[\s,;]+',raw) if re.fullmatch(r'[A-HJ-NPR-Z0-9]{17}',x.upper())))

@app.get('/health')
def health(x_worker_key:str|None=Header(default=None)):
    auth(x_worker_key); return {'ok':True,'worker':{'worker_id':socket.gethostname(),'hostname':socket.gethostname(),'dtna_status':'browser ready' if proc_running('msedge','chrome') else 'worker ready','outlook_status':'open' if proc_running('outlook') else 'available','onedrive_status':'connected' if WORKBOOK.exists() else 'workbook missing','master_workbook':str(WORKBOOK),'last_seen':now(),'details':workbook_status()}}
@app.post('/batches')
def create_batch(body:BatchIn,x_worker_key:str|None=Header(default=None)):
    auth(x_worker_key); vins=clean_vins(body.vins)
    if not vins: raise HTTPException(400,'Enter at least one valid 17-character VIN')
    bid=str(uuid.uuid4()); opts={'workers':body.workers,'batchSize':body.batchSize,'retryRounds':body.retryRounds,'batchPause':body.batchPause,'retryPause':body.retryPause}; c=db(); c.execute('insert into batches values(?,?,?,?,?,?,?,?)',(bid,'queued',len(vins),body.lookupMode,json.dumps(opts),now(),None,None))
    for i,vin in enumerate(vins): c.execute('insert into items(id,batch_id,vin,queue_position,status,attempts) values(?,?,?,?,?,0)',(str(uuid.uuid4()),bid,vin,i,'queued'))
    c.commit(); c.close(); return {'batchId':bid,'total':len(vins)}
@app.get('/batches/resumable')
def resumable(x_worker_key:str|None=Header(default=None)):
    auth(x_worker_key); c=db(); r=c.execute("select * from batches where status in ('queued','running','paused') order by created_at desc limit 1").fetchone(); c.close(); return {'batch':dict(r) if r else None}
@app.get('/batches/{bid}')
def get_batch(bid:str,x_worker_key:str|None=Header(default=None)):
    auth(x_worker_key); c=db(); b=c.execute('select * from batches where id=?',(bid,)).fetchone(); its=c.execute('select * from items where batch_id=? order by queue_position',(bid,)).fetchall(); c.close()
    if not b: raise HTTPException(404,'Batch not found')
    out=[]
    for x in its:
        d=dict(x); d['result']=json.loads(d['result']) if d.get('result') else {}; out.append(d)
    return {'batch':dict(b),'items':out}
@app.post('/batches/{bid}/retry')
def retry(bid:str,x_worker_key:str|None=Header(default=None)):
    auth(x_worker_key); c=db(); c.execute("update items set status='retry',error_message=null,completed_at=null where batch_id=? and status in ('error','incomplete')",(bid,)); c.execute("update batches set status='queued',completed_at=null where id=?",(bid,)); c.commit(); c.close(); return {'ok':True}
@app.post('/batches/{bid}/cancel')
def cancel(bid:str,x_worker_key:str|None=Header(default=None)):
    auth(x_worker_key); c=db(); c.execute("update batches set status='cancelled',completed_at=? where id=?",(now(),bid)); c.execute("update items set status='cancelled' where batch_id=? and status in ('queued','retry')",(bid,)); c.commit(); c.close(); return {'ok':True}
@app.post('/sync')
def sync(x_worker_key:str|None=Header(default=None)):
    auth(x_worker_key); run_command('OUTLOOK_SYNC_COMMAND',[],1); return {'ok':True,'workbook':workbook_status()}

if __name__=='__main__':
    import uvicorn; uvicorn.run(app,host='0.0.0.0',port=PORT)
