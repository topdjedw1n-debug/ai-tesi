============================= test session starts ==============================
platform darwin -- Python 3.11.9, pytest-7.4.3, pluggy-1.6.0 -- /Users/maxmaxvel/AI TESI/qa_venv/bin/python3.11
cachedir: .pytest_cache
rootdir: /Users/maxmaxvel/AI TESI
configfile: pytest.ini
plugins: cov-4.1.0, asyncio-0.21.1, anyio-3.7.1
asyncio: mode=Mode.AUTO
collecting ... collected 69 items

tests/test_ai_service.py::test_get_user_usage_correctness PASSED         [  1%]
tests/test_ai_service.py::test_generate_outline_not_found PASSED         [  2%]
tests/test_ai_service.py::test_build_outline_prompt PASSED               [  4%]
tests/test_ai_service.py::test_build_section_prompt PASSED               [  5%]
tests/test_ai_service.py::test_call_openai_missing_api_key PASSED        [  7%]
tests/test_ai_service.py::test_call_anthropic_missing_api_key PASSED     [  8%]
tests/test_ai_service.py::test_call_ai_provider_unsupported PASSED       [ 10%]
tests/test_ai_service_extended.py::test_get_user_usage_user_not_found PASSED [ 11%]
tests/test_ai_service_extended.py::test_generate_outline_success_mock PASSED [ 13%]
tests/test_ai_service_extended.py::test_generate_section_success_mock FAILED [ 14%]
tests/test_ai_service_extended.py::test_generate_section_document_not_found PASSED [ 15%]
tests/test_ai_service_extended.py::test_generate_section_outline_not_found PASSED [ 17%]
tests/test_ai_service_extended.py::test_call_openai_success_mock FAILED  [ 18%]
tests/test_ai_service_extended.py::test_call_anthropic_success_mock FAILED [ 20%]
tests/test_api_endpoints.py::test_health_endpoint_accessible PASSED      [ 21%]
tests/test_api_endpoints.py::test_auth_me_endpoint_requires_token PASSED [ 23%]
tests/test_api_endpoints.py::test_generate_models_endpoint PASSED        [ 24%]
tests/test_api_endpoints.py::test_documents_list_requires_auth PASSED    [ 26%]
tests/test_api_endpoints.py::test_create_document_requires_auth PASSED   [ 27%]
tests/test_api_endpoints.py::test_export_document_requires_auth PASSED   [ 28%]
tests/test_api_endpoints.py::test_generate_outline_requires_auth PASSED  [ 30%]
tests/test_api_endpoints.py::test_generate_section_requires_auth PASSED  [ 31%]
tests/test_api_endpoints.py::test_full_document_generation_requires_auth PASSED [ 33%]
tests/test_api_endpoints.py::test_usage_stats_requires_auth PASSED       [ 34%]
tests/test_api_integration.py::test_auth_flow FAILED                     [ 36%]
tests/test_api_integration.py::test_create_document_flow FAILED          [ 37%]
tests/test_api_integration.py::test_document_list_flow FAILED            [ 39%]
tests/test_api_integration.py::test_document_update_flow FAILED          [ 40%]
tests/test_api_integration.py::test_document_delete_flow FAILED          [ 42%]
tests/test_api_integration.py::test_usage_stats_flow PASSED              [ 43%]
tests/test_api_integration_simple.py::test_health_endpoint_flow PASSED   [ 44%]
tests/test_api_integration_simple.py::test_models_endpoint_flow PASSED   [ 46%]
tests/test_api_integration_simple.py::test_authenticated_me_endpoint FAILED [ 47%]
tests/test_api_integration_simple.py::test_documents_endpoint_requires_auth PASSED [ 49%]
tests/test_api_integration_simple.py::test_create_document_with_auth FAILED [ 50%]
tests/test_api_integration_simple.py::test_usage_stats_endpoint PASSED   [ 52%]
tests/test_auth_no_token.py::test_auth_no_token PASSED                   [ 53%]
tests/test_auth_service_extended.py::test_send_magic_link_new_user PASSED [ 55%]
tests/test_auth_service_extended.py::test_send_magic_link_existing_user PASSED [ 56%]
tests/test_auth_service_extended.py::test_send_magic_link_invalid_email PASSED [ 57%]
tests/test_auth_service_extended.py::test_verify_magic_link_success FAILED [ 59%]
tests/test_auth_service_extended.py::test_verify_magic_link_invalid_token PASSED [ 60%]
tests/test_auth_service_extended.py::test_verify_magic_link_expired_token PASSED [ 62%]
tests/test_auth_service_extended.py::test_verify_magic_link_already_used PASSED [ 63%]
tests/test_auth_service_extended.py::test_get_current_user_invalid_token PASSED [ 65%]
tests/test_auth_service_extended.py::test_get_current_user_user_not_found PASSED [ 66%]
tests/test_auth_service_extended.py::test_get_current_user_inactive PASSED [ 68%]
tests/test_document_service.py::test_create_document_success PASSED      [ 69%]
tests/test_document_service.py::test_get_document_success PASSED         [ 71%]
tests/test_document_service.py::test_get_document_not_found PASSED       [ 72%]
tests/test_document_service.py::test_get_user_documents_with_pagination PASSED [ 73%]
tests/test_document_service.py::test_update_document_success PASSED      [ 75%]
tests/test_document_service.py::test_delete_document_success PASSED      [ 76%]
tests/test_document_service.py::test_export_document_docx_fails_on_incomplete PASSED [ 78%]
tests/test_document_service.py::test_export_document_pdf_fails_on_incomplete PASSED [ 79%]
tests/test_document_service.py::test_export_document_pdf_unsupported_format PASSED [ 81%]
tests/test_document_service.py::test_update_document_not_found FAILED    [ 82%]
tests/test_document_service.py::test_delete_document_not_found PASSED    [ 84%]
tests/test_document_service.py::test_get_document_sections_not_found PASSED [ 85%]
tests/test_document_service.py::test_get_document_sections_success PASSED [ 86%]
tests/test_document_service_extended.py::test_get_user_documents_empty PASSED [ 88%]
tests/test_document_service_extended.py::test_get_user_documents_pagination PASSED [ 89%]
tests/test_document_service_extended.py::test_update_document_partial_fields PASSED [ 91%]
tests/test_document_service_extended.py::test_get_document_with_sections PASSED [ 92%]
tests/test_document_service_extended.py::test_update_document_invalid_field PASSED [ 94%]
tests/test_document_service_extended.py::test_delete_document_with_sections PASSED [ 95%]
tests/test_health_endpoint.py::test_health_endpoint PASSED               [ 97%]
tests/test_rate_limit_init.py::test_rate_limit_init PASSED               [ 98%]
tests/test_rate_limit_init.py::test_app_starts_without_exceptions PASSED [100%]

=================================== FAILURES ===================================
______________________ test_generate_section_success_mock ______________________
app/services/ai_service.py:142: in generate_section
    section_result = await section_generator.generate_section(
app/services/ai_pipeline/generator.py:103: in generate_section
    section_content = await self._call_ai_provider(
app/services/ai_pipeline/generator.py:167: in _call_ai_provider
    return await self._call_openai(model, prompt)
app/services/ai_pipeline/generator.py:179: in _call_openai
    raise ValueError("OpenAI API key not configured")
E   ValueError: OpenAI API key not configured

The above exception was the direct cause of the following exception:
tests/test_ai_service_extended.py:112: in test_generate_section_success_mock
    result = await service.generate_section(
app/services/ai_service.py:212: in generate_section
    raise AIProviderError(f"Failed to generate section: {str(e)}") from e
E   app.core.exceptions.AIProviderError: Failed to generate section: OpenAI API key not configured
------------------------------ Captured log call -------------------------------
ERROR    app.services.ai_pipeline.generator:generator.py:196 OpenAI API error: OpenAI API key not configured
ERROR    app.services.ai_pipeline.generator:generator.py:161 Error generating section: OpenAI API key not configured
ERROR    app.services.ai_service:ai_service.py:211 Error generating section: OpenAI API key not configured
________________________ test_call_openai_success_mock _________________________
tests/test_ai_service_extended.py:187: in test_call_openai_success_mock
    with patch('app.services.ai_service.openai') as mock_openai:
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:1446: in __enter__
    original, local = self.get_original()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:1419: in get_original
    raise AttributeError(
E   AttributeError: <module 'app.services.ai_service' from '/Users/maxmaxvel/AI TESI/apps/api/app/services/ai_service.py'> does not have the attribute 'openai'
_______________________ test_call_anthropic_success_mock _______________________
tests/test_ai_service_extended.py:217: in test_call_anthropic_success_mock
    with patch('app.services.ai_service.Anthropic') as mock_anthropic:
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:1446: in __enter__
    original, local = self.get_original()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:1419: in get_original
    raise AttributeError(
E   AttributeError: <module 'app.services.ai_service' from '/Users/maxmaxvel/AI TESI/apps/api/app/services/ai_service.py'> does not have the attribute 'Anthropic'
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
E     {'type': 'missing', 'loc': ('response', 'expires_in_minutes'), 'msg': 'Field required', 'input': {'message': 'Magic link sent successfully', 'email': 'test@example.com', 'expires_in': 900, 'magic_link': 'http://localhost:3000/auth/verify?token=WC_GQHg2wjZVgFdiLiYiThbVubKLXopB7i1F5bI8Lxw'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}

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
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:174: in __call__
    response = await self.handler(request, exc)
main.py:107: in unhandled_exception_handler
    logger.exception(
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2065: in exception
    __self._log("ERROR", False, options, __message, args, kwargs)
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2021: in _log
    log_record["message"] = message.format(*args, **kwargs)
E   KeyError: "'type'"
----------------------------- Captured stdout call -----------------------------
2025-11-02 00:53:10.215 | INFO | 0cbee186-ae2a-488f-9658-c894d6ed57bc | HTTP POST /api/v1/auth/magic-link
2025-11-02 00:53:10.221 | INFO | 0cbee186-ae2a-488f-9658-c894d6ed57bc | {"timestamp": "2025-11-01T22:53:10.221438", "event_type": "auth_attempt", "correlation_id": "unknown", "user_id": null, "ip": "127.0.0.1", "endpoint": "/api/v1/auth/magic-link", "resource": "auth", "action": "request_magic_link", "outcome": "success", "details": {"email": "test@example.com"}}
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
E   fastapi.exceptions.ResponseValidationError: 5 validation errors:
E     {'type': 'missing', 'loc': ('response', 'user_id'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Test Thesis', 'topic': 'AI in Education', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'is_archived'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Test Thesis', 'topic': 'AI in Education', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'updated_at'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Test Thesis', 'topic': 'AI in Education', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'word_count'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Test Thesis', 'topic': 'AI in Education', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'estimated_reading_time'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Test Thesis', 'topic': 'AI in Education', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}

During handling of the above exception, another exception occurred:
tests/test_api_integration.py:153: in test_create_document_flow
    create_response = await client.post(
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
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:174: in __call__
    response = await self.handler(request, exc)
main.py:107: in unhandled_exception_handler
    logger.exception(
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2065: in exception
    __self._log("ERROR", False, options, __message, args, kwargs)
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2021: in _log
    log_record["message"] = message.format(*args, **kwargs)
E   KeyError: "'type'"
----------------------------- Captured stdout call -----------------------------
2025-11-02 00:53:10.447 | INFO | 0896f4b6-55f2-4d55-b89f-cc4e9eeb40ee | HTTP POST /api/v1/documents/
___________________________ test_document_list_flow ____________________________
tests/test_api_integration.py:213: in test_document_list_flow
    assert list_response.status_code == 200
E   assert 307 == 200
E    +  where 307 = <Response [307 Temporary Redirect]>.status_code
----------------------------- Captured stdout call -----------------------------
2025-11-02 00:53:10.678 | INFO | 35a8b673-da69-43f0-bae7-bb45ad6f79ee | HTTP POST /api/v1/documents/
2025-11-02 00:53:10.680 | INFO | 35a8b673-da69-43f0-bae7-bb45ad6f79ee | 422 POST /api/v1/documents/
2025-11-02 00:53:10.681 | INFO | 1d6b2c72-b5ab-4da1-bba0-3fe754a3da90 | HTTP POST /api/v1/documents/
2025-11-02 00:53:10.683 | INFO | 1d6b2c72-b5ab-4da1-bba0-3fe754a3da90 | 422 POST /api/v1/documents/
2025-11-02 00:53:10.685 | INFO | 31401b3f-e646-4b60-88f5-4e8ff2895682 | HTTP POST /api/v1/documents/
2025-11-02 00:53:10.687 | INFO | 31401b3f-e646-4b60-88f5-4e8ff2895682 | 422 POST /api/v1/documents/
2025-11-02 00:53:10.688 | INFO | 6be64b8e-013c-4d5e-b9b0-47b587427889 | HTTP GET /api/v1/documents
2025-11-02 00:53:10.688 | INFO | 6be64b8e-013c-4d5e-b9b0-47b587427889 | 307 GET /api/v1/documents
__________________________ test_document_update_flow ___________________________
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
E   fastapi.exceptions.ResponseValidationError: 5 validation errors:
E     {'type': 'missing', 'loc': ('response', 'user_id'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Original Title', 'topic': 'Original Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'is_archived'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Original Title', 'topic': 'Original Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'updated_at'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Original Title', 'topic': 'Original Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'word_count'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Original Title', 'topic': 'Original Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'estimated_reading_time'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Original Title', 'topic': 'Original Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}

During handling of the above exception, another exception occurred:
tests/test_api_integration.py:223: in test_document_update_flow
    doc_response = await client.post(
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
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:174: in __call__
    response = await self.handler(request, exc)
main.py:107: in unhandled_exception_handler
    logger.exception(
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2065: in exception
    __self._log("ERROR", False, options, __message, args, kwargs)
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2021: in _log
    log_record["message"] = message.format(*args, **kwargs)
E   KeyError: "'type'"
----------------------------- Captured stdout call -----------------------------
2025-11-02 00:53:10.718 | INFO | ddcd9ede-07a4-4449-a57d-32c2bb69931e | HTTP POST /api/v1/documents/
__________________________ test_document_delete_flow ___________________________
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
E   fastapi.exceptions.ResponseValidationError: 5 validation errors:
E     {'type': 'missing', 'loc': ('response', 'user_id'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'To Delete', 'topic': 'Test Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'is_archived'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'To Delete', 'topic': 'Test Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'updated_at'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'To Delete', 'topic': 'Test Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'word_count'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'To Delete', 'topic': 'Test Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'estimated_reading_time'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'To Delete', 'topic': 'Test Topic', 'status': 'draft', 'created_at': '2025-11-01T22:53:10'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}

During handling of the above exception, another exception occurred:
tests/test_api_integration.py:253: in test_document_delete_flow
    doc_response = await client.post(
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
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:174: in __call__
    response = await self.handler(request, exc)
main.py:107: in unhandled_exception_handler
    logger.exception(
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2065: in exception
    __self._log("ERROR", False, options, __message, args, kwargs)
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2021: in _log
    log_record["message"] = message.format(*args, **kwargs)
E   KeyError: "'type'"
----------------------------- Captured stdout call -----------------------------
2025-11-02 00:53:10.919 | INFO | 9e8371e0-0df9-41a6-9fcb-d530f504fbc2 | HTTP POST /api/v1/documents/
________________________ test_authenticated_me_endpoint ________________________
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
E   fastapi.exceptions.ResponseValidationError: 3 validation errors:
E     {'type': 'missing', 'loc': ('response', 'is_active'), 'msg': 'Field required', 'input': {'id': 1, 'email': 'integration@test.com', 'full_name': 'Integration Test User', 'is_verified': False, 'is_admin': False, 'preferred_language': 'en', 'timezone': 'UTC', 'total_tokens_used': 0, 'total_documents_created': 0, 'created_at': '2025-11-01T22:53:11', 'last_login': None}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'updated_at'), 'msg': 'Field required', 'input': {'id': 1, 'email': 'integration@test.com', 'full_name': 'Integration Test User', 'is_verified': False, 'is_admin': False, 'preferred_language': 'en', 'timezone': 'UTC', 'total_tokens_used': 0, 'total_documents_created': 0, 'created_at': '2025-11-01T22:53:11', 'last_login': None}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'total_cost'), 'msg': 'Field required', 'input': {'id': 1, 'email': 'integration@test.com', 'full_name': 'Integration Test User', 'is_verified': False, 'is_admin': False, 'preferred_language': 'en', 'timezone': 'UTC', 'total_tokens_used': 0, 'total_documents_created': 0, 'created_at': '2025-11-01T22:53:11', 'last_login': None}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}

During handling of the above exception, another exception occurred:
tests/test_api_integration_simple.py:116: in test_authenticated_me_endpoint
    response = await client.get(
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
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:174: in __call__
    response = await self.handler(request, exc)
main.py:107: in unhandled_exception_handler
    logger.exception(
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2065: in exception
    __self._log("ERROR", False, options, __message, args, kwargs)
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2021: in _log
    log_record["message"] = message.format(*args, **kwargs)
E   KeyError: "'type'"
----------------------------- Captured stdout call -----------------------------
2025-11-02 00:53:11.182 | INFO | aab934fd-1301-4472-805e-28ed90db6551 | HTTP GET /api/v1/auth/me
2025-11-02 00:53:11.183 | INFO | aab934fd-1301-4472-805e-28ed90db6551 | {"timestamp": "2025-11-01T22:53:11.183774", "event_type": "user_lookup", "correlation_id": "unknown", "user_id": 1, "ip": "127.0.0.1", "endpoint": "/api/v1/auth/me", "resource": "user", "action": "read", "outcome": "success", "details": {}}
________________________ test_create_document_with_auth ________________________
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
E   fastapi.exceptions.ResponseValidationError: 5 validation errors:
E     {'type': 'missing', 'loc': ('response', 'user_id'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Integration Test Document', 'topic': 'Testing Integration', 'status': 'draft', 'created_at': '2025-11-01T22:53:11'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'is_archived'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Integration Test Document', 'topic': 'Testing Integration', 'status': 'draft', 'created_at': '2025-11-01T22:53:11'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'updated_at'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Integration Test Document', 'topic': 'Testing Integration', 'status': 'draft', 'created_at': '2025-11-01T22:53:11'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'word_count'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Integration Test Document', 'topic': 'Testing Integration', 'status': 'draft', 'created_at': '2025-11-01T22:53:11'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}
E     {'type': 'missing', 'loc': ('response', 'estimated_reading_time'), 'msg': 'Field required', 'input': {'id': 1, 'title': 'Integration Test Document', 'topic': 'Testing Integration', 'status': 'draft', 'created_at': '2025-11-01T22:53:11'}, 'url': 'https://errors.pydantic.dev/2.12/v/missing'}

During handling of the above exception, another exception occurred:
tests/test_api_integration_simple.py:146: in test_create_document_with_auth
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
../../qa_venv/lib/python3.11/site-packages/starlette/middleware/errors.py:174: in __call__
    response = await self.handler(request, exc)
main.py:107: in unhandled_exception_handler
    logger.exception(
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2065: in exception
    __self._log("ERROR", False, options, __message, args, kwargs)
../../qa_venv/lib/python3.11/site-packages/loguru/_logger.py:2021: in _log
    log_record["message"] = message.format(*args, **kwargs)
E   KeyError: "'type'"
----------------------------- Captured stdout call -----------------------------
2025-11-02 00:53:11.411 | INFO | 0c2236e0-5791-4ec7-9ad3-33efc1d5d6fd | HTTP POST /api/v1/documents/
________________________ test_verify_magic_link_success ________________________
app/services/auth_service.py:102: in verify_magic_link
    raise AuthenticationError("Invalid or expired magic link")
E   app.core.exceptions.AuthenticationError: Invalid or expired magic link

The above exception was the direct cause of the following exception:
tests/test_auth_service_extended.py:80: in test_verify_magic_link_success
    result = await service.verify_magic_link(token)
app/services/auth_service.py:151: in verify_magic_link
    raise AuthenticationError(f"Failed to verify magic link: {str(e)}") from e
E   app.core.exceptions.AuthenticationError: Failed to verify magic link: Invalid or expired magic link
------------------------------ Captured log call -------------------------------
ERROR    app.services.auth_service:auth_service.py:150 Error verifying magic link: Invalid or expired magic link
________________________ test_update_document_not_found ________________________
app/services/document_service.py:196: in update_document
    raise NotFoundError("Document not found")
E   app.core.exceptions.NotFoundError: Document not found

The above exception was the direct cause of the following exception:
tests/test_document_service.py:307: in test_update_document_not_found
    await service.update_document(
app/services/document_service.py:219: in update_document
    raise ValidationError(f"Failed to update document: {str(e)}") from e
E   app.core.exceptions.ValidationError: Failed to update document: Document not found
------------------------------ Captured log call -------------------------------
ERROR    app.services.document_service:document_service.py:218 Error updating document: Document not found
=============================== warnings summary ===============================
../../qa_venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1373
  /Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/_pytest/config/__init__.py:1373: PytestConfigWarning: Unknown config option: asyncio_default_fixture_loop_scope
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

app/core/config.py:14
  /Users/maxmaxvel/AI TESI/apps/api/app/core/config.py:14: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class Settings(BaseSettings):

app/api/v1/endpoints/admin.py:179
  /Users/maxmaxvel/AI TESI/apps/api/app/api/v1/endpoints/admin.py:179: DeprecationWarning: `regex` has been deprecated, please use `pattern` instead
    group_by: str = Query("day", regex="^(day|week|month)$"),

app/schemas/user.py:30
  /Users/maxmaxvel/AI TESI/apps/api/app/schemas/user.py:30: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.12/migration/
    class UserResponse(UserBase):

../../qa_venv/lib/python3.11/site-packages/passlib/utils/__init__.py:854
  /Users/maxmaxvel/AI TESI/qa_venv/lib/python3.11/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

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
app/api/v1/endpoints/auth.py                       125     74    41%   46-56, 80-103, 114-187, 198-271, 281-330, 378-389
app/api/v1/endpoints/documents.py                   94     58    38%   50-56, 72-86, 101-113, 129-141, 156-168, 184-198, 214-228
app/api/v1/endpoints/generate.py                    81     48    41%   40-59, 74-95, 127, 135-138, 168-227
app/core/__init__.py                                 1      0   100%
app/core/config.py                                 185     88    52%   102-108, 112, 118, 134, 141, 145, 151-153, 157-159, 167, 181-193, 198-199, 210-212, 215-216, 222-240, 247-248, 260-304, 323-348
app/core/database.py                               114     50    56%   52-54, 58, 79-89, 111, 127, 164-206, 222-277
app/core/dependencies.py                            59     22    63%   83, 85, 92, 97, 102-103, 112, 116, 120-136, 159-172
app/core/exceptions.py                              26      2    92%   45, 59
app/core/logging.py                                 27      0   100%
app/core/monitoring.py                              13      1    92%   23
app/middleware/csrf.py                              10      0   100%
app/middleware/rate_limit.py                       164    114    30%   37-66, 72-75, 86, 101-145, 150-166, 175-182, 188, 204-246, 264-287, 309, 321-338
app/models/__init__.py                               4      0   100%
app/models/auth.py                                  47      3    94%   39, 65, 92
app/models/document.py                              79      4    95%   71, 108, 133, 165
app/models/user.py                                   2      0   100%
app/schemas/__init__.py                              0      0   100%
app/schemas/auth.py                                 31      0   100%
app/schemas/document.py                            188     57    70%   75-82, 88-110, 115-121, 166-172, 192-194, 199-205, 253-259
app/schemas/user.py                                 26      0   100%
app/services/__init__.py                             0      0   100%
app/services/admin_service.py                      111     95    14%   24, 28-94, 103-149, 160-223, 232-278, 282-322
app/services/ai_pipeline/__init__.py                 6      0   100%
app/services/ai_pipeline/citation_formatter.py     166    126    24%   37-40, 65-72, 89-96, 101-111, 116-126, 131-143, 149-181, 187-215, 221-251, 263-289
app/services/ai_pipeline/generator.py               80     36    55%   86, 110-150, 168-171, 181-193, 201-223
app/services/ai_pipeline/humanizer.py               56     45    20%   45-84, 94-99, 103-125, 129-151
app/services/ai_pipeline/prompt_builder.py          27      8    70%   31-55, 82-84, 130-153
app/services/ai_pipeline/rag_retriever.py          103     51    50%   38, 102-183, 187-216, 225, 230, 253-255
app/services/ai_service.py                         112     30    73%   154-197, 233-235, 245, 247, 259-274, 291-306
app/services/auth_service.py                       129     59    54%   105-135, 155-201, 205-238, 253, 256, 268, 290-298, 302-310
app/services/background_jobs.py                    170    136    20%   46-64, 94-316, 338-378, 383-399, 404-417
app/services/document_service.py                   235    135    43%   73-76, 174-176, 303-330, 344-429, 463, 471, 476-506, 510-590, 596-648, 656, 659-662
------------------------------------------------------------------------------
TOTAL                                             2590   1331    49%
Coverage HTML written to dir htmlcov
Coverage XML written to file coverage.xml

=========================== short test summary info ============================
FAILED tests/test_ai_service_extended.py::test_generate_section_success_mock
FAILED tests/test_ai_service_extended.py::test_call_openai_success_mock - Att...
FAILED tests/test_ai_service_extended.py::test_call_anthropic_success_mock - ...
FAILED tests/test_api_integration.py::test_auth_flow - KeyError: "'type'"
FAILED tests/test_api_integration.py::test_create_document_flow - KeyError: "...
FAILED tests/test_api_integration.py::test_document_list_flow - assert 307 ==...
FAILED tests/test_api_integration.py::test_document_update_flow - KeyError: "...
FAILED tests/test_api_integration.py::test_document_delete_flow - KeyError: "...
FAILED tests/test_api_integration_simple.py::test_authenticated_me_endpoint
FAILED tests/test_api_integration_simple.py::test_create_document_with_auth
FAILED tests/test_auth_service_extended.py::test_verify_magic_link_success - ...
FAILED tests/test_document_service.py::test_update_document_not_found - app.c...
================== 12 failed, 57 passed, 7 warnings in 3.85s ===================
