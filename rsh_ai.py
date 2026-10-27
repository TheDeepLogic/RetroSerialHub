#!/usr/bin/env python3
"""
AI interaction module for RetroSerialHub.

Uses OpenAI-compatible chat endpoints for OpenAI, Gemini, and local Ollama.
"""

from rsh_storage import settings_path
import os
import json
from urllib.parse import urlsplit
from openai import OpenAI
from rsh_terminal import clear_terminal_screen

CONFIG_FILE = settings_path("ai_config.json")
DEFAULT_MODEL = "gpt-5.6-terra"
PROVIDERS = {
    "openai": ("OpenAI", DEFAULT_MODEL, "https://api.openai.com/v1", "OPENAI_API_KEY"),
    "gemini": ("Google Gemini", "gemini-3.8-flash", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "ollama": ("Local Ollama", "llama3.2:3b", "http://localhost:11434/v1/", None),
}
SYSTEM_PROMPT = (
    "You are a helpful AI assistant in a retro BBS system. Keep responses "
    "concise and informative. Use ASCII art sparingly and only when "
    "specifically requested."
)

def write(ser, s):
    """Write a string to the serial port."""
    ser.write(s.encode('ascii', errors='ignore'))

def write_header(ser, use_ansi, model=DEFAULT_MODEL, provider="openai"):
    """Show the AI chat header."""
    clear_terminal_screen(ser, use_ansi)
    write(ser, "\r\nLogicNet AI Assistant\r\n")
    write(ser, "--------------------------------------\r\n\r\n")
    write(ser, f"Provider: {PROVIDERS[provider][0]}\r\nModel: {model}\r\n\r\n")
    write_help(ser)
    
def write_help(ser):
    """Show the available commands."""
    write(ser, "Commands:\r\n")
    write(ser, "  N = Start new conversation\r\n")
    write(ser, "  Q = Return to main menu\r\n")
    write(ser, "\r\nAsk any question or type a command. The AI will maintain\r\n")
    write(ser, "context of your conversation until you start a new one.\r\n")
    write(ser, "\r\nEnter your message: ")

def _load_config():
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open(encoding="utf-8") as config_file:
                config = json.load(config_file)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Cannot read settings/local/ai_config.json; check its permissions and JSON format.") from exc
        else:
            if isinstance(config, dict):
                return config
            raise ValueError("settings/local/ai_config.json must contain a JSON object.")
    return {}


def _provider(config):
    provider = os.environ.get("AI_PROVIDER") or config.get("provider", "openai")
    if not isinstance(provider, str) or provider.strip().lower() not in PROVIDERS:
        raise ValueError("AI provider must be openai, gemini, or ollama.")
    return provider.strip().lower()


def _load_chat_options(config=None, provider=None):
    config = _load_config() if config is None else config
    provider = provider or _provider(config)
    # An environment provider override must not reuse another provider's settings.
    same_provider = provider == str(config.get("provider", "openai")).strip().lower()
    selected = config if same_provider else {}
    default_model = PROVIDERS[provider][1]
    model = os.environ.get("AI_MODEL") or os.environ.get(provider.upper()+"_MODEL") or selected.get("model", default_model)
    if model in (None, ""):
        model = default_model
    if not isinstance(model, str) or not model.strip():
        raise ValueError("AI model must be a model ID string in settings/local/ai_config.json or AI_MODEL.")
    model = model.strip()
    budget = selected.get("max_tokens", 500)
    if type(budget) is not int or not 1 <= budget <= 8192:
        raise ValueError("max_tokens must be an integer between 1 and 8192.")
    options = {"model": model, "max_completion_tokens" if provider == "openai" else "max_tokens": budget}
    if provider == "gemini":
        effort = selected.get("reasoning_effort")
        if effort not in (None, '', 'default'):
            if effort not in ('minimal', 'low', 'medium', 'high'):
                raise ValueError("Gemini reasoning_effort must be minimal, low, medium, high, or default.")
            options['reasoning_effort'] = effort
    if provider != "openai":
        return options
    effort = os.environ.get("OPENAI_REASONING_EFFORT") or selected.get("reasoning_effort")
    if effort is None and model == DEFAULT_MODEL:
        # Do not spend the short serial response budget on hidden reasoning.
        effort = "none"
    if effort not in (None, "", "default"):
        if effort not in ("none", "minimal", "low", "medium", "high", "xhigh", "max"):
            raise ValueError("Invalid reasoning_effort setting. Use default to let the selected model decide.")
        options["reasoning_effort"] = effort
    return options


def _create_client(config, provider):
    _, _, base_url, key_variable = PROVIDERS[provider]
    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL") or config.get("base_url") or base_url
        if not isinstance(base_url, str):
            raise ValueError("Ollama base_url must be an HTTP(S) URL ending in /v1/.")
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or
                parsed.username or parsed.password or parsed.query or parsed.fragment or
                parsed.path.rstrip("/") != "/v1"):
            raise ValueError("Ollama base_url must be an HTTP(S) URL ending in /v1/.")
        key = "ollama"  # SDK requires a value; local Ollama ignores it.
    else:
        same_provider = provider == str(config.get("provider", "openai")).strip().lower()
        key = os.environ.get(key_variable) or (config.get("api_key") if same_provider else None)
        if (not isinstance(key, str) or not key.strip() or
                key.strip().lower().startswith(("your", "replace"))):
            raise ValueError(f"{PROVIDERS[provider][0]} API key not configured. Set {key_variable} or api_key in settings/local/ai_config.json. Local Ollama needs no key.")
        key = key.strip()
    return OpenAI(api_key=key, base_url=base_url, timeout=60.0, max_retries=0)

def create_session(ser, use_ansi=True):
    """Initialize a new AI chat session.
    
    Returns a dict with conversation state that will be passed to handle_input.
    """
    try:
        config = _load_config()
        provider = _provider(config)
        options = _load_chat_options(config, provider)
        client = _create_client(config, provider)
    except ValueError as exc:
        write(ser, f"\r\n*** AI configuration error: {exc} ***\r\n")
        return None
        
    write_header(ser, use_ansi, options["model"], provider)
    return {
        'client': client,
        'provider': provider,
        'request_options': options,
        'messages': [
            {"role": "system", "content": SYSTEM_PROMPT}
        ],
        'pending_response': False
    }

def handle_input(session, line_str, ser, use_ansi=True):
    """Handle user input in the AI chat session.
    
    Args:
        session: The session object from create_session()
        line_str: The line typed by the user
        ser: Serial port to write responses to
        use_ansi: Whether to use ANSI escape codes
        
    Returns:
        (consumed, action) where consumed is True if input was handled,
        and action is None to continue or 'MENU' to exit.
    """
    client = session.get('client')
    if client is None:
        return True, 'MENU'
        
    if not line_str:
        # Just pressed Enter - show the help
        write_help(ser)
        return True, None
        
    upper = line_str.upper()
    if upper == 'Q':
        client.close()
        return True, 'MENU'
        
    if upper == 'N':
        # Start fresh conversation with just the system message
        session['messages'] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        write_header(ser, use_ansi, session['request_options']['model'], session['provider'])
        return True, None
        
    # Normal message - send to AI
    write(ser, "\r\n")
    
    try:
        # Add user message to history
        session['messages'].append({"role": "user", "content": line_str})
        
        # Call the provider captured when this session opened.
        try:
            response = client.chat.completions.create(
                messages=session['messages'],
                **session['request_options']
            )

            # Get response content
            content = response.choices[0].message.content or ""
            if not content.strip():
                raise ValueError("Provider returned no text. Try a different model.")
            session['messages'].append(
                {"role": "assistant", "content": content}
            )

            # Format and display response
            content = content.strip()
            # Split into lines and add proper line endings
            lines = [ln.rstrip() for ln in content.splitlines()]
            for line in lines:
                write(ser, line + "\r\n")
                
        except Exception as e:
            detail = str(e).replace(client.api_key, '[redacted]') if isinstance(client.api_key, str) and client.api_key else str(e)
            write(ser, f"*** API Error: {detail} ***\r\n")
            if session.get('provider') == 'ollama':
                write(ser, "Check Ollama is running and the model is installed (ollama list).\r\n")
            elif getattr(e, 'status_code', None) == 429:
                write(ser, "Provider quota or rate limit reached; try again later.\r\n")
            if getattr(e, "code", None) == "model_not_found":
                write(ser, "Choose an available model using the model field in settings/local/ai_config.json\r\n")
                write(ser, "or AI_MODEL (OPENAI_MODEL for OpenAI), then reopen the assistant.\r\n")
            # Remove failed message from history
            session['messages'].pop()
            
    except Exception as e:
        write(ser, f"*** Error: {str(e)} ***\r\n")
        
    write(ser, "\r\n")
    write(ser, "Enter your message (N=New conversation, Q=Quit): ")
    return True, None
