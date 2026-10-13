"""Text-mode minesweeper and a small Klondike solitaire game."""

import random

_context = None
_mines = {}
_cards = {}
_SUITS = ("S", "H", "D", "C")
_RANKS = "A23456789TJQK"


def _new_minesweeper(rows, columns, count):
    if not (4 <= rows <= 16 and 4 <= columns <= 38 and 1 <= count < rows * columns):
        raise ValueError("Use rows 4-16, columns 4-38, and fewer mines than cells.")
    mines = set(random.sample(range(rows * columns), count))
    numbers = {}
    for cell in range(rows * columns):
        row, column = divmod(cell, columns)
        numbers[cell] = sum(
            (r * columns + c) in mines
            for r in range(max(0, row - 1), min(rows, row + 2))
            for c in range(max(0, column - 1), min(columns, column + 2))
        )
    return {"rows": rows, "columns": columns, "mines": mines, "numbers": numbers, "shown": set(), "flags": set(), "lost": False}


def _reveal_cell(game, cell):
    # First click safety: move mine if first action hits one
    if not game["shown"] and cell in game["mines"]:
        available = [c for c in range(game["rows"] * game["columns"]) if c not in game["mines"] and c != cell]
        if available:
            game["mines"].remove(cell)
            new_mine = random.choice(available)
            game["mines"].add(new_mine)
            for c_idx in range(game["rows"] * game["columns"]):
                r, c = divmod(c_idx, game["columns"])
                game["numbers"][c_idx] = sum(
                    (nr * game["columns"] + nc) in game["mines"]
                    for nr in range(max(0, r - 1), min(game["rows"], r + 2))
                    for nc in range(max(0, c - 1), min(game["columns"], c + 2))
                )

    queue = [cell]
    while queue:
        cur = queue.pop()
        if cur in game["flags"] or cur in game["shown"]:
            continue
        game["shown"].add(cur)
        if cur in game["mines"]:
            game["lost"] = True
            break
        # Cascade empty squares (0 neighboring mines)
        if game["numbers"][cur] == 0:
            r, c = divmod(cur, game["columns"])
            for nr in range(max(0, r - 1), min(game["rows"], r + 2)):
                for nc in range(max(0, c - 1), min(game["columns"], c + 2)):
                    neighbor = nr * game["columns"] + nc
                    if neighbor not in game["shown"] and neighbor not in game["flags"]:
                        queue.append(neighbor)


def _mine_board(game):
    lines = []
    col_hdr = "   " + " ".join(f"{c + 1}" for c in range(game["columns"]))
    lines.append(col_hdr)
    lines.append("  +" + "--" * game["columns"])
    for row in range(game["rows"]):
        cells = []
        for column in range(game["columns"]):
            cell = row * game["columns"] + column
            if cell in game["flags"]:
                symbol = "F"
            elif cell not in game["shown"] and not game["lost"]:
                symbol = "#"
            elif cell in game["mines"]:
                symbol = "*"
            else:
                symbol = str(game["numbers"][cell]) if game["numbers"][cell] else "."
            cells.append(symbol)
        lines.append(f"{row + 1:2d}| " + " ".join(cells))

    flags_left = len(game["mines"]) - len(game["flags"])
    lines.append(f"Mines: {len(game['mines'])} | Flags: {len(game['flags'])} | Remaining: {flags_left}")
    lines.append("Commands: r <row> <col> (reveal) | f <row> <col> (flag) | new [r c m]")
    lines.append("Rows and columns are 1-based.")
    return "\n".join(lines)


def _card_text(card):
    return "--" if card is None else card[0] + card[1]


def _solitaire_status(game, cols=None):
    if cols is None and _context and getattr(_context, "session", None):
        cols = getattr(_context.session, "cols", 80)
    cols = cols or 80

    columns = []
    for pile, face_up in zip(game["tableau"], game["face_up"]):
        visible = ["##"] * (len(pile) - face_up)
        visible.extend(_card_text(card) for card in pile[-face_up:])
        columns.append(" ".join(visible) or "--")

    stock_waste = "Stock: %d  Waste: %s" % (
        len(game["stock"]),
        _card_text(game["waste"][-1] if game["waste"] else None),
    )
    foundations = "Foundations: " + " ".join(
        _card_text(pile[-1] if pile else None) for pile in game["foundations"]
    )
    if cols < 50:
        header = f"{stock_waste}\n{foundations}"
        cmd_help = (
            "Commands: draw | auto | new\n"
            "          move <waste|1-7> <1-7|f1-f4>"
        )
    else:
        header = f"{stock_waste}  {foundations}"
        cmd_help = "Commands: draw | auto | move <waste|1-7> <1-7|f1-f4> | new"

    tableau_str = "\n".join(f"{index + 1}: {pile}" for index, pile in enumerate(columns))
    return f"{header}\n{tableau_str}\n{cmd_help}"


def _solitaire_auto_move(game):
    """Automatically move any eligible cards from waste or tableau to foundations."""
    moved_any = False
    changed = True
    while changed:
        changed = False
        if game["waste"]:
            card = game["waste"][-1]
            for pile in game["foundations"]:
                if (card[0] == "A" and not pile) or (pile and _RANKS.index(card[0]) == _RANKS.index(pile[-1][0]) + 1 and card[1] == pile[-1][1]):
                    pile.append(game["waste"].pop())
                    moved_any = True
                    changed = True
                    break
        for col_idx, col in enumerate(game["tableau"]):
            if col:
                card = col[-1]
                for pile in game["foundations"]:
                    if (card[0] == "A" and not pile) or (pile and _RANKS.index(card[0]) == _RANKS.index(pile[-1][0]) + 1 and card[1] == pile[-1][1]):
                        pile.append(col.pop())
                        game["face_up"][col_idx] = max(1, game["face_up"][col_idx] - 1) if col else 0
                        moved_any = True
                        changed = True
                        break
    return moved_any


def _new_solitaire():
    deck = [(rank, suit, color) for suit in _SUITS for rank, color in zip(_RANKS, ("R" if suit in "HD" else "B",) * 13)]
    random.shuffle(deck)
    tableau = []
    for column in range(7):
        pile = deck[:column + 1]
        del deck[:column + 1]
        tableau.append(pile)
    return {
        "stock": deck,
        "waste": [],
        "tableau": tableau,
        "face_up": [1] * 7,
        "foundations": [[] for _ in range(4)],
    }


def init(context):
    global _context
    _context = context


def register_commands(registry):
    def games(args):
        context = _context
        if not args or args[0].lower() == "help":
            return "Games: minesweeper new [rows cols mines] | minesweeper r <row> <col> | minesweeper f <row> <col> | solitaire [new|draw|auto|move <src> <dst>]"
        name = args[0].lower()
        session_id = context.session.id
        if name in ("minesweeper", "mines"):
            sub = args[1].lower() if len(args) > 1 else ""
            if not sub or sub in ("board", "show"):
                if session_id not in _mines:
                    defaults = (8, min(16, context.session.cols - 2), 10)
                    _mines[session_id] = _new_minesweeper(*defaults)
                return _mine_board(_mines[session_id])

            if sub == "new":
                defaults = (8, min(16, context.session.cols - 2), 10)
                try:
                    settings = tuple(map(int, args[2:5])) if len(args) > 2 else defaults
                    _mines[session_id] = _new_minesweeper(*settings)
                except ValueError as exc:
                    return f"Minesweeper: {exc}"
                return _mine_board(_mines[session_id])

            game = _mines.get(session_id)
            if game is None:
                return "Start a game with: games minesweeper new"

            action = "reveal"
            coords = []
            if sub in ("reveal", "r"):
                action = "reveal"
                coords = args[2:]
            elif sub in ("flag", "f"):
                action = "flag"
                coords = args[2:]
            elif sub.isdigit() and len(args) >= 3 and args[2].isdigit():
                action = "reveal"
                coords = [args[1], args[2]]
            else:
                return "Usage: games minesweeper [new | r <row> <col> | f <row> <col>]"

            if len(coords) < 2:
                return "Usage: games minesweeper r <row> <column>"
            try:
                row, column = int(coords[0]) - 1, int(coords[1]) - 1
            except ValueError:
                return "Row and column must be numbers."
            if not (0 <= row < game["rows"] and 0 <= column < game["columns"]):
                return f"Square ({coords[0]},{coords[1]}) is outside the board (rows 1-{game['rows']}, cols 1-{game['columns']})."

            cell = row * game["columns"] + column
            if action == "flag":
                if cell in game["flags"]:
                    game["flags"].remove(cell)
                elif cell not in game["shown"]:
                    game["flags"].add(cell)
            elif cell not in game["flags"]:
                _reveal_cell(game, cell)
                if game["lost"]:
                    return "*** BOOM! Mine hit. Game over. ***\n" + _mine_board(game)
                safe_count = game["rows"] * game["columns"] - len(game["mines"])
                if len(game["shown"] - game["mines"]) >= safe_count:
                    return "*** CONGRATULATIONS! You cleared all safe squares and won! ***\n" + _mine_board(game)
            return _mine_board(game)

        if name in ("solitaire", "sol"):
            if (len(args) > 1 and args[1].lower() == "new") or session_id not in _cards:
                _cards[session_id] = _new_solitaire()
                return _solitaire_status(_cards[session_id])
            game = _cards[session_id]
            sub = args[1].lower() if len(args) > 1 else ""
            if not sub or sub in ("board", "status", "show"):
                return _solitaire_status(game)
            if sub in ("draw", "d"):
                if game["stock"]:
                    game["waste"].append(game["stock"].pop())
                elif game["waste"]:
                    game["stock"] = list(reversed(game["waste"]))
                    game["waste"] = []
                return _solitaire_status(game)
            if sub in ("auto", "a"):
                moved = _solitaire_auto_move(game)
                msg = "Moved cards to foundation.\n" if moved else "No cards can be moved to foundation.\n"
                if sum(map(len, game["foundations"])) == 52:
                    return "*** CONGRATULATIONS! You won Solitaire! ***\n" + _solitaire_status(game)
                return msg + _solitaire_status(game)
            if sub in ("move", "m") and len(args) >= 4:
                source, target = args[2].lower(), args[3].lower()
                if source in ("waste", "w"):
                    source_pile = game["waste"]
                    source_column = None
                elif source.isdigit() and 1 <= int(source) <= 7:
                    source_column = int(source) - 1
                    source_pile = game["tableau"][source_column]
                else:
                    return "Source must be waste (w) or column 1-7."
                if not source_pile:
                    return "Source pile is empty."

                if target in ("f", "foundation"):
                    card = source_pile[-1]
                    found_idx = None
                    for f_idx, pile in enumerate(game["foundations"]):
                        if (card[0] == "A" and not pile) or (
                            pile
                            and _RANKS.index(card[0]) == _RANKS.index(pile[-1][0]) + 1
                            and card[1] == pile[-1][1]
                        ):
                            found_idx = f_idx
                            break
                    if found_idx is None:
                        return "That card cannot be moved to any foundation."
                    game["foundations"][found_idx].append(source_pile.pop())
                    if source_column is not None:
                        if source_pile:
                            game["face_up"][source_column] = max(
                                1, game["face_up"][source_column] - 1
                            )
                        else:
                            game["face_up"][source_column] = 0
                elif target.startswith("f") and target[1:].isdigit() and 1 <= int(target[1:]) <= 4:
                    card = source_pile[-1]
                    pile = game["foundations"][int(target[1:]) - 1]
                    legal = (card[0] == "A" and not pile) or (
                        pile
                        and _RANKS.index(card[0]) == _RANKS.index(pile[-1][0]) + 1
                        and card[1] == pile[-1][1]
                    )
                    if not legal:
                        return "That card cannot be moved to the foundation."
                    pile.append(source_pile.pop())
                    if source_column is not None:
                        if source_pile:
                            game["face_up"][source_column] = max(
                                1, game["face_up"][source_column] - 1
                            )
                        else:
                            game["face_up"][source_column] = 0
                elif target.isdigit() and 1 <= int(target) <= 7:
                    target_column = int(target) - 1
                    pile = game["tableau"][target_column]
                    cards_to_move = None
                    if source_column is not None:
                        face_up_count = game["face_up"][source_column]
                        face_up_cards = source_pile[-face_up_count:] if face_up_count > 0 else []
                        for start_idx in range(len(face_up_cards)):
                            cand = face_up_cards[start_idx]
                            legal = (cand[0] == "K" and not pile) or (
                                pile
                                and cand[2] != pile[-1][2]
                                and _RANKS.index(cand[0]) == _RANKS.index(pile[-1][0]) - 1
                            )
                            if legal:
                                cut_idx = len(source_pile) - len(face_up_cards) + start_idx
                                cards_to_move = source_pile[cut_idx:]
                                del source_pile[cut_idx:]
                                break
                    if cards_to_move is None:
                        card = source_pile[-1]
                        legal = (card[0] == "K" and not pile) or (
                            pile
                            and card[2] != pile[-1][2]
                            and _RANKS.index(card[0]) == _RANKS.index(pile[-1][0]) - 1
                        )
                        if not legal:
                            return "That card cannot be placed there."
                        cards_to_move = [source_pile.pop()]

                    pile.extend(cards_to_move)
                    game["face_up"][target_column] += len(cards_to_move)
                    if source_column is not None:
                        if source_pile:
                            game["face_up"][source_column] = max(
                                1, game["face_up"][source_column] - len(cards_to_move)
                            )
                        else:
                            game["face_up"][source_column] = 0
                else:
                    return "Destination must be column 1-7 or foundation f1-f4."

                if sum(map(len, game["foundations"])) == 52:
                    return "All cards moved to the foundations. You win!\n" + _solitaire_status(game)
                return _solitaire_status(game)
            return "Usage: games solitaire [new|draw|auto|move <source> <destination>]"
        return "Choose minesweeper or solitaire."
    registry.register_command("games", games)
    registry.register_command("minesweeper", lambda args: games(["minesweeper", *args]))
    registry.register_command("mines", lambda args: games(["minesweeper", *args]))
    registry.register_command("solitaire", lambda args: games(["solitaire", *args]))


def register_menu(menu):
    menu.append(("games", "Games"))


def handle_event(event):
    return None
