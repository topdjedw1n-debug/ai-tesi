============================= test session starts ==============================
platform darwin -- Python 3.11.9, pytest-7.4.3, pluggy-1.6.0 -- /Users/maxmaxvel/AI TESI/qa_venv/bin/python3.11
cachedir: .pytest_cache
rootdir: /Users/maxmaxvel/AI TESI
configfile: pytest.ini
plugins: cov-4.1.0, asyncio-0.21.1, anyio-3.7.1
asyncio: mode=Mode.AUTO
collecting ... collected 12 items

tests/test_api_integration.py::test_auth_flow FAILED                     [  8%]
tests/test_api_integration.py::test_create_document_flow FAILED          [ 16%]
tests/test_api_integration.py::test_document_list_flow FAILED            [ 25%]
tests/test_api_integration.py::test_document_update_flow FAILED          [ 33%]
tests/test_api_integration.py::test_document_delete_flow PASSED          [ 41%]
tests/test_api_integration.py::test_usage_stats_flow PASSED              [ 50%]
tests/test_api_integration_simple.py::test_health_endpoint_flow PASSED   [ 58%]
tests/test_api_integration_simple.py::test_models_endpoint_flow PASSED   [ 66%]
tests/test_api_integration_simple.py::test_authenticated_me_endpoint PASSED [ 75%]
tests/test_api_integration_simple.py::test_documents_endpoint_requires_auth PASSED [ 83%]
tests/test_api_integration_simple.py::test_create_document_with_auth PASSED [ 91%]
tests/test_api_integration_simple.py::test_usage_stats_endpoint PASSED   [100%]

=================================== FAILURES ===================================
________________________________ test_auth_flow ________________________________
../../qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py:98: in receive
    return self.receive_nowait()
../../qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py:93: in receive_nowait
    raise WouldBlock
E   anyio.WouldBlock

During handling of the above exception, another exception occurred:
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:78: in call_next
    message = await recv_stream.receive()
../../qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py:118: in receive
    raise EndOfStream
E   anyio.EndOfStream

During handling of the above exception, another exception occurred:
tests/test_api_integration.py:102: in test_auth_flow
    response = await client.post(
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1848: in post
    return await self.request(
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1530: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1617: in send
    response = await self._send_handling_auth(
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1645: in _send_handling_auth
    response = await self._send_handling_redirects(
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1682: in _send_handling_redirects
    response = await self._send_single_request(request)
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1719: in _send_single_request
    response = await transport.handle_async_request(request)
../../qa_venv/lib/python3.11/site-packages/httpx/_transports/asgi.py:162: in handle_async_request
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/fastapi/applications.py:1106: in __call__
    await super().__call__(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/applications.py:122: in __call__
    await self.middleware_stack(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:184: in __call__
    raise exc
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:162: in __call__
    await self.app(scope, receive, _send)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:108: in __call__
    response = await self.dispatch_func(request, call_next)
app/middleware/csrf.py:27: in dispatch
    return await call_next(request)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:84: in call_next
    raise app_exc
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:70: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/trustedhost.py:51: in __call__
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/cors.py:83: in __call__
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:108: in __call__
    response = await self.dispatch_func(request, call_next)
app/core/logging.py:98: in dispatch
    response = await call_next(request)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:84: in call_next
    raise app_exc
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:70: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py:79: in __call__
    raise exc
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py:68: in __call__
    await self.app(scope, receive, sender)
../../qa_venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:20: in __call__
    raise e
../../qa_venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:17: in __call__
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/routing.py:718: in __call__
    await route.handle(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/routing.py:276: in handle
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/routing.py:66: in app
    response = await func(request)
../../qa_venv/lib/python3.11/site-packages/fastapi/routing.py:292: in app
    content = await serialize_response(
../../qa_venv/lib/python3.11/site-packages/fastapi/routing.py:155: in serialize_response
    raise ResponseValidationError(
E   fastapi.exceptions.ResponseValidationError: 1 validation errors:
E     {'type': 'missing', 'loc': ('response', 'expires_in_minutes'), 'msg': 'Field required', 'input': {'message': 'Magic link sent successfully', 'email': 'test@example.com', 'expires_in': 900, 'magic_link': 'http://localhost:3000/auth/verify?token=if9T9PhHQamT9W14SeGWEkVP1pleSuYAQtl7H5IAn84'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
----------------------------- Captured stdout call -----------------------------
2025-11-02 01:15:20.366 | INFO | 7de6878f-e3a1-4a09-97c6-e59f52eb096a | HTTP POST /api/v1/auth/magic-link
2025-11-02 01:15:20.375 | INFO | 7de6878f-e3a1-4a09-97c6-e59f52eb096a | {"timestamp": "2025-11-01T23:15:20.375090", "event_type": "auth_attempt", "correlation_id": "unknown", "user_id": null, "ip": "127.0.0.1", "endpoint": "/api/v1/auth/magic-link", "resource": "auth", "action": "request_magic_link", "outcome": "success", "details": {"email": "test@example.com"}}
2025-11-02 01:15:20.376 | ERROR | unknown | Unhandled exception: ResponseValidationError - 1 validation errors:
  {'type': 'missing', 'loc': ('response', 'expires_in_minutes'), 'msg': 'Field required', 'input': {'message': 'Magic link sent successfully', 'email': 'test@example.com', 'expires_in': 900, 'magic_link': 'http://localhost:3000/auth/verify?token=if9T9PhHQamT9W14SeGWEkVP1pleSuYAQtl7H5IAn84'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}

Traceback (most recent call last):
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py", line 98, in receive
    return self.receive_nowait()
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py", line 93, in receive_nowait
    raise WouldBlock
anyio.WouldBlock

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 78, in call_next
    message = await recv_stream.receive()
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py", line 118, in receive
    raise EndOfStream
anyio.EndOfStream

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py", line 162, in __call__
    await self.app(scope, receive, _send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 108, in __call__
    response = await self.dispatch_func(request, call_next)
  File "/Users/maxmaxvel/AI TESI/apps/api/app/middleware/csrf.py", line 27, in dispatch
    return await call_next(request)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 84, in call_next
    raise app_exc
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 70, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/trustedhost.py", line 51, in __call__
    await self.app(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/cors.py", line 83, in __call__
    await self.app(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 108, in __call__
    response = await self.dispatch_func(request, call_next)
  File "/Users/maxmaxvel/AI TESI/apps/api/app/core/logging.py", line 98, in dispatch
    response = await call_next(request)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 84, in call_next
    raise app_exc
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 70, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py", line 79, in __call__
    raise exc
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py", line 68, in __call__
    await self.app(scope, receive, sender)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py", line 20, in __call__
    raise e
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py", line 17, in __call__
    await self.app(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/routing.py", line 718, in __call__
    await route.handle(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/routing.py", line 276, in handle
    await self.app(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/routing.py", line 66, in app
    response = await func(request)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/fastapi/routing.py", line 292, in app
    content = await serialize_response(
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/fastapi/routing.py", line 155, in serialize_response
    raise ResponseValidationError(
fastapi.exceptions.ResponseValidationError: 1 validation errors:
  {'type': 'missing', 'loc': ('response', 'expires_in_minutes'), 'msg': 'Field required', 'input': {'message': 'Magic link sent successfully', 'email': 'test@example.com', 'expires_in': 900, 'magic_link': 'http://localhost:3000/auth/verify?token=if9T9PhHQamT9W14SeGWEkVP1pleSuYAQtl7H5IAn84'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}

__________________________ test_create_document_flow ___________________________
../../qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py:98: in receive
    return self.receive_nowait()
../../qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py:93: in receive_nowait
    raise WouldBlock
E   anyio.WouldBlock

During handling of the above exception, another exception occurred:
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:78: in call_next
    message = await recv_stream.receive()
../../qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py:118: in receive
    raise EndOfStream
E   anyio.EndOfStream

During handling of the above exception, another exception occurred:
tests/test_api_integration.py:178: in test_create_document_flow
    get_response = await client.get(
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1757: in get
    return await self.request(
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1530: in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1617: in send
    response = await self._send_handling_auth(
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1645: in _send_handling_auth
    response = await self._send_handling_redirects(
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1682: in _send_handling_redirects
    response = await self._send_single_request(request)
../../qa_venv/lib/python3.11/site-packages/httpx/_client.py:1719: in _send_single_request
    response = await transport.handle_async_request(request)
../../qa_venv/lib/python3.11/site-packages/httpx/_transports/asgi.py:162: in handle_async_request
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/fastapi/applications.py:1106: in __call__
    await super().__call__(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/applications.py:122: in __call__
    await self.middleware_stack(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:184: in __call__
    raise exc
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:162: in __call__
    await self.app(scope, receive, _send)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:108: in __call__
    response = await self.dispatch_func(request, call_next)
app/middleware/csrf.py:27: in dispatch
    return await call_next(request)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:84: in call_next
    raise app_exc
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:70: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/trustedhost.py:51: in __call__
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/cors.py:83: in __call__
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:108: in __call__
    response = await self.dispatch_func(request, call_next)
app/core/logging.py:98: in dispatch
    response = await call_next(request)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:84: in call_next
    raise app_exc
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py:70: in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py:79: in __call__
    raise exc
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py:68: in __call__
    await self.app(scope, receive, sender)
../../qa_venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:20: in __call__
    raise e
../../qa_venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:17: in __call__
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/routing.py:718: in __call__
    await route.handle(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/routing.py:276: in handle
    await self.app(scope, receive, send)
../../qa_venv/lib/python3.11/site-packages/starlette/routing.py:66: in app
    response = await func(request)
../../qa_venv/lib/python3.11/site-packages/fastapi/routing.py:292: in app
    content = await serialize_response(
../../qa_venv/lib/python3.11/site-packages/fastapi/routing.py:155: in serialize_response
    raise ResponseValidationError(
E   fastapi.exceptions.ResponseValidationError: 1 validation errors:
E     {'type': 'dict_type', 'loc': ('response', 'sections'), 'msg': 'Input should be a valid dictionary', 'input': [], 'url': 'https://errors.pydantic.dev/2.12/v/dict_type'}
----------------------------- Captured stdout call -----------------------------
2025-11-02 01:15:20.626 | INFO | 63760c8d-cc99-4f7f-86e5-f19d6804584b | HTTP POST /api/v1/documents/
2025-11-02 01:15:20.632 | INFO | 63760c8d-cc99-4f7f-86e5-f19d6804584b | 200 POST /api/v1/documents/
2025-11-02 01:15:20.634 | INFO | 43cc3811-d44b-43f2-9614-ffe21c4f2a5f | HTTP GET /api/v1/documents/1
2025-11-02 01:15:20.639 | ERROR | unknown | Unhandled exception: ResponseValidationError - 1 validation errors:
  {'type': 'dict_type', 'loc': ('response', 'sections'), 'msg': 'Input should be a valid dictionary', 'input': [], 'url': 'https://errors.pydantic.dev/2.12/v/dict_type'}

Traceback (most recent call last):
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py", line 98, in receive
    return self.receive_nowait()
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py", line 93, in receive_nowait
    raise WouldBlock
anyio.WouldBlock

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 78, in call_next
    message = await recv_stream.receive()
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/anyio/streams/memory.py", line 118, in receive
    raise EndOfStream
anyio.EndOfStream

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py", line 162, in __call__
    await self.app(scope, receive, _send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 108, in __call__
    response = await self.dispatch_func(request, call_next)
  File "/Users/maxmaxvel/AI TESI/apps/api/app/middleware/csrf.py", line 27, in dispatch
    return await call_next(request)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 84, in call_next
    raise app_exc
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 70, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/trustedhost.py", line 51, in __call__
    await self.app(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/cors.py", line 83, in __call__
    await self.app(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 108, in __call__
    response = await self.dispatch_func(request, call_next)
  File "/Users/maxmaxvel/AI TESI/apps/api/app/core/logging.py", line 98, in dispatch
    response = await call_next(request)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 84, in call_next
    raise app_exc
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/base.py", line 70, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py", line 79, in __call__
    raise exc
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py", line 68, in __call__
    await self.app(scope, receive, sender)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py", line 20, in __call__
    raise e
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py", line 17, in __call__
    await self.app(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/routing.py", line 718, in __call__
    await route.handle(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/routing.py", line 276, in handle
    await self.app(scope, receive, send)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/starlette/routing.py", line 66, in app
    response = await func(request)
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/fastapi/routing.py", line 292, in app
    content = await serialize_response(
  File "/Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/fastapi/routing.py", line 155, in serialize_response
    raise ResponseValidationError(
fastapi.exceptions.ResponseValidationError: 1 validation errors:
  {'type': 'dict_type', 'loc': ('response', 'sections'), 'msg': 'Input should be a valid dictionary', 'input': [], 'url': 'https://errors.pydantic.dev/2.12/v/dict_type'}

___________________________ test_document_list_flow ____________________________
tests/test_api_integration.py:213: in test_document_list_flow
    assert list_response.status_code == 200
E   assert 307 == 200
E    +  where 307 = <Response [307 Temporary Redirect]>.status_code
----------------------------- Captured stdout call -----------------------------
2025-11-02 01:15:20.827 | INFO | 0cad6912-9633-4eb3-9f7a-a8c1e44227ac | HTTP POST /api/v1/documents/
2025-11-02 01:15:20.830 | INFO | 0cad6912-9633-4eb3-9f7a-a8c1e44227ac | 422 POST /api/v1/documents/
2025-11-02 01:15:20.831 | INFO | e844018a-d42e-44e6-96bb-2564e3377591 | HTTP POST /api/v1/documents/
2025-11-02 01:15:20.834 | INFO | e844018a-d42e-44e6-96bb-2564e3377591 | 422 POST /api/v1/documents/
2025-11-02 01:15:20.835 | INFO | e59e80b0-ad92-4798-9344-b87ddb187be9 | HTTP POST /api/v1/documents/
2025-11-02 01:15:20.837 | INFO | e59e80b0-ad92-4798-9344-b87ddb187be9 | 422 POST /api/v1/documents/
2025-11-02 01:15:20.838 | INFO | 29014c5b-272e-4d22-b1b3-81a291df43e9 | HTTP GET /api/v1/documents
2025-11-02 01:15:20.839 | INFO | 29014c5b-272e-4d22-b1b3-81a291df43e9 | 307 GET /api/v1/documents
__________________________ test_document_update_flow ___________________________
tests/test_api_integration.py:244: in test_document_update_flow
    assert update_response.status_code == 200
E   assert 500 == 200
E    +  where 500 = <Response [500 Internal Server Error]>.status_code
----------------------------- Captured stdout call -----------------------------
2025-11-02 01:15:20.893 | INFO | aa23b9d3-9cd3-4e34-9c2b-211c63d2e26f | HTTP POST /api/v1/documents/
2025-11-02 01:15:20.897 | INFO | aa23b9d3-9cd3-4e34-9c2b-211c63d2e26f | 200 POST /api/v1/documents/
2025-11-02 01:15:20.899 | INFO | c0586807-e3fa-4144-ac8c-a93bb046eda1 | HTTP PUT /api/v1/documents/1
2025-11-02 01:15:20.901 | INFO | c0586807-e3fa-4144-ac8c-a93bb046eda1 | 500 PUT /api/v1/documents/1
=============================== warnings summary ===============================
../../qa_venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1373
  /Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1373: PytestConfigWarning: Unknown config option: asyncio_default_fixture_loop_scope
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

../../qa_venv/lib/python3.11/site-packages/passlib/utils/__init__.py:854
  /Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

app/core/config.py:14
  /Users/maxmaxvel/AI TESI/apps/api/app/core/config.py:14: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class Settings(BaseSettings):

app/api/v1/endpoints/admin.py:179
  /Users/maxmaxvel/AI TESI/apps/api/app/api/v1/endpoints/admin.py:179: DeprecationWarning: `regex` has been deprecated, please use `pattern` instead
    group_by: str = Query("day", regex="^(day|week|month)$"),

app/schemas/user.py:30
  /Users/maxmaxvel/AI TESI/apps/api/app/schemas/user.py:30: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class UserResponse(UserBase):

app/schemas/document.py:132
  /Users/maxmaxvel/AI TESI/apps/api/app/schemas/document.py:132: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class DocumentResponse(DocumentBase):

app/schemas/document.py:216
  /Users/maxmaxvel/AI TESI/apps/api/app/schemas/document.py:216: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class DocumentVersionResponse(BaseModel):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html

---------- coverage: platform darwin, python 3.11.9-final-0 ----------
Name                                             Stmts   Miss  Cover   Missing
------------------------------------------------------------------------------
app/__init__.py                                      0      0   100%
app/api/v1/endpoints/admin.py                      119     89    25%   32-63, 80-113, 132-167, 184-217, 231-263, 277-315, 329-362, 376-416
app/api/v1/endpoints/auth.py                       125     78    38%   46-56, 80-103, 114-187, 198-271, 281-330, 346-356, 376-389
app/api/v1/endpoints/documents.py                   94     40    57%   50-56, 72-86, 105, 112-113, 132-134, 136, 160, 162-168, 184-198, 214-228
app/api/v1/endpoints/generate.py                    81     48    41%   40-59, 74-95, 127, 135-138, 168-227
app/core/__init__.py                                 1      0   100%
app/core/config.py                                 185     88    52%   102-108, 112, 118, 134, 141, 145, 151-153, 157-159, 167, 181-193, 198-199, 210-212, 215-216, 222-240, 247-248, 260-304, 323-348
app/core/database.py                               114     50    56%   52-54, 58, 79-89, 111, 127, 164-206, 222-277
app/core/dependencies.py                            59     23    61%   46, 83, 85, 92, 97, 102-103, 112, 116, 120-136, 159-172
app/core/exceptions.py                              26      5    81%   31, 38, 45, 52, 59
app/core/logging.py                                 27      0   100%
app/core/monitoring.py                              13      1    92%   23
app/middleware/csrf.py                              10      1    90%   22
app/middleware/rate_limit.py                       164    114    30%   37-66, 72-75, 86, 101-145, 150-166, 175-182, 188, 204-246, 264-287, 309, 321-338
app/models/__init__.py                               4      0   100%
app/models/auth.py                                  48      3    94%   40, 66, 93
app/models/document.py                              80      4    95%   72, 109, 134, 166
app/models/user.py                                   2      0   100%
app/schemas/__init__.py                              0      0   100%
app/schemas/auth.py                                 31      0   100%
app/schemas/document.py                            188     57    70%   75-82, 88-110, 115-121, 166-172, 192-194, 199-205, 253-259
app/schemas/user.py                                 26      0   100%
app/services/__init__.py                             0      0   100%
app/services/admin_service.py                      114     98    14%   24, 28-94, 103-149, 160-226, 235-281, 285-325
app/services/ai_pipeline/__init__.py                 6      0   100%
app/services/ai_pipeline/citation_formatter.py     166    126    24%   37-40, 65-72, 89-96, 101-111, 116-126, 131-143, 149-181, 187-215, 221-251, 263-289
app/services/ai_pipeline/generator.py               80     64    20%   38-41, 72-162, 166-171, 175-197, 201-223
app/services/ai_pipeline/humanizer.py               56     46    18%   24, 45-84, 94-99, 103-125, 129-151
app/services/ai_pipeline/prompt_builder.py          27     17    37%   31-55, 80-113, 130-153
app/services/ai_pipeline/rag_retriever.py          103     73    29%   38, 65-69, 94-183, 187-216, 220-255, 260-261
app/services/ai_service.py                         112     86    23%   37-98, 109-212, 224-235, 244-249, 253-281, 285-313, 321-347, 357-378
app/services/auth_service.py                       129     92    29%   38, 48-85, 89-151, 155-201, 205-238, 253, 256, 263-289, 293-301, 305-313
app/services/background_jobs.py                    170    136    20%   46-64, 94-316, 338-378, 383-399, 404-417
app/services/document_service.py                   243    207    15%   67-86, 99-111, 151-153, 162-203, 212-246, 258-275, 283-321, 330-357, 371-456, 471-689
------------------------------------------------------------------------------
TOTAL                                             2603   1546    41%
Coverage HTML written to dir htmlcov
Coverage XML written to file coverage.xml

=========================== short test summary info ============================
FAILED tests/test_api_integration.py::test_auth_flow - fastapi.exceptions.Res...
FAILED tests/test_api_integration.py::test_create_document_flow - fastapi.exc...
FAILED tests/test_api_integration.py::test_document_list_flow - assert 307 ==...
FAILED tests/test_api_integration.py::test_document_update_flow - assert 500 ...
=================== 4 failed, 8 passed, 7 warnings in 1.84s ====================
