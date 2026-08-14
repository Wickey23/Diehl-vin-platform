import { NextResponse } from 'next/server';
import { adminDb } from '../../../../lib/supabase-admin';
export async function GET(){
  try{
    const db=adminDb();
    const {data,error}=await db.from('lookup_batches').select('*').in('status',['queued','running','paused']).order('created_at',{ascending:false}).limit(1).maybeSingle();
    if(error) throw error;
    return NextResponse.json({batch:data||null});
  }catch(e){return NextResponse.json({error:e instanceof Error?e.message:'Unable to load batch'},{status:500})}
}
