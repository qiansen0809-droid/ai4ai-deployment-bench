import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from starter.adapters.llm.vllm_http import VLLMAdapter


@contextlib.contextmanager
def server(chunks):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert payload["return_token_ids"] and payload["temperature"] == 0
            self.send_response(200); self.send_header("Content-Type","text/event-stream"); self.end_headers()
            for chunk in chunks:
                self.wfile.write(("data: " + (chunk if isinstance(chunk,str) else json.dumps(chunk)) + "\n\n").encode())
            self.wfile.flush()
        def log_message(self, *args): pass
    srv = ThreadingHTTPServer(("127.0.0.1",0),Handler)
    t = threading.Thread(target=srv.serve_forever,daemon=True); t.start()
    try: yield "http://127.0.0.1:" + str(srv.server_port)
    finally: srv.shutdown(); srv.server_close(); t.join()


def request():
    return {"modality":"llm","request_id":"test","input":{"text":"hi"},"generation":{"max_tokens":2}}


def test_sse_stream_with_chunked_tokens():
    with server([{"choices":[{"text":"ab","token_ids":[10,11]}]},"[DONE]"]) as url:
        events=[]
        out=VLLMAdapter(url,"test").run(request(),lambda kind,**data: events.append(data))
        assert out.token_ids == [10,11] and out.text == "ab" and len(events)==1


@pytest.mark.parametrize("chunks", [
    [{"choices":[{"text":"a","token_ids":[1]}]}],
    [{"choices":[{"text":"a"}]},"[DONE]"],
    [{"error":"out of memory"}],
])
def test_sse_faults(chunks):
    with server(chunks) as url:
        with pytest.raises((RuntimeError, ValueError)):
            VLLMAdapter(url,"test").run(request(),lambda *a,**kw:None)
