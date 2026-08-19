from __future__ import annotations

import uvicorn

import service_v5 as service

# v5.14 keeps the corrected OWL flow and prevents worker startup from opening
# another Diehl VIN Platform website tab.
service.base.VERSION = '5.14'


if __name__ == '__main__':
    uvicorn.run(service.base.app, host='127.0.0.1', port=service.base.PORT, log_level='warning')
