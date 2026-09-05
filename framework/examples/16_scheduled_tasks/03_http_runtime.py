"""Run an HTTP runtime replica for AMP scheduled task dispatches.

Set the secrets to the values used by the AMP, register this endpoint as a
privileged runtime replica, then run: ``python 03_http_runtime.py``.
"""

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wolfpack.schedules import HttpRuntimeRunner, RuntimeContext


def execute(context: RuntimeContext) -> dict:
    # Long-running handlers may call runner.renew(context.dispatch) periodically.
    if context.cancelled:
        return {"cancelled": True}
    return {"message": "scheduled task completed", "payload": context.dispatch.payload}


runner = HttpRuntimeRunner(
    instance_id=os.environ.get("WOLFPACK_RUNTIME_INSTANCE", "reporter-1"),
    dispatch_secret=os.environ["WOLFPACK_SCHEDULER_DISPATCH_SECRET"],
    callback_secret=os.environ["WOLFPACK_SCHEDULER_CALLBACK_SECRET"],
    control_plane_url=os.environ.get("WOLFPACK_AMP_URL", "http://localhost:8000"),
    handler=execute,
    max_concurrency=int(os.environ.get("WOLFPACK_RUNTIME_CONCURRENCY", "2")),
)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/scheduled-task":
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            response = runner.handle_dispatch(body, self.headers.get("X-Wolfpack-Schedule-Signature"))
        except (PermissionError, ValueError) as error:
            self.send_error(401, str(error))
            return
        encoded = str(response).encode()
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 9010), Handler).serve_forever()
