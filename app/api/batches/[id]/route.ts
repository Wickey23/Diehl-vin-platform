import { NextResponse } from 'next/server';
import { adminDb } from '../../../../lib/supabase-admin';

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const db = adminDb();
    const [{ data: batch, error }, { data: items }] = await Promise.all([
      db.from('lookup_batches').select('*').eq('id', id).single(),
      db.from('lookup_batch_items').select('*').eq('batch_id', id).order('queue_position')
    ]);
    if (error) throw error;
    return NextResponse.json({ batch, items: items || [] });
  } catch (e) { return NextResponse.json({ error: e instanceof Error ? e.message : 'Not found' }, { status: 404 }); }
}
