from __future__ import annotations

import uvicorn

import service_v5 as service

# v5.13 packages the corrected OWL v5 flow while preserving the verified
# Excel/database service layer from service_v5.
service.base.VERSION = '5.13'


if __name__ == '__main__':
    uvicorn.run(service.base.app, host='127.0.0.1', port=service.base.PORT, log_level='warning')
