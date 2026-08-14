import { NextResponse } from "next/server";
export async function GET(){return NextResponse.json({ok:true,service:"diehl-vin-platform",databaseConfigured:Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL),workerConfigured:Boolean(process.env.DTNA_WORKER_URL)})}
