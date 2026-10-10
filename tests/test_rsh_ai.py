import unittest
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
            model="gpt-3.5-turbo",
            messages=ANY,
            max_tokens=500,
            temperature=0.7,
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


if __name__ == "__main__":
    unittest.main()
