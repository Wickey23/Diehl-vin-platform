import { NextResponse } from 'next/server';
import { adminDb } from '../../../../lib/supabase-admin';
function ok(req:Request){const s=process.env.DTNA_WORKER_SECRET;return !!s&&req.headers.get('x-worker-secret')===s}
export async function POST(req:Request){
 if(!ok(req)) return NextResponse.json({error:'Unauthorized'},{status:401});
 try{const body=await req.json();const db=adminDb();const limit=Math.max(1,Math.min(100,Number(body.limit||20)));
   const {data:batch}=await db.from('lookup_batches').select('*').in('status',['queued','running']).order('created_at',{ascending:true}).limit(1).maybeSingle();
   if(!batch)return NextResponse.json({batch:null,items:[]});
   await db.from('lookup_batches').update({status:'running',started_at:batch.started_at||new Date().toISOString(),worker_id:body.workerId||'windows-worker'}).eq('id',batch.id);
   const {data:items,error}=await db.from('lookup_batch_items').select('*').eq('batch_id',batch.id).in('status',['queued','retry']).order('queue_position').limit(limit);if(error)throw error;
   const ids=(items||[]).map(x=>x.id);if(ids.length)await db.from('lookup_batch_items').update({status:'running',started_at:new Date().toISOString()}).in('id',ids);
   return NextResponse.json({batch,items:items||[]});
 }catch(e){return NextResponse.json({error:e instanceof Error?e.message:'Claim failed'},{status:500})}
}
