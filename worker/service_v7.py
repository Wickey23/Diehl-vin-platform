from __future__ import annotations

import json
import uuid

import uvicorn
from fastapi import HTTPException
from fastapi.routing import APIRoute

import service_v5 as service

# v5.15 keeps the corrected OWL flow, exact Coverage/Major Components/Product
# Registration extraction, and prevents stale local batches from blocking a new
# VIN run before the OWL browser can launch.
service.base.VERSION = '5.15'


def _remove_route(path: str, method: str) -> None:
    keep = []
    for route in service.base.app.router.routes:
        if isinstance(route, APIRoute) and route.path == path and method.upper() in route.methods:
            continue
        keep.append(route)
    service.base.app.router.routes = keep


_remove_route('/batches', 'POST')


@service.base.app.post('/batches')
def create_fresh_batch(body: service.base.BatchIn):
    vins = service.base.clean_vins(body.vins)
    if not vins:
        raise HTTPException(400, 'Enter at least one valid 17-character VIN.')

    path = service.base.workbook_path()
    if not path.exists():
        raise HTTPException(409, 'The shared Excel database cannot be found on this computer.')

    batch_id = str(uuid.uuid4())
    options = {'workers': 1, 'batchSize': max(1, body.batchSize)}
    c = service.base.conn()
    try:
        # A previous browser/worker shutdown can leave a batch permanently marked
        # queued/running in worker_state.db. The scheduler always picks the oldest
        # active batch, so that stale state can make a new VIN sit at 0% forever.
        # A new user-initiated run is authoritative: retire older unfinished work
        # before inserting the new active batch.
        stale = c.execute("select id from batches where status in ('queued','running','paused')").fetchall()
        for row in stale:
            old_id = row['id']
            c.execute("update batches set status='cancelled', completed_at=? where id=?", (service.base.now(), old_id))
            c.execute(
                "update items set status='cancelled', completed_at=?, error_message=coalesce(error_message, ?) "
                "where batch_id=? and status in ('queued','retry','running')",
                (service.base.now(), 'Superseded by a newer VIN run.', old_id),
            )

        c.execute(
            'insert into batches(id,status,total_vins,lookup_mode,options,created_at) values(?,?,?,?,?,?)',
            (batch_id, 'queued', len(vins), body.lookupMode, json.dumps(options), service.base.now()),
        )
        for i, vin in enumerate(vins):
            c.execute(
                'insert into items(id,batch_id,vin,queue_position,status,attempts) values(?,?,?,?,?,0)',
                (str(uuid.uuid4()), batch_id, vin, i, 'queued'),
            )
        c.commit()
    finally:
        c.close()

    print(f'VIN batch {batch_id}: queued {len(vins)} VIN(s); stale active batches cleared.', flush=True)
    return {'batchId': batch_id, 'total': len(vins), 'fresh': True}


if __name__ == '__main__':
    uvicorn.run(service.base.app, host='127.0.0.1', port=service.base.PORT, log_level='warning')
