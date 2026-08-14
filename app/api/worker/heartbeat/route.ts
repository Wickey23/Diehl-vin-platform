import { NextResponse } from 'next/server';
import { adminDb } from '../../../../lib/supabase-admin';
function ok(req:Request){const s=process.env.DTNA_WORKER_SECRET;return !!s&&req.headers.get('x-worker-secret')===s}
export async function POST(req:Request){
  if(!ok(req)) return NextResponse.json({error:'Unauthorized'},{status:401});
  try{const body=await req.json();const db=adminDb();const workerId=String(body.workerId||'windows-worker');
    const {error}=await db.from('worker_status').upsert({worker_id:workerId,hostname:body.hostname||'',dtna_status:body.dtnaStatus||'unknown',outlook_status:body.outlookStatus||'unknown',onedrive_status:body.onedriveStatus||'unknown',master_workbook:body.masterWorkbook||'',details:body.details||{},last_seen:new Date().toISOString()},{onConflict:'worker_id'});if(error)throw error;return NextResponse.json({ok:true});
  }catch(e){return NextResponse.json({error:e instanceof Error?e.message:'Heartbeat failed'},{status:500})}
}
export async function GET(){try{const db=adminDb();const {data}=await db.from('worker_status').select('*').order('last_seen',{ascending:false}).limit(1).maybeSingle();return NextResponse.json({worker:data||null})}catch(e){return NextResponse.json({worker:null},{status:200})}}
