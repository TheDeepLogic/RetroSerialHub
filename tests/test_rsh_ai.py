import unittest
import json
import tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import ANY, Mock, patch

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
        patch.dict(rsh_ai.os.environ, {"OPENAI_MODEL": "", "OPENAI_REASONING_EFFORT": ""}).start()

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

        with patch.object(rsh_ai, "client", openai_client):
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

        with patch.object(rsh_ai, "client", openai_client):
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
        with patch.object(rsh_ai, "client", client):
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
        with patch.object(rsh_ai, "client", client):
            self.assertIsNone(rsh_ai.create_session(serial, use_ansi=False))
        client.chat.completions.create.assert_not_called()
        self.assertIn("AI configuration error", serial.output)

    def test_model_not_found_explains_how_to_change_model_and_keeps_history_clean(self):
        class MissingModelError(Exception):
            code = "model_not_found"
        serial, client = FakeSerial(), Mock()
        client.chat.completions.create.side_effect = MissingModelError("Model is unavailable")
        session = {"messages": [{"role": "system", "content": "system"}]}
        with patch.object(rsh_ai, "client", client):
            rsh_ai.handle_input(session, "Hello", serial, use_ansi=False)
        self.assertEqual(len(session["messages"]), 1)
        self.assertIn("OPENAI_MODEL", serial.output)

    def test_reasoning_default_can_be_explicitly_omitted(self):
        self.config.write_text(json.dumps({"model": rsh_ai.DEFAULT_MODEL, "reasoning_effort": "default"}), encoding="utf-8")
        self.assertNotIn("reasoning_effort", rsh_ai._load_chat_options())


if __name__ == "__main__":
    unittest.main()
