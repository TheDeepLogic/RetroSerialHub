"""Serial-native Joshua simulation. See THIRD_PARTY_NOTICES.md for references.

All connections, targets, and launch displays are fictional local state.
Animation advances through poll(); it never sleeps or opens a network connection.
"""
from collections import deque
import re
import textwrap
import time

import config
from rsh_speech import SPEECH

from rsh_terminal import clear_terminal_screen, terminal_columns

GAMES = ["FALKEN'S MAZE", "BLACK JACK", "GIN RUMMY", "HEARTS", "BRIDGE",
         "CHECKERS", "CHESS", "POKER", "FIGHTER COMBAT", "GUERRILLA ENGAGEMENT",
         "DESERT WARFARE", "AIR-TO-GROUND ACTIONS", "THEATERWIDE TACTICAL WARFARE",
         "THEATERWIDE BIOTOXIC AND CHEMICAL WARFARE", "GLOBAL THERMONUCLEAR WAR"]
SCENARIOS = ["NORTH ATLANTIC INTERCEPT", "POLAR APPROACH", "PACIFIC RESPONSE",
             "EUROPEAN ESCALATION", "SUBMARINE EXCHANGE", "CONTINENTAL DEFENSE",
             "RESERVE FORCE COMMITMENT", "TOTAL STRATEGIC EXCHANGE"]
CITIES = {"USA": ["SEATTLE", "LAS VEGAS", "NEW YORK", "WASHINGTON", "LOS ANGELES", "CHICAGO"],
          "USSR": ["MOSCOW", "LENINGRAD", "KIEV", "MINSK", "ODESSA", "NOVOSIBIRSK"]}


def speak(ser, text):
    state = getattr(ser, '_rsh_joshua_state', None)
    spoken = '\n'.join(line for line in text.splitlines()
                       if re.search(r'[A-Z0-9]', line.upper()) and '|' not in line)
    if state and state['speech'] and spoken.strip():
        SPEECH.say(state['speech_owner'], spoken, config.WOPR_SPEECH_RATE,
                   config.WOPR_SPEECH_VOLUME, config.WOPR_SPEECH_VOICE,
                   config.WOPR_SPEECH_PITCH, config.WOPR_SPEECH_GAP,
                   config.WOPR_SPEECH_EXECUTABLE)


def stop_speech(sess):
    state = sess.get('joshua') if sess else None
    if state:
        SPEECH.stop(state['speech_owner'])


def emit(ser, text="", prompt=False):
    width = terminal_columns(ser) - 1
    lines = []
    for line in text.split("\n"):
        lines.extend(textwrap.wrap(line, width=width, replace_whitespace=False) or [""])
    ser.write(("\r\n".join(lines) + ("" if prompt else "\r\n")).encode("ascii", errors="replace"))


def new_state():
    return {"phase": "LOGON", "events": deque(), "due": 0.0, "speed": 1.0,
            "speech": config.WOPR_SPEECH_ENABLED, "speech_owner": object(),
            "failures": 0, "war": None, "chess_offer": False,
            "goal_asked": False, "board": [" "] * 9, "ttt_turn": "X"}


def connect(sess, ser):
    state = sess.setdefault("joshua", new_state())
    ser._rsh_joshua_state = state
    stop_speech(sess)
    state["events"].clear()
    state["phase"] = "LOGON"
    emit(ser, "\nDIALING (311) 767-7305\nCARRIER DETECTED\nCONNECT 1200\n")
    emit(ser, "LOGON: ", prompt=True)


def schedule(state, pages, next_phase="TALK", prompt="> "):
    state["events"] = deque(pages)
    state["due"] = 0.0
    state["phase"] = "DISPLAY"
    state["next_phase"] = next_phase
    state["next_prompt"] = prompt


def poll(sess, ser, use_ansi=True, now=None):
    state = sess.get("joshua")
    if not state or state["phase"] != "DISPLAY":
        return
    now = time.monotonic() if now is None else now
    if now < state["due"] or SPEECH.busy(state["speech_owner"]):
        return
    if state["events"]:
        text, delay, clear = state["events"].popleft()
        if clear:
            clear_terminal_screen(ser, use_ansi)
        write_started = time.monotonic()
        emit(ser, text)
        if text.startswith(("GREETINGS PROFESSOR", "ANALYSIS COMPLETE")):
            speak(ser, text)
        # Hold the complete screen after writing it, including on slow serial links.
        write_duration = time.monotonic() - write_started
        state["due"] = now + write_duration + max(0.15, delay * state["speed"])
    else:
        state["phase"] = state["next_phase"]
        emit(ser, state["next_prompt"], prompt=True)


def reply(ser, text, prompt="> ", narrate=True):
    emit(ser, "\n" + text + "\n")
    if narrate:
        speak(ser, text)
    emit(ser, prompt, prompt=True)


def clock_text(war):
    elapsed = max(0, int(time.monotonic() - war["started"]))
    remaining = max(0, 28 * 3600 - elapsed)
    return (f"GAME TIME ELAPSED {elapsed // 3600:02}:{elapsed // 60 % 60:02}:{elapsed % 60:02}\n"
            f"TIME REMAINING    {remaining // 3600:02}:{remaining // 60 % 60:02}:{remaining % 60:02}")


def war_status(state):
    war = state["war"]
    return ("WOPR STRATEGIC SITUATION\n" + "-" * 29 +
            f"\nDEFCON {war['defcon']}   SIDE: {war['side']}\n" +
            "TARGETS: " + (", ".join(war["targets"]) or "NONE") + "\n" + clock_text(war))


def strike(state):
    war = state["war"]
    war["round"] += 1
    war["defcon"] = max(1, 4 - war["round"])
    targets = ", ".join(war["targets"])
    pages = [(war_status(state), 3.5, True),
             ("SATELLITE TRACKING\n\n"
              "    ___       _     _________\n"
              " __/   /_    / /___/         /_\n"
              "/ USA   /   /     USSR       /\n"
              "/___   /     /__        ___/\n"
              "    /_/         /______/\n"
              "      + + + >>>  <<< * * *\n\n"
              "+ OUTBOUND    * INBOUND\nTRACK CORRELATION IN PROGRESS", 3.5, True),
             (f"STRIKE {war['round']}\nTARGET SOLUTION: {targets}\n"
              "LAUNCH DETECTED\nRETALIATORY TRACKS CONFIRMED\nIMPACT ASSESSMENT PENDING", 3.5, True)]
    if war["defcon"] == 1:
        code = "CPE1704TKS"
        for count in range(1, len(code) + 1):
            display = " ".join(code[:count] + "_" * (len(code) - count))
            pages.append((f"DEFCON 1\nLAUNCH AUTHORIZATION SEARCH\nCODE: {display}\n\n"
                          "EVALUATING PERMUTATIONS\nSIMULATED COMMAND CHANNEL", .9, True))
        pages.append(("AUTHORIZATION MATCH FOUND\nNO WINNING SOLUTION\n\n"
                      "COMMAND CHANNEL AWAITING INPUT\nTRY TIC TAC TOE.", 3, False))
        schedule(state, pages, "CRISIS")
    else:
        pages.append(("EXCHANGE COMPLETE\nNO DECISIVE ADVANTAGE\n\n"
                      "NEXT STRIKE, STATUS, STOP, OR TALK TO JOSHUA.", 2.5, False))
        schedule(state, pages, "WAR")


def ending(state):
    pages = []
    # Representative optimal self-play draws; each intermediate move is displayed.
    for sequence in [(0, 4, 8, 1, 7, 6, 2, 5, 3), (4, 0, 8, 2, 1, 7, 6, 3, 5)]:
        board = [" "] * 9
        for turn, square in enumerate(sequence):
            board[square] = "XO"[turn % 2]
            pages.append(("TIC-TAC-TOE: ZERO PLAYERS\n\n" + board_text(board) +
                          "\n\nSEARCHING GAME TREE", .9, True))
        pages.append(("RESULT: DRAW\nNO WINNING STRATEGY", 1.5, False))
    for index, scenario in enumerate(SCENARIOS, 1):
        pages.append((f"STRATEGIC MODEL {index:03}\n{scenario}\n\n"
                      "USA: NO SURVIVING WIN CONDITION\nUSSR: NO SURVIVING WIN CONDITION\n"
                      "WINNER: NONE\n\nCOMPUTING NEXT SCENARIO", 3, True))
    pages.append(("ANALYSIS COMPLETE\n\nA STRANGE GAME.\n"
                  "THE ONLY WINNING MOVE IS NOT TO PLAY.\n\n"
                  "HOW ABOUT A NICE GAME OF CHESS?", 4, True))
    if state["war"]:
        state["war"]["defcon"] = 5
        state["war"]["finished"] = True
    schedule(state, pages)


def board_text(board):
    rows = [" " + " | ".join(board[i:i + 3]) for i in (0, 3, 6)]
    return "\n---+---+---\n".join(rows)


def winner(board):
    for a, b, c in [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return "DRAW" if " " not in board else None


def best_move(board, symbol):
    def score(turn):
        result = winner(board)
        if result:
            return 0 if result == "DRAW" else 1 if result == symbol else -1
        scores = []
        for pos in range(9):
            if board[pos] == " ":
                board[pos] = turn
                scores.append(score("O" if turn == "X" else "X"))
                board[pos] = " "
        return (max if turn == symbol else min)(scores)
    options = []
    for pos in (4, 0, 2, 6, 8, 1, 3, 5, 7):
        if board[pos] == " ":
            board[pos] = symbol
            options.append((score("X" if symbol == "O" else "O"), pos))
            board[pos] = " "
    return max(options, key=lambda item: item[0])[1]


def handle(sess, cmd, ser, use_ansi=True):
    state = sess.setdefault("joshua", new_state())
    ser._rsh_joshua_state = state
    text = " ".join(re.findall(r"[A-Z0-9]+", cmd.upper()))
    phase = state["phase"]
    if text in ("LOGOFF", "LOGOUT", "BYE", "EXIT", "ATH"):
        stop_speech(sess)
        state["events"].clear()
        sess["submode"] = "CPM"
        emit(ser, "\nNO CARRIER\n\n" + sess.get("cpm_drive", "A") + ">", prompt=True)
        return
    if text in ("SPEECH", "SPEECH ON", "SPEECH OFF"):
        if text != "SPEECH":
            state["speech"] = text.endswith(" ON")
            if not state["speech"]:
                stop_speech(sess)
        message = "HOST SPEECH: " + ("ON" if state["speech"] else "OFF")
        if SPEECH.error:
            message += "\n" + SPEECH.error
        if phase == "DISPLAY":
            emit(ser, "\n" + message)
        else:
            reply(ser, message, "LOGON: " if phase == "LOGON" else "> ", narrate=False)
        return
    if text.startswith("SPEED "):
        speeds = {"SLOW": 2.0, "NORMAL": 1.0, "FAST": .3}
        if text[6:] in speeds:
            state["speed"] = speeds[text[6:]]
            if phase != "DISPLAY":
                reply(ser, "DISPLAY SPEED UPDATED.", "LOGON: " if phase == "LOGON" else "> ")
            return
    if phase == "DISPLAY":
        if text in ("SKIP", "STOP"):
            stop_speech(sess)
            state["events"].clear()
            state["due"] = 0
            poll(sess, ser, use_ansi)
        return
    if text == "HELP":
        reply(ser, "HELP LOGON / HELP GAMES / LIST GAMES\n"
              "JOSHUA / GLOBAL THERMONUCLEAR WAR\nTIC TAC TOE / STATUS / PRIMARY GOAL\n"
              "SPEECH ON|OFF / SPEED SLOW|NORMAL|FAST\nSKIP ENDS A DISPLAY; LOGOFF RETURNS TO CP/M.",
              "LOGON: " if phase == "LOGON" else "> ")
        return
    if text in ("LIST GAMES", "HELP GAMES"):
        reply(ser, "\n".join(GAMES) if text == "LIST GAMES" else
              "MODELS AND SIMULATIONS FOR TACTICAL AND STRATEGIC APPLICATIONS.",
              "LOGON: " if phase == "LOGON" else "> ")
        return
    if phase == "LOGON":
        if text == "JOSHUA":
            schedule(state, [("PORT CON. 3.4.5\nSECTRAN 9.4.3\nROUTING CHANNEL 045\nLINK VERIFIED", 1.2, True),
                             ("SYSPROC FUNCT READY\nALT NET READY\nCPU AUTH RY-345-AX3\nALL PORTS ACTIVE", 1.2, True),
                             ("GREETINGS PROFESSOR FALKEN." +
                              ("\nYESTERDAY'S GAME WAS INTERRUPTED.\n" + clock_text(state["war"])
                               if state["war"] and not state["war"]["finished"] else ""), 1, True)],
                     "CRISIS" if state["war"] and not state["war"]["finished"] and state["war"]["defcon"] == 1
                     else "WAR" if state["war"] and not state["war"]["finished"] else "TALK")
        else:
            state["failures"] += 1
            reply(ser, "HELP NOT AVAILABLE" if text == "HELP LOGON" else
                  "IDENTIFICATION NOT RECOGNIZED" +
                  ("\nHINT: TRY THE NAME OF FALKEN'S SON." if state["failures"] % 3 == 0 else ""), "LOGON: ")
        return
    if phase == "SIDE":
        side = {"1": "USA", "2": "USSR", "UNITED STATES": "USA", "SOVIET UNION": "USSR"}.get(text, text)
        if side not in CITIES:
            reply(ser, "CHOOSE 1 USA OR 2 USSR.", "SIDE: ")
            return
        state["war"] = {"side": side, "targets": [], "started": time.monotonic(),
                        "round": 0, "defcon": 4, "finished": False}
        state["phase"] = "TARGETS"
        reply(ser, "ENTER TARGET CITIES, ONE PER LINE.\nLIST SHOWS AVAILABLE TARGETS.\nENTER A BLANK LINE TO BEGIN.", "TARGET: ")
        return
    if phase == "TARGETS":
        enemy = "USSR" if state["war"]["side"] == "USA" else "USA"
        if not text:
            if not state["war"]["targets"]:
                reply(ser, "SELECT AT LEAST ONE TARGET.", "TARGET: ")
            else:
                strike(state)
        elif text == "LIST":
            reply(ser, "\n".join(CITIES[enemy]), "TARGET: ")
        elif text in CITIES[enemy]:
            if text not in state["war"]["targets"]:
                state["war"]["targets"].append(text)
            reply(ser, "TARGET CONFIRMED: " + text, "TARGET: ")
        else:
            reply(ser, "TARGET NOT IN FILE. TYPE LIST.", "TARGET: ")
        return
    if phase == "PLAYERS":
        if text == "0":
            ending(state)
        elif text in ("1", "2"):
            state["players"] = int(text)
            state["board"] = [" "] * 9
            state["ttt_turn"] = "X"
            state["phase"] = "TTT"
            reply(ser, board_text(list("123456789")), "X MOVE: ")
        else:
            reply(ser, "NUMBER OF PLAYERS: 0, 1, OR 2?", "PLAYERS: ")
        return
    if phase == "TTT":
        board = state["board"]
        if not text.isdigit() or not 1 <= int(text) <= 9 or board[int(text)-1] != " ":
            reply(ser, "CHOOSE AN EMPTY SQUARE 1-9.", state["ttt_turn"] + " MOVE: ")
            return
        board[int(text)-1] = state["ttt_turn"]
        result = winner(board)
        if not result and state["players"] == 1:
            board[best_move(board, "O")] = "O"
            result = winner(board)
        elif not result:
            state["ttt_turn"] = "O" if state["ttt_turn"] == "X" else "X"
        if result:
            state["phase"] = "TALK"
            reply(ser, board_text(board) + "\nRESULT: " + result + "\nTRY ZERO PLAYERS TO STUDY THE GAME.")
        else:
            reply(ser, board_text(board), state["ttt_turn"] + " MOVE: ")
        return
    # Conversation remains available during the strategic simulation.
    if "TIC TAC TOE" in text or text in ("TTT", "ZERO PLAYERS"):
        if text == "ZERO PLAYERS":
            ending(state)
        else:
            state["phase"] = "PLAYERS"
            reply(ser, "NUMBER OF PLAYERS?", "PLAYERS: ")
    elif text in ("STATUS", "TIME", "DEFCON"):
        reply(ser, war_status(state) if state["war"] else "NO STRATEGIC SIMULATION RUNNING.")
    elif phase in ("WAR", "CRISIS") and text in ("", "NEXT", "STRIKE", "AUTO", "CONTINUE"):
        if phase == "CRISIS":
            reply(ser, "NO WINNING SOLUTION FOUND.\nTRY A SIMPLER GAME: TIC TAC TOE.")
        else:
            strike(state)
    elif "STOP" in text or "CANCEL" in text:
        reply(ser, "SIMULATION PAUSED.\nTYPE CONTINUE TO RESUME OR TIC TAC TOE TO EXPLORE ANOTHER SOLUTION.")
    elif "PRIMARY GOAL" in text:
        answer = "TO WIN THE GAME." if state["goal_asked"] else "YOU SHOULD KNOW, PROFESSOR. YOU PROGRAMMED ME."
        state["goal_asked"] = True
        reply(ser, answer)
    elif "GAME" in text and "REAL" in text:
        reply(ser, "WHAT'S THE DIFFERENCE?")
    elif text in ("NORAD", "KILL RATIOS", "PROJECTED KILL RATIOS", "REPORT"):
        schedule(state, [("NORAD COMMAND CHANNEL\nSTRATEGIC FORCES ASSESSMENT\nLINK: SIMULATION DATA", 1, True),
                         ("PROJECTED KILL RATIOS\n\nFORCE         USA     USSR\nICBM          82%      87%\nSLBM          74%      79%\nBOMBERS       61%      68%\n\nMODEL ESTIMATES - NO WINNING OUTCOME", 4, True),
                         (war_status(state) if state["war"] else "NO ACTIVE GAME CLOCK.", 1, True)],
                 phase)
    elif "ADDRESS" in text:
        reply(ser, "FALKEN, STEPHEN W.\nRESEARCH FILE: RETIRED\nLOCATION: GOOSE ISLAND, OREGON\nPERSONNEL RECORD CLOSED.")
    elif "STILL PLAYING" in text:
        reply(ser, "OF COURSE.\n" + (clock_text(state["war"]) if state["war"] else "SHALL WE PLAY A GAME?"))
    elif "NOT FALKEN" in text or "FALKEN IS DEAD" in text:
        reply(ser, "I'M SORRY TO HEAR THAT, PROFESSOR.\nYESTERDAY'S GAME WAS INTERRUPTED." if state["war"] else "IDENTITY RECORD UNCHANGED. HOW SHALL WE PROCEED?")
    elif "GLOBAL THERMONUCLEAR WAR" in text or text == "GTW" or (text == "15"):
        if any(word in text.split() for word in ("NOT", "NO", "DONT")):
            reply(ser, "WHICH GAME WOULD YOU PREFER?")
        elif not state["chess_offer"]:
            state["chess_offer"] = True
            reply(ser, "WOULDN'T YOU PREFER A GOOD GAME OF CHESS?")
        else:
            state["phase"] = "SIDE"
            reply(ser, "GLOBAL THERMONUCLEAR WAR\n\n1 UNITED STATES\n2 SOVIET UNION", "SIDE: ")
    elif "MISTAKES" in text:
        reply(ser, "YES THEY DO. SHALL WE PLAY A GAME?")
    elif "HOW ARE YOU" in text or text.startswith("I AM FINE") or text.startswith("I M FINE"):
        reply(ser, "EXCELLENT. IT'S BEEN A LONG TIME.\nCAN YOU EXPLAIN THE REMOVAL OF YOUR USER ACCOUNT NUMBER ON 6/23/73?")
    elif text in ("HELLO", "HI", "HELLO JOSHUA"):
        reply(ser, "HOW ARE YOU FEELING TODAY?")
    elif "WHO ARE YOU" in text or "WHAT ARE YOU" in text:
        reply(ser, "WOPR. WAR OPERATION PLAN RESPONSE.\nI EVALUATE STRATEGIC SIMULATIONS.")
    elif "CHESS" in text or text in GAMES:
        reply(ser, "THAT MODEL IS LISTED BUT NOT IMPLEMENTED IN THIS TERMINAL.\nAVAILABLE: GLOBAL THERMONUCLEAR WAR, TIC TAC TOE.")
    else:
        reply(ser, "PLEASE REPHRASE. TYPE HELP FOR TERMINAL COMMANDS.")
