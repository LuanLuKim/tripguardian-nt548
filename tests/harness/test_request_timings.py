import http.client
import json
import threading
import re
from http.server import ThreadingHTTPServer

from harness.server import handler
from test_dispatch import make
from test_harness_server import FakeAccounts, headers


def test_json_response_reports_processing_and_serialization_timing():
    h, _ = make()
    view = h.create(owner='a' * 32)
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(h, FakeAccounts(), 'http://app.test'))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        conn = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=5)
        conn.request('GET', '/api/harness/sessions/'+view['id'], headers=headers())
        response = conn.getresponse()
        assert response.status == 200
        assert json.loads(response.read())['revision'] == view['revision']
        timing = response.getheader('Server-Timing')
        assert timing and 'app;dur=' in timing and 'serialize;dur=' in timing
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_trace_correlates_module_spans_and_response_without_leaking_between_requests(caplog):
    h, _ = make()
    view = h.create(owner='a' * 32)
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(h, FakeAccounts(), 'http://app.test'))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    ids = []
    try:
        with caplog.at_level('INFO'):
            for suffix in ['', '?view=0']:
                conn = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=5)
                conn.request('GET', '/api/harness/sessions/'+view['id']+suffix, headers=headers())
                response = conn.getresponse()
                assert response.status == 200
                response.read()
                trace = response.getheader('X-Request-ID')
                assert trace and re.fullmatch('[0-9a-f]{32}', trace)
                ids.append(trace)
                timing = response.getheader('Server-Timing')
                assert 'db_state;dur=' in timing
                assert ('view;dur=' in timing) == (not suffix)
                conn.close()
        assert ids[0] != ids[1]
        for trace in ids:
            assert any(trace in record.message and 'spans=' in record.message for record in caplog.records)
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
