import unittest
import json
import tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import ANY, Mock, patch
try:
    import httpx2 as httpx
except ImportError:
    import httpx
from openai import OpenAI

import rsh_ai


class FakeSerial:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    @property
    def output(self):
        return b"".join(self.writes).decode("ascii")


class AiAssistantTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config = Path(directory.name) / "ai_config.json"
        self.addCleanup(patch.stopall)
        patch.object(rsh_ai, "CONFIG_FILE", self.config).start()
        patch.dict(rsh_ai.os.environ, {name: "" for name in ("AI_PROVIDER", "AI_MODEL", "OPENAI_API_KEY", "GEMINI_API_KEY", "OPENAI_MODEL", "GEMINI_MODEL", "OLLAMA_MODEL", "OLLAMA_BASE_URL", "OPENAI_REASONING_EFFORT")}).start()

    def test_chat_uses_modern_openai_client_and_stores_assistant_reply(self):
        serial = FakeSerial()
        session = {"messages": [{"role": "system", "content": "system"}]}
        openai_client = Mock()
        request_messages = []

        def create_completion(**kwargs):
            request_messages.append(deepcopy(kwargs["messages"]))
            return Mock(
                choices=[Mock(message=Mock(content="Hello from the assistant."))]
            )

        openai_client.chat.completions.create.side_effect = create_completion

        session.update(client=openai_client, provider="openai", request_options=rsh_ai._load_chat_options())
        with patch.object(rsh_ai, "_create_client", return_value=openai_client):
            consumed, action = rsh_ai.handle_input(
                session, "Hello", serial, use_ansi=False
            )

        self.assertTrue(consumed)
        self.assertIsNone(action)
        openai_client.chat.completions.create.assert_called_once_with(
            model=rsh_ai.DEFAULT_MODEL,
            messages=ANY,
            max_completion_tokens=500,
            reasoning_effort="none",
        )
        self.assertEqual(
            request_messages,
            [[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "Hello"},
            ]],
        )
        self.assertEqual(
            session["messages"][-1],
            {"role": "assistant", "content": "Hello from the assistant."},
        )
        self.assertIn("Hello from the assistant.", serial.output)

    def test_api_error_removes_unsuccessful_user_message(self):
        serial = FakeSerial()
        session = {"messages": [{"role": "system", "content": "system"}]}
        openai_client = Mock()
        openai_client.chat.completions.create.side_effect = RuntimeError(
            "request failed"
        )

        session.update(client=openai_client, provider="openai", request_options=rsh_ai._load_chat_options())
        with patch.object(rsh_ai, "_create_client", return_value=openai_client):
            rsh_ai.handle_input(session, "Hello", serial, use_ansi=False)

        self.assertEqual(
            session["messages"], [{"role": "system", "content": "system"}]
        )
        self.assertIn("*** API Error: request failed ***", serial.output)

    def test_config_and_environment_select_model_without_unsupported_sampling_fields(self):
        self.config.write_text(json.dumps({"model": "custom-chat-model"}), encoding="utf-8")
        self.assertEqual(rsh_ai._load_chat_options(), {"model": "custom-chat-model", "max_completion_tokens": 500})
        with patch.dict(rsh_ai.os.environ, {"OPENAI_MODEL": "environment-model", "OPENAI_REASONING_EFFORT": "low"}):
            self.assertEqual(rsh_ai._load_chat_options(), {"model": "environment-model", "max_completion_tokens": 500, "reasoning_effort": "low"})

    def test_new_conversations_reload_model_but_existing_conversation_keeps_its_settings(self):
        serial = FakeSerial()
        client = Mock()
        client.chat.completions.create.return_value = Mock(choices=[Mock(message=Mock(content="Hello"))])
        self.config.write_text(json.dumps({"api_key": "test-placeholder", "model": "first-model"}), encoding="utf-8")
        with patch.object(rsh_ai, "_create_client", return_value=client):
            session = rsh_ai.create_session(serial, use_ansi=False)
            self.config.write_text(json.dumps({"api_key": "test-placeholder", "model": "second-model"}), encoding="utf-8")
            before = self.config.read_bytes()
            rsh_ai.handle_input(session, "Hello", serial, use_ansi=False)
            client.chat.completions.create.assert_called_once_with(model="first-model", max_completion_tokens=500, messages=ANY)
            second = rsh_ai.create_session(serial, use_ansi=False)
            self.assertEqual(second["request_options"]["model"], "second-model")
            self.assertEqual(self.config.read_bytes(), before)
        self.assertIn("Model: first-model", serial.output)

    def test_invalid_model_config_is_reported_before_any_request(self):
        self.config.write_text('{"model": ["not a string"]}', encoding="utf-8")
        serial, client = FakeSerial(), Mock()
        with patch.object(rsh_ai, "_create_client", return_value=client):
            self.assertIsNone(rsh_ai.create_session(serial, use_ansi=False))
        client.chat.completions.create.assert_not_called()
        self.assertIn("AI configuration error", serial.output)

    def test_model_not_found_explains_how_to_change_model_and_keeps_history_clean(self):
        class MissingModelError(Exception):
            code = "model_not_found"
        serial, client = FakeSerial(), Mock()
        client.chat.completions.create.side_effect = MissingModelError("Model is unavailable")
        session = {"messages": [{"role": "system", "content": "system"}], "client": client, "provider": "openai", "request_options": rsh_ai._load_chat_options()}
        with patch.object(rsh_ai, "_create_client", return_value=client):
            rsh_ai.handle_input(session, "Hello", serial, use_ansi=False)
        self.assertEqual(len(session["messages"]), 1)
        self.assertIn("OPENAI_MODEL", serial.output)

    def test_reasoning_default_can_be_explicitly_omitted(self):
        self.config.write_text(json.dumps({"model": rsh_ai.DEFAULT_MODEL, "reasoning_effort": "default"}), encoding="utf-8")
        self.assertNotIn("reasoning_effort", rsh_ai._load_chat_options())

    def test_provider_requests_use_real_sdk_with_isolated_credentials_and_options(self):
        for provider in ('openai', 'gemini', 'ollama'):
            with self.subTest(provider=provider):
                self.config.write_text(json.dumps({'provider': provider}), encoding='utf-8')
                requests = []

                def respond(request):
                    requests.append(request)
                    if provider == 'gemini' and 'reasoning_effort' in json.loads(request.content):
                        return httpx.Response(400, json={'error': {
                            'code': 400, 'status': 'INVALID_ARGUMENT',
                            'message': 'Thinking level MINIMAL is not supported for this model.'}})
                    return httpx.Response(200, json={
                        'id': 'test', 'object': 'chat.completion', 'created': 0,
                        'model': rsh_ai.PROVIDERS[provider][1],
                        'choices': [{'index': 0, 'finish_reason': 'stop',
                                     'message': {'role': 'assistant', 'content': 'Reply'}}]})

                def make_client(**kwargs):
                    result = OpenAI(http_client=httpx.Client(transport=httpx.MockTransport(respond)), **kwargs)
                    self.addCleanup(result.close)
                    return result

                with patch.dict(rsh_ai.os.environ, {'OPENAI_API_KEY': 'openai-test', 'GEMINI_API_KEY': 'gemini-test'}), patch.object(rsh_ai, 'OpenAI', side_effect=make_client):
                    serial = FakeSerial()
                    session = rsh_ai.create_session(serial, False)
                    self.assertIsNotNone(session)
                    rsh_ai.handle_input(session, 'Question', serial, False)
                    self.assertEqual(len(requests), 1)
                    request = requests[0]
                    self.assertEqual(str(request.url), rsh_ai.PROVIDERS[provider][2].rstrip('/')+'/chat/completions')
                    expected_key = {'openai': 'openai-test', 'gemini': 'gemini-test', 'ollama': 'ollama'}[provider]
                    self.assertEqual(request.headers['Authorization'], 'Bearer '+expected_key)
                    body = json.loads(request.content)
                    self.assertEqual(body['model'], rsh_ai.PROVIDERS[provider][1])
                    if provider == 'openai':
                        self.assertEqual(body['max_completion_tokens'], 500)
                        self.assertEqual(body['reasoning_effort'], 'none')
                    else:
                        self.assertEqual(body['max_tokens'], 500)
                        self.assertNotIn('max_completion_tokens', body)
                        self.assertNotIn('reasoning_effort', body)
                    self.assertIn('Provider: '+rsh_ai.PROVIDERS[provider][0], serial.output)
                    self.assertEqual(session['messages'][-1]['content'], 'Reply')

    def test_ollama_needs_no_key_and_supports_custom_host(self):
        self.config.write_text(json.dumps({'provider': 'ollama', 'base_url': 'http://192.0.2.1:11434/v1/'}), encoding='utf-8')
        with patch.object(rsh_ai, 'OpenAI') as constructor:
            rsh_ai.create_session(FakeSerial(), False)
        constructor.assert_called_once_with(api_key='ollama', base_url='http://192.0.2.1:11434/v1/', timeout=60.0, max_retries=0)

    def test_provider_override_does_not_reuse_another_providers_key_or_model(self):
        self.config.write_text(json.dumps({'api_key': 'openai-only', 'model': 'openai-only-model'}), encoding='utf-8')
        with patch.dict(rsh_ai.os.environ, {'AI_PROVIDER': 'gemini'}), patch.object(rsh_ai, 'OpenAI') as constructor:
            serial = FakeSerial()
            self.assertIsNone(rsh_ai.create_session(serial, False))
            self.assertIn('GEMINI_API_KEY', serial.output)
            constructor.assert_not_called()
            self.assertEqual(rsh_ai._load_chat_options()['model'], rsh_ai.PROVIDERS['gemini'][1])

    def test_invalid_configuration_never_constructs_a_client(self):
        for config in ('{', '[]', '{"provider":"unknown"}',
                       '{"provider":"ollama","base_url":"file:///tmp/v1"}',
                       '{"provider":"ollama","base_url":"http://localhost:11434"}',
                       '{"provider":"ollama","max_tokens":true}',
                       '{"provider":"ollama","max_tokens":0}',
                       '{"api_key":"YOUR_OPENAI_API_KEY_HERE"}'):
            with self.subTest(config=config), patch.object(rsh_ai, 'OpenAI') as constructor:
                self.config.write_text(config, encoding='utf-8')
                serial = FakeSerial()
                self.assertIsNone(rsh_ai.create_session(serial, False))
                self.assertIn('AI configuration error', serial.output)
                constructor.assert_not_called()

    def test_reopening_changes_provider_but_existing_conversation_and_new_command_stay_bound(self):
        self.config.write_text('{"provider":"ollama"}', encoding='utf-8')
        first_client, second_client = Mock(), Mock()
        first_client.chat.completions.create.return_value = Mock(choices=[Mock(message=Mock(content='Local reply'))])
        with patch.object(rsh_ai, '_create_client', side_effect=[first_client, second_client]):
            first = rsh_ai.create_session(FakeSerial(), False)
            self.config.write_text('{"provider":"gemini","api_key":"gemini-test"}', encoding='utf-8')
            second = rsh_ai.create_session(FakeSerial(), False)
        self.assertEqual(second['provider'], 'gemini')
        serial = FakeSerial()
        rsh_ai.handle_input(first, 'Still local', serial, False)
        first_client.chat.completions.create.assert_called_once()
        second_client.chat.completions.create.assert_not_called()
        rsh_ai.handle_input(first, 'N', serial, False)
        self.assertEqual(len(first['messages']), 1)
        self.assertIn('Provider: Local Ollama', serial.output)

    def test_quota_failure_does_not_switch_providers_or_keep_failed_turn(self):
        self.config.write_text('{"provider":"gemini","api_key":"gemini-test"}', encoding='utf-8')
        client = Mock(api_key='gemini-test')
        error = RuntimeError('quota for gemini-test exceeded')
        error.status_code = 429
        client.chat.completions.create.side_effect = error
        with patch.object(rsh_ai, '_create_client', return_value=client) as constructor:
            serial = FakeSerial()
            session = rsh_ai.create_session(serial, False)
            rsh_ai.handle_input(session, 'Question', serial, False)
            self.assertEqual(constructor.call_count, 1)
        self.assertEqual(len(session['messages']), 1)
        self.assertIn('quota or rate limit', serial.output)
        self.assertNotIn('gemini-test', serial.output)

    def test_custom_budget_and_gemini_reasoning_do_not_inherit_openai_environment(self):
        self.config.write_text('{"provider":"gemini","max_tokens":1024,"reasoning_effort":"low"}', encoding='utf-8')
        with patch.dict(rsh_ai.os.environ, {'OPENAI_MODEL': 'openai-only', 'OPENAI_REASONING_EFFORT': 'none'}):
            options = rsh_ai._load_chat_options()
        self.assertEqual(options, {'model': 'gemini-3.8-flash', 'max_tokens': 1024, 'reasoning_effort': 'low'})

    def test_gemini_reasoning_is_omitted_unless_explicitly_selected(self):
        for model in ('gemini-3.8-flash', 'custom-gemini-model'):
            for effort in (None, 'default', 'low'):
                with self.subTest(model=model, effort=effort):
                    config = {'provider': 'gemini', 'model': model}
                    if effort is not None:
                        config['reasoning_effort'] = effort
                    with patch.dict(rsh_ai.os.environ, {'OPENAI_REASONING_EFFORT': 'minimal'}):
                        options = rsh_ai._load_chat_options(config)
                    if effort == 'low':
                        self.assertEqual(options['reasoning_effort'], 'low')
                    else:
                        self.assertNotIn('reasoning_effort', options)

    def test_empty_reply_or_local_connection_failure_can_be_retried(self):
        for failure in ('empty', 'connection'):
            with self.subTest(failure=failure):
                self.config.write_text('{"provider":"ollama"}', encoding='utf-8')
                client = Mock(api_key='ollama')
                client.chat.completions.create.side_effect = [
                    Mock(choices=[Mock(message=Mock(content=''))]) if failure == 'empty' else RuntimeError('Connection refused'),
                    Mock(choices=[Mock(message=Mock(content='Recovered'))]),
                ]
                with patch.object(rsh_ai, '_create_client', return_value=client):
                    serial = FakeSerial()
                    session = rsh_ai.create_session(serial, False)
                rsh_ai.handle_input(session, 'Question', serial, False)
                self.assertEqual(len(session['messages']), 1)
                self.assertIn('ollama list', serial.output)
                rsh_ai.handle_input(session, 'Question', serial, False)
                self.assertEqual(len(session['messages']), 3)
                self.assertEqual(session['messages'][-1]['content'], 'Recovered')
                self.assertEqual(rsh_ai.handle_input(session, 'Q', serial, False), (True, 'MENU'))
                client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
