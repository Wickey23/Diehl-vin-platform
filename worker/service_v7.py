from __future__ import annotations

import json
import threading
import uuid

import uvicorn
from fastapi import HTTPException
from fastapi.routing import APIRoute

import service_v5 as service

# v5.16 starts each new VIN batch immediately in a dedicated local execution
# thread. This bypasses stale/failed scheduler state that could leave a newly
# submitted VIN stuck at queued / 0% without ever opening OWL.
service.base.VERSION = '5.16'


def _remove_route(path: str, method: str) -> None:
    keep = []
    for route in service.base.app.router.routes:
        if isinstance(route, APIRoute) and route.path == path and method.upper() in route.methods:
            continue
        keep.append(route)
    service.base.app.router.routes = keep


def _finish_batch(batch_id: str) -> None:
    c = service.base.conn()
    try:
        remaining = c.execute(
            "select count(*) n from items where batch_id=? and status in ('queued','retry','running')",
            (batch_id,),
        ).fetchone()['n']
        if remaining == 0:
            c.execute(
                "update batches set status='complete', completed_at=? where id=? and status!='cancelled'",
                (service.base.now(), batch_id),
            )
            c.commit()
    finally:
        c.close()


def _process_batch_now(batch_id: str, vins: list[str]) -> None:
    """Run one user-started VIN batch immediately, independent of legacy scheduler."""
    c = service.base.conn()
    try:
        row = c.execute('select status from batches where id=?', (batch_id,)).fetchone()
        if not row or row['status'] == 'cancelled':
            return
        c.execute(
            "update batches set status='direct_running', started_at=coalesce(started_at, ?) where id=?",
            (service.base.now(), batch_id),
        )
        c.execute(
            "update items set status='running', started_at=?, attempts=attempts+1 where batch_id=? and status in ('queued','retry')",
            (service.base.now(), batch_id),
        )
        c.commit()
    finally:
        c.close()

    print(f'VIN batch {batch_id}: DIRECT START for {len(vins)} VIN(s). Launching OWL now.', flush=True)

    try:
        looked = service.base.run_lookup(vins)
        global_error = looked.get('_error') if isinstance(looked, dict) else 'OWL lookup did not return a result payload.'

        for vin in vins:
            check = service.base.conn()
            try:
                batch_state = check.execute('select status from batches where id=?', (batch_id,)).fetchone()
                if batch_state and batch_state['status'] == 'cancelled':
                    check.execute(
                        "update items set status='cancelled', completed_at=? where batch_id=? and vin=? and status='running'",
                        (service.base.now(), batch_id, vin),
                    )
                    check.commit()
                    continue
            finally:
                check.close()

            result = looked.get(vin) if isinstance(looked, dict) else None
            x = service.base.conn()
            try:
                if not isinstance(result, dict) or not result:
                    raise RuntimeError(global_error or f'OWL returned no result for {vin}.')
                if result.get('_error'):
                    raise RuntimeError(str(result.get('_error')))

                result.setdefault('vin', vin)
                service.base.write_result(vin, result)
                x.execute(
                    "update items set status='complete', result=?, error_message=null, completed_at=? where batch_id=? and vin=?",
                    (json.dumps(result, default=str), service.base.now(), batch_id, vin),
                )
                x.commit()
                print(f'VIN batch {batch_id}: COMPLETE {vin}', flush=True)
            except Exception as exc:
                x.execute(
                    "update items set status='error', error_message=?, completed_at=? where batch_id=? and vin=?",
                    (str(exc), service.base.now(), batch_id, vin),
                )
                x.commit()
                print(f'VIN batch {batch_id}: ERROR {vin}: {exc}', flush=True)
            finally:
                x.close()
    except Exception as exc:
        x = service.base.conn()
        try:
            x.execute(
                "update items set status='error', error_message=?, completed_at=? where batch_id=? and status='running'",
                (f'OWL launch/execution failed: {exc}', service.base.now(), batch_id),
            )
            x.commit()
        finally:
            x.close()
        print(f'VIN batch {batch_id}: FATAL direct execution error: {exc}', flush=True)
    finally:
        _finish_batch(batch_id)


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
    options = {'workers': 1, 'batchSize': max(1, body.batchSize), 'execution': 'direct'}
    c = service.base.conn()
    try:
        # Retire abandoned batches from older worker runs so they cannot interfere
        # with resumable state or the old background scheduler.
        stale = c.execute("select id from batches where status in ('queued','running','paused','direct_running')").fetchall()
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
            (batch_id, 'direct_running', len(vins), body.lookupMode, json.dumps(options), service.base.now()),
        )
        for i, vin in enumerate(vins):
            c.execute(
                'insert into items(id,batch_id,vin,queue_position,status,attempts) values(?,?,?,?,?,0)',
                (str(uuid.uuid4()), batch_id, vin, i, 'queued'),
            )
        c.commit()
    finally:
        c.close()

    # Start BEFORE returning to the browser. The website should see the item
    # transition to running on its very next refresh and OWL should launch now.
    threading.Thread(target=_process_batch_now, args=(batch_id, vins), daemon=True).start()
    print(f'VIN batch {batch_id}: accepted from website; immediate OWL thread started.', flush=True)
    return {'batchId': batch_id, 'total': len(vins), 'fresh': True, 'execution': 'direct'}


if __name__ == '__main__':
    uvicorn.run(service.base.app, host='127.0.0.1', port=service.base.PORT, log_level='warning')
