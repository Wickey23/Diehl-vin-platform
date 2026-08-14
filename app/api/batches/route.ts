import { NextResponse } from 'next/server';
import { adminDb } from '../../../lib/supabase-admin';

function vinsFrom(input: unknown) {
  const raw = Array.isArray(input) ? input.join('\n') : String(input || '');
  return [...new Set(raw.split(/[\s,;]+/).map(v => v.trim().toUpperCase()).filter(v => /^[A-HJ-NPR-Z0-9]{17}$/.test(v)))];
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const vins = vinsFrom(body.vins);
    if (!vins.length) return NextResponse.json({ error: 'Enter at least one valid 17-character VIN.' }, { status: 400 });
    const db = adminDb();
    const options = {
      workers: Math.max(1, Math.min(8, Number(body.workers || 1))),
      batchSize: Math.max(1, Number(body.batchSize || 100)),
      retryRounds: Math.max(0, Number(body.retryRounds || 3)),
      batchPause: Math.max(0, Number(body.batchPause || .5)),
      retryPause: Math.max(0, Number(body.retryPause || 3))
    };
    const { data: batch, error } = await db.from('lookup_batches').insert({ lookup_mode: body.lookupMode || 'in_service_customer', total_vins: vins.length, status: 'queued', options }).select().single();
    if (error) throw error;
    const rows = vins.map((vin, index) => ({ batch_id: batch.id, vin, queue_position: index, status: 'queued' }));
    const queued = await db.from('lookup_batch_items').insert(rows);
    if (queued.error) throw queued.error;
    return NextResponse.json({ batchId: batch.id, total: vins.length });
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : 'Unable to create batch' }, { status: 500 });
  }
}
