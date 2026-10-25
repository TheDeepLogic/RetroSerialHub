#!/usr/bin/env python3
"""
AI interaction module for RetroSerialHub.

Uses OpenAI's Chat Completions API with a configurable model and a short
response budget suitable for serial terminals.
"""

import os
import json
from pathlib import Path
from openai import OpenAI
from rsh_terminal import clear_terminal_screen

# Load OpenAI API key from config file or environment
CONFIG_FILE = Path(__file__).resolve().parent / "ai_config.json"
DEFAULT_MODEL = "gpt-5.6-terra"
SYSTEM_PROMPT = (
    "You are a helpful AI assistant in a retro BBS system. Keep responses "
    "concise and informative. Use ASCII art sparingly and only when "
    "specifically requested."
)

def write(ser, s):
    """Write a string to the serial port."""
    ser.write(s.encode('ascii', errors='ignore'))

def write_header(ser, use_ansi, model=DEFAULT_MODEL):
    """Show the AI chat header."""
    clear_terminal_screen(ser, use_ansi)
    write(ser, "\r\nLogicNet AI Assistant (powered by ChatGPT)\r\n")
    write(ser, "--------------------------------------\r\n\r\n")
    write(ser, f"Model: {model}\r\n\r\n")
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
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Config file error: {exc}")
        else:
            if isinstance(config, dict):
                return config
            print("Config file error: ai_config.json must contain a JSON object.")
    return {}


def _load_api_key():
    return _load_config().get("api_key") or os.environ.get("OPENAI_API_KEY")


def _load_chat_options():
    config = _load_config()
    model = os.environ.get("OPENAI_MODEL") or config.get("model", DEFAULT_MODEL)
    if model in (None, ""):
        model = DEFAULT_MODEL
    if not isinstance(model, str) or not model.strip():
        raise ValueError("AI model must be a model ID string in ai_config.json or OPENAI_MODEL.")
    model = model.strip()
    options = {"model": model, "max_completion_tokens": 500}
    effort = os.environ.get("OPENAI_REASONING_EFFORT") or config.get("reasoning_effort")
    if effort is None and model == DEFAULT_MODEL:
        # Do not spend the short serial response budget on hidden reasoning.
        effort = "none"
    if effort not in (None, "", "default"):
        if effort not in ("none", "minimal", "low", "medium", "high", "xhigh", "max"):
            raise ValueError("Invalid reasoning_effort setting. Use default to let the selected model decide.")
        options["reasoning_effort"] = effort
    return options


_api_key = _load_api_key()
client = OpenAI(api_key=_api_key) if _api_key else None

def create_session(ser, use_ansi=True):
    """Initialize a new AI chat session.
    
    Returns a dict with conversation state that will be passed to handle_input.
    """
    if client is None:
        clear_terminal_screen(ser, use_ansi)
        write(ser, "\r\n*** Error: OpenAI API key not configured ***\r\n")
        write(ser, "Please create ai_config.json with {'api_key': 'your-key'}\r\n")
        write(ser, "or set OPENAI_API_KEY environment variable.\r\n")
        return None

    try:
        options = _load_chat_options()
    except ValueError as exc:
        write(ser, f"\r\n*** AI configuration error: {exc} ***\r\n")
        return None
        
    write_header(ser, use_ansi, options["model"])
    return {
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
    if client is None:
        return True, 'MENU'
        
    if not line_str:
        # Just pressed Enter - show the help
        write_help(ser)
        return True, None
        
    upper = line_str.upper()
    if upper == 'Q':
        return True, 'MENU'
        
    if upper == 'N':
        # Start fresh conversation with just the system message
        session['messages'] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        write_header(ser, use_ansi, session.get('request_options', {}).get('model', DEFAULT_MODEL))
        return True, None
        
    # Normal message - send to AI
    write(ser, "\r\n")
    
    try:
        # Add user message to history
        session['messages'].append({"role": "user", "content": line_str})
        
        # Call ChatGPT API
        try:
            response = client.chat.completions.create(
                messages=session['messages'],
                **(session.get('request_options') or _load_chat_options())
            )

            # Get response content
            content = response.choices[0].message.content or ""
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
            write(ser, f"*** API Error: {str(e)} ***\r\n")
            if getattr(e, "code", None) == "model_not_found":
                write(ser, "Choose an available model using the model field in ai_config.json\r\n")
                write(ser, "or the OPENAI_MODEL environment variable, then reopen the assistant.\r\n")
            # Remove failed message from history
            session['messages'].pop()
            
    except Exception as e:
        write(ser, f"*** Error: {str(e)} ***\r\n")
        
    write(ser, "\r\n")
    write(ser, "Enter your message (N=New conversation, Q=Quit): ")
    return True, None
