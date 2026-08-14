import { NextResponse } from 'next/server';
import { adminDb } from '../../../../lib/supabase-admin';
function ok(req:Request){const s=process.env.DTNA_WORKER_SECRET;return !!s&&req.headers.get('x-worker-secret')===s}
export async function POST(req:Request){
 if(!ok(req)) return NextResponse.json({error:'Unauthorized'},{status:401});
 try{const b=await req.json();const db=adminDb();const status=b.status==='complete'?'complete':b.status==='retry'?'retry':'error';
   const {error}=await db.from('lookup_batch_items').update({status,result:b.result||{},error_message:b.error||null,completed_at:status==='complete'?new Date().toISOString():null,attempts:Number(b.attempts||1)}).eq('id',b.itemId);if(error)throw error;
   if(status==='complete'&&b.result?.vin)await db.from('vehicles').upsert({vin:String(b.result.vin).toUpperCase(),serial_no:b.result.serialNo||null,model:b.result.model||null,customer:b.result.customerName||b.result.registeredCustomerName||null,in_service_date:b.result.inServiceDate||null,source:'VIN worker',extra_fields:b.result,updated_at:new Date().toISOString()},{onConflict:'vin'});
   const {data:remaining}=await db.from('lookup_batch_items').select('id',{count:'exact'}).eq('batch_id',b.batchId).in('status',['queued','running','retry']);
   if(!remaining?.length)await db.from('lookup_batches').update({status:'complete',completed_at:new Date().toISOString()}).eq('id',b.batchId);
   return NextResponse.json({ok:true});
 }catch(e){return NextResponse.json({error:e instanceof Error?e.message:'Result failed'},{status:500})}
}
