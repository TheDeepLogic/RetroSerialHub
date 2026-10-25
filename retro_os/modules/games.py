"""Session-scoped text-mode games for Retro Serial Hub."""

import random
import math

_context = None
_mines = {}
_cards = {}
_wumpus_games = {}
_lander_games = {}
_blackjack_games = {}
_mastermind_games = {}
_word_guess_games = {}
_trek_games = {}
_SUITS = ("S", "H", "D", "C")
_RANKS = "A23456789TJQK"
_WORD_GUESS_WORDS = (
    "apple", "badge", "beach", "brain", "brick", "cabin", "cable", "candy",
    "chair", "charm", "chess", "cloud", "crane", "dance", "dream", "earth",
    "flame", "giant", "grape", "green", "house", "light", "magic", "maple",
    "metal", "money", "mouse", "music", "ocean", "piano", "plant", "radio",
    "river", "robot", "round", "scale", "sheep", "shore", "smile", "sound",
    "spare", "spoon", "stone", "storm", "table", "tiger", "train", "vapor",
    "water", "whale", "world", "zebra",
)


def _new_trek_game():
    quadrants = {}
    for qy in range(8):
        for qx in range(8):
            quadrants[(qy, qx)] = {"klingons": [], "base": None, "stars": []}

    def free_sector(quadrant):
        occupied = {(k["y"], k["x"]) for k in quadrant["klingons"]} | set(quadrant["stars"])
        if quadrant["base"] is not None:
            occupied.add(quadrant["base"])
        choices = [(y, x) for y in range(8) for x in range(8) if (y, x) not in occupied]
        return random.choice(choices)

    klingon_count = random.randint(16, 24)
    base_count = 2
    for _ in range(klingon_count):
        quadrant = random.choice(list(quadrants.values()))
        y, x = free_sector(quadrant)
        quadrant["klingons"].append({"y": y, "x": x, "hull": random.randint(250, 400)})
    for _ in range(base_count):
        quadrant = random.choice(list(quadrants.values()))
        while quadrant["base"] is not None:
            quadrant = random.choice(list(quadrants.values()))
        quadrant["base"] = free_sector(quadrant)
    for quadrant in quadrants.values():
        for _ in range(random.randint(1, 4)):
            quadrant["stars"].append(free_sector(quadrant))

    game = {
        "quadrants": quadrants,
        "qy": 3, "qx": 3, "sy": 3, "sx": 3,
        "klingons": klingon_count, "bases": base_count,
        "energy": 5000, "shields": 1000, "torpedoes": 10,
        "stardate": 0.0, "deadline": 30.0, "over": False,
    }
    # Keep the Enterprise's starting sector free of objects.
    quadrant = quadrants[(game["qy"], game["qx"])]
    quadrant["klingons"] = [k for k in quadrant["klingons"] if (k["y"], k["x"]) != (game["sy"], game["sx"])]
    if quadrant["base"] == (game["sy"], game["sx"]):
        quadrant["base"] = None
        game["bases"] -= 1
    quadrant["stars"] = [p for p in quadrant["stars"] if p != (game["sy"], game["sx"])]
    game["klingons"] = sum(len(q["klingons"]) for q in quadrants.values())
    return game


def _trek_quadrant(game):
    return game["quadrants"][(game["qy"], game["qx"])]


def _trek_sector_scan(game):
    quadrant = _trek_quadrant(game)
    grid = [["." for _ in range(8)] for _ in range(8)]
    for y, x in quadrant["stars"]:
        grid[y][x] = "*"
    if quadrant["base"]:
        y, x = quadrant["base"]
        grid[y][x] = "B"
    for klingon in quadrant["klingons"]:
        grid[klingon["y"]][klingon["x"]] = "K"
    grid[game["sy"]][game["sx"]] = "E"
    lines = [f"QUADRANT {game['qy'] + 1}-{game['qx'] + 1}  (E=Enterprise K=Klingon B=base *=star)", "   1 2 3 4 5 6 7 8"]
    lines.extend(f"{y + 1:2d} " + " ".join(row) for y, row in enumerate(grid))
    lines.append(f"Klingons: {len(quadrant['klingons'])}  Starbases: {int(quadrant['base'] is not None)}  Stars: {len(quadrant['stars'])}")
    return "\n".join(lines)


def _trek_status(game, notice=""):
    lines = [
        f"STAR TREK  Stardate {3424 + game['stardate']:.1f}/{3424 + game['deadline']:.0f}",
        f"Quadrant {game['qy'] + 1}-{game['qx'] + 1} Sector {game['sy'] + 1}-{game['sx'] + 1}",
        f"Klingons: {game['klingons']}  Starbases: {game['bases']}  Torpedoes: {game['torpedoes']}",
        f"Energy: {game['energy']}  Shields: {game['shields']}",
    ]
    if notice:
        lines.append(notice)
    lines.append("Commands: scan, long, move <course 0-359> <warp 1-8>, phasers <energy>,")
    lines.append("          torpedo <course>, shield <energy>, status, new, quit")
    return "\n".join(lines)


def _trek_enemy_turn(game):
    quadrant = _trek_quadrant(game)
    attacks = len(quadrant["klingons"])
    if not attacks:
        return ""
    total_hit = sum(random.randint(80, 220) for _ in range(attacks))
    absorbed = min(game["shields"], total_hit)
    game["shields"] -= absorbed
    spill = total_hit - absorbed
    game["energy"] = max(0, game["energy"] - spill)
    if game["energy"] <= 0:
        game["over"] = True
        return f"Klingons hit for {total_hit} units. Shields are down; the Enterprise is destroyed!"
    return f"Klingons hit for {total_hit} units ({absorbed} absorbed by shields)."


def _trek_command(game, args):
    if not args or args[0].lower() in ("status", "i", "show"):
        return _trek_status(game) + "\n\n" + _trek_sector_scan(game)
    command = args[0].lower()
    if command in ("scan", "srs"):
        return _trek_sector_scan(game)
    if command in ("long", "lrs", "computer"):
        y_range = range(max(0, game["qy"] - 1), min(8, game["qy"] + 2))
        x_range = range(max(0, game["qx"] - 1), min(8, game["qx"] + 2))
        lines = ["LONG RANGE SCAN  (Klingons / Starbases / Stars)",
                 "       " + "  ".join(f"Q{game['qy'] + 1}-{x + 1}" for x in x_range)]
        for y in y_range:
            cells = []
            for x in x_range:
                quadrant = game["quadrants"][(y, x)]
                cells.append(f"{len(quadrant['klingons']):1d}/{int(quadrant['base'] is not None):1d}/{len(quadrant['stars']):1d}")
            lines.append(f"Q{y + 1}: " + "  ".join(cells))
        lines.append("Quadrant entries are K/B/*; scan shows exact sector positions.")
        return "\n".join(lines)
    if command in ("move", "warp", "nav") and len(args) == 3:
        try:
            course, warp = float(args[1]), int(args[2])
        except ValueError:
            return "Use: move <course 0-359> <warp 1-8>"
        if not math.isfinite(course) or not 0 <= course < 360:
            return "Course must be from 0 to 359 degrees."
        if not 1 <= warp <= 8:
            return "Warp factor must be from 1 to 8."
        energy_cost = int(10 * warp * warp)
        if energy_cost > game["energy"]:
            return f"Insufficient energy; movement requires {energy_cost}."
        radians = math.radians(course)
        dx, dy = math.sin(radians), -math.cos(radians)
        steps = max(1, int(round(warp * 2)))
        notices = []
        px, py = float(game["sx"]), float(game["sy"])
        quadrant = _trek_quadrant(game)
        occupied = {(k["y"], k["x"]) for k in quadrant["klingons"]} | set(quadrant["stars"])
        if quadrant["base"]:
            occupied.add(quadrant["base"])
        for _ in range(steps):
            px += dx
            py += dy
            nx, ny = int(round(px)), int(round(py))
            qx, qy = game["qx"], game["qy"]
            if nx < 0:
                qx, px = qx - 1, px + 8
                nx = int(round(px))
            elif nx > 7:
                qx, px = qx + 1, px - 8
                nx = int(round(px))
            if ny < 0:
                qy, py = qy - 1, py + 8
                ny = int(round(py))
            elif ny > 7:
                qy, py = qy + 1, py - 8
                ny = int(round(py))
            if not (0 <= qx < 8 and 0 <= qy < 8):
                notices.append("Galactic boundary reached.")
                break
            next_quadrant = game["quadrants"][(qy, qx)]
            if next_quadrant is not quadrant:
                next_occupied = {(k["y"], k["x"]) for k in next_quadrant["klingons"]} | set(next_quadrant["stars"])
                if next_quadrant["base"]:
                    next_occupied.add(next_quadrant["base"])
            else:
                next_occupied = occupied
            if (ny, nx) in next_occupied:
                notices.append("Course blocked by an object in that sector.")
                break
            if next_quadrant is not quadrant:
                game["qx"], game["qy"] = qx, qy
                quadrant, occupied = next_quadrant, next_occupied
            game["sx"], game["sy"] = nx, ny
        game["energy"] -= energy_cost
        game["stardate"] += warp / 4
        if quadrant["base"] and abs(quadrant["base"][0] - game["sy"]) <= 1 and abs(quadrant["base"][1] - game["sx"]) <= 1:
            game["energy"], game["shields"], game["torpedoes"] = 5000, 1000, 10
            notices.append("Docked at starbase; energy, shields, and torpedoes replenished.")
        if game["stardate"] >= game["deadline"] and game["klingons"]:
            game["over"] = True
            notices.append("Mission time expired. The Federation has fallen.")
        enemy_notice = _trek_enemy_turn(game) if not game["over"] else ""
        if enemy_notice:
            notices.append(enemy_notice)
        return _trek_status(game, " ".join(notices)) + "\n\n" + _trek_sector_scan(game)
    if command in ("phasers", "phaser", "p") and len(args) == 2:
        try:
            amount = int(args[1])
        except ValueError:
            return "Use: phasers <energy units>"
        quadrant = _trek_quadrant(game)
        klingons = quadrant["klingons"]
        if not klingons:
            return "No Klingons in this quadrant."
        if not 1 <= amount <= game["energy"]:
            return f"Choose an energy level from 1 to {game['energy']}."
        game["energy"] -= amount
        hits = []
        for klingon in list(klingons):
            distance = math.hypot(klingon["x"] - game["sx"], klingon["y"] - game["sy"])
            damage = amount / len(klingons) * random.uniform(0.65, 1.35) / (1 + distance * 0.12)
            klingon["hull"] -= int(damage)
            if klingon["hull"] <= 0:
                klingons.remove(klingon)
                game["klingons"] -= 1
                hits.append("Klingon destroyed")
            else:
                hits.append(f"Klingon damaged ({klingon['hull']} hull left)")
        game["stardate"] += 0.2
        if game["klingons"] == 0:
            game["over"] = True
            hits.append("VICTORY! The Federation is clear of Klingons.")
        elif game["stardate"] >= game["deadline"]:
            game["over"] = True
            hits.append("Mission time expired. The Federation has fallen.")
        else:
            enemy_notice = _trek_enemy_turn(game)
            if enemy_notice:
                hits.append(enemy_notice)
        return _trek_status(game, "; ".join(hits)) + "\n\n" + _trek_sector_scan(game)
    if command in ("torpedo", "torpedoes", "t") and len(args) == 2:
        try:
            course_value = float(args[1])
        except ValueError:
            return "Use: torpedo <course 0-359>"
        if not math.isfinite(course_value) or not 0 <= course_value < 360:
            return "Course must be from 0 to 359 degrees."
        course = math.radians(course_value)
        if game["torpedoes"] <= 0:
            return "No photon torpedoes remain."
        game["torpedoes"] -= 1
        dx, dy = math.sin(course), -math.cos(course)
        quadrant = _trek_quadrant(game)
        result = "Photon torpedo missed."
        seen = set()
        for distance in range(1, 12):
            x = int(round(game["sx"] + dx * distance))
            y = int(round(game["sy"] + dy * distance))
            if not (0 <= x < 8 and 0 <= y < 8) or (x, y) in seen:
                if not (0 <= x < 8 and 0 <= y < 8):
                    break
                continue
            seen.add((x, y))
            target = next((k for k in quadrant["klingons"] if (k["y"], k["x"]) == (y, x)), None)
            if target:
                quadrant["klingons"].remove(target)
                game["klingons"] -= 1
                result = "Klingon destroyed by photon torpedo!"
                break
            if (y, x) in quadrant["stars"] or quadrant["base"] == (y, x):
                result = "Photon torpedo detonated against an obstruction."
                break
        game["stardate"] += 0.2
        if game["klingons"] == 0:
            game["over"] = True
            result += " VICTORY! The Federation is clear of Klingons."
        elif game["stardate"] >= game["deadline"]:
            game["over"] = True
            result += " Mission time expired. The Federation has fallen."
        else:
            enemy_notice = _trek_enemy_turn(game)
            if enemy_notice:
                result += " " + enemy_notice
        return _trek_status(game, result) + "\n\n" + _trek_sector_scan(game)
    if command in ("shield", "shields") and len(args) == 2:
        try:
            amount = int(args[1])
        except ValueError:
            return "Use: shield <energy units to transfer>"
        if amount < 0 or amount > game["energy"]:
            return f"Choose an energy transfer from 0 to {game['energy']}."
        game["energy"] -= amount
        game["shields"] += amount
        return _trek_status(game, f"Transferred {amount} energy units to shields.")
    return "Use: scan | long | move <course> <warp> | phasers <energy> | torpedo <course> | shield <energy> | status | new | quit"

# The classic dodecahedral cave: every room connects to three neighbors.
_CAVE = (
    (2, 5, 8), (1, 3, 10), (2, 4, 12), (3, 5, 14), (1, 4, 6),
    (5, 7, 15), (6, 8, 17), (1, 7, 9), (8, 10, 18), (2, 9, 11),
    (10, 12, 19), (3, 11, 13), (12, 14, 20), (4, 13, 15), (6, 14, 16),
    (15, 17, 20), (7, 16, 18), (9, 17, 19), (11, 18, 20), (13, 16, 19),
)


def _new_wumpus():
    rooms = random.sample(range(1, 21), 6)
    return {
        "player": rooms[0], "wumpus": rooms[1],
        "pits": set(rooms[2:4]), "bats": set(rooms[4:6]),
        "arrows": 3, "over": False,
    }


def _new_lander():
    return {"altitude": 100, "velocity": 5.0, "fuel": 30, "turn": 0, "landed": False, "over": False}


def _lander_status(game, notice=""):
    bars = max(0, min(20, int(game["altitude"] / 5)))
    lines = ["LUNAR LANDER", f"ALTITUDE {max(0, game['altitude']):3d} m | SPEED {game['velocity']:4.1f} m/s | FUEL {game['fuel']:2d}",
             "MOON  " + "=" * bars + "v" + " " * max(0, 19 - bars)]
    if notice:
        lines.append(notice)
    lines.append("Burn 0-4 units per turn (0=coast); land at <= 2 m/s. B <0-4>=burn, I=status, N=new, Q=quit")
    return "\n".join(lines)


def _new_blackjack():
    deck = [(rank, suit) for suit in _SUITS for rank in _RANKS]
    random.shuffle(deck)
    game = {"deck": deck, "player": [deck.pop(), deck.pop()], "dealer": [deck.pop(), deck.pop()], "over": False}
    return game


def _hand_value(hand):
    total = sum(11 if rank == "A" else 10 if rank in "TJQK" else int(rank) for rank, _ in hand)
    aces = sum(rank == "A" for rank, _ in hand)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _blackjack_status(game, reveal_dealer=False, notice=""):
    dealer = game["dealer"] if reveal_dealer else game["dealer"][:1]
    lines = ["BLACKJACK", "You: " + " ".join(_card_text(card) for card in game["player"]) + f"  ({_hand_value(game['player'])})",
             "Dealer: " + " ".join(_card_text(card) for card in dealer) + (f"  ({_hand_value(game['dealer'])})" if reveal_dealer else "  ??")]
    if notice:
        lines.append(notice)
    if not game["over"]:
        lines.append("H=hit, S=stand, N=new, Q=quit")
    return "\n".join(lines)


def _new_mastermind():
    return {"code": random.sample("123456", 4), "guesses": [], "over": False}


def _mastermind_status(game, notice=""):
    lines = ["MASTERMIND  Choose four different digits from 1-6.", "Guesses: %d/10" % len(game["guesses"])]
    lines.extend(f"{guess}  {exact} exact, {near} misplaced" for guess, exact, near in game["guesses"])
    if notice:
        lines.append(notice)
    if not game["over"]:
        lines.append("G <four digits>=guess, N=new, Q=quit")
    return "\n".join(lines)


def _new_word_guess():
    return {"word": random.choice(_WORD_GUESS_WORDS), "guesses": [], "over": False}


def _word_guess_feedback(answer, guess):
    marks = ["."] * len(answer)
    remaining = list(answer)
    for index, letter in enumerate(guess):
        if letter == answer[index]:
            marks[index] = "G"
            remaining[index] = None
    for index, letter in enumerate(guess):
        if marks[index] == "." and letter in remaining:
            marks[index] = "Y"
            remaining[remaining.index(letter)] = None
    return " ".join(marks)


def _word_guess_status(game, notice=""):
    lines = ["WORD GUESS  Find the hidden 5-letter word in 6 guesses."]
    lines.extend(
        f"{index}. {guess.upper()}  {_word_guess_feedback(game['word'], guess)}"
        for index, guess in enumerate(game["guesses"], 1)
    )
    if notice:
        lines.append(notice)
    if not game["over"]:
        lines.append("G=right spot  Y=elsewhere  .=not in word")
        lines.append("Enter a 5-letter guess, N=new, Q=quit")
    return "\n".join(lines)


def _wumpus_status(game, notice=""):
    room = game["player"]
    nearby = _CAVE[room - 1]
    clues = []
    if game["wumpus"] in nearby:
        clues.append("I smell a Wumpus!")
    if any(n in game["pits"] for n in nearby):
        clues.append("I feel a draft.")
    if any(n in game["bats"] for n in nearby):
        clues.append("Bats nearby!")
    lines = [f"HUNT THE WUMPUS  Room {room}  Arrows: {game['arrows']}",
             f"Tunnels lead to: {nearby[0]}, {nearby[1]}, {nearby[2]}"]
    lines.extend(clues or ["The cave is quiet..."])
    if notice:
        lines.append(notice)
    lines.append("Move: m <room> | Shoot: s <room>[,<room>,<room>] | quit")
    return "\n".join(lines)


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
    context = _context
    def games(args):
        if not args or args[0].lower() == "help":
            return "Games: minesweeper [new|r row col|f row col] | solitaire [new|draw|auto|move src dst] | wumpus [new|m room|s room,...] | lander [new|burn 0-4] | blackjack [new|hit|stand] | mastermind [new|guess 1234] | wordguess [new|<5-letter guess>] | trek [new|scan|long|move|phasers|torpedo|shield|quit]"
        name = args[0].lower()
        session_id = context.session.id
        if name in ("trek", "startrek", "star-trek", "star_trek"):
            sub = args[1].lower() if len(args) > 1 else ""
            if sub in ("n", "new", "start") or session_id not in _trek_games:
                _trek_games[session_id] = _new_trek_game()
                return _trek_status(_trek_games[session_id], "Captain, your mission begins.") + "\n\n" + _trek_sector_scan(_trek_games[session_id])
            game = _trek_games[session_id]
            if sub in ("q", "quit", "exit"):
                del _trek_games[session_id]
                return "Star Trek mission ended."
            if game["over"]:
                return "Mission over. Start another with: games trek new"
            return _trek_command(game, args[1:])
        if name in ("wordguess", "word", "wordle"):
            sub = args[1].lower() if len(args) > 1 else ""
            if sub in ("n", "new", "start") or session_id not in _word_guess_games:
                _word_guess_games[session_id] = _new_word_guess()
                if sub in ("", "n", "new", "start"):
                    return _word_guess_status(_word_guess_games[session_id], "New word selected.")
            game = _word_guess_games[session_id]
            if sub in ("q", "quit", "exit"):
                del _word_guess_games[session_id]
                return "Word Guess session ended."
            if game["over"]:
                return "Game over. Start another with: games wordguess new"
            guess = args[2] if sub in ("g", "guess") and len(args) == 3 else sub
            if len(guess) != 5 or not guess.isalpha():
                return "Enter exactly five letters, for example: games wordguess crane"
            guess = guess.lower()
            game["guesses"].append(guess)
            if guess == game["word"]:
                game["over"] = True
                return _word_guess_status(game, f"YOU WIN! Solved in {len(game['guesses'])} guesses.")
            if len(game["guesses"]) >= 6:
                game["over"] = True
                return _word_guess_status(game, f"No guesses left. The word was {game['word'].upper()}.")
            return _word_guess_status(game)
        if name in ("blackjack", "21"):
            sub = args[1].lower() if len(args) > 1 else ""
            if sub in ("n", "new", "start") or session_id not in _blackjack_games:
                game = _new_blackjack()
                _blackjack_games[session_id] = game
                if _hand_value(game["player"]) == 21:
                    game["over"] = True
                    return _blackjack_status(game, True, "BLACKJACK! You win!")
                return _blackjack_status(game)
            game = _blackjack_games[session_id]
            if sub in ("q", "quit", "exit"):
                del _blackjack_games[session_id]
                return "Hand ended."
            if game["over"]:
                return "Hand is over. Start another with: games blackjack new"
            if sub in ("h", "hit"):
                if not game["deck"]:
                    return _blackjack_status(game, notice="No cards remain. Stand to end the hand.")
                game["player"].append(game["deck"].pop())
                if _hand_value(game["player"]) > 21:
                    game["over"] = True
                    return _blackjack_status(game, True, "Bust! Dealer wins.")
                return _blackjack_status(game)
            if sub in ("s", "stand"):
                while _hand_value(game["dealer"]) < 17 and game["deck"]:
                    game["dealer"].append(game["deck"].pop())
                game["over"] = True
                player_total, dealer_total = _hand_value(game["player"]), _hand_value(game["dealer"])
                outcome = "You win!" if dealer_total > 21 or player_total > dealer_total else "Push." if player_total == dealer_total else "Dealer wins."
                return _blackjack_status(game, True, outcome)
            if sub in ("", "i", "status", "show"):
                return _blackjack_status(game)
            return "Usage: games blackjack [H|S|N|Q] (hit|stand|new|quit)"
        if name in ("mastermind", "codebreaker"):
            sub = args[1].lower() if len(args) > 1 else ""
            if sub in ("n", "new", "start") or session_id not in _mastermind_games:
                _mastermind_games[session_id] = _new_mastermind()
                return _mastermind_status(_mastermind_games[session_id], "Secret code set. Crack it in 10 guesses!")
            game = _mastermind_games[session_id]
            if sub in ("q", "quit", "exit"):
                del _mastermind_games[session_id]
                return "Codebreaker session ended."
            if game["over"]:
                return "Puzzle is over. Start another with: games mastermind new"
            if sub in ("guess", "g") and len(args) == 3:
                guess = args[2]
                if len(guess) != 4 or any(digit not in "123456" for digit in guess) or len(set(guess)) != 4:
                    return "Enter four different digits from 1 to 6, for example: guess 1352"
                exact = sum(a == b for a, b in zip(guess, game["code"]))
                near = len(set(guess) & set(game["code"])) - exact
                game["guesses"].append((guess, exact, near))
                if exact == 4:
                    game["over"] = True
                    return _mastermind_status(game, f"YOU WIN! Code cracked in {len(game['guesses'])} guesses.")
                if len(game["guesses"]) >= 10:
                    game["over"] = True
                    return _mastermind_status(game, "Out of guesses. The code was " + "".join(game["code"]) + ".")
                return _mastermind_status(game)
            if sub in ("", "i", "status", "show"):
                return _mastermind_status(game)
            return "Usage: games mastermind [G <four-digits>|N|I|Q]"
        if name in ("wumpus", "wump"):
            sub = args[1].lower() if len(args) > 1 else ""
            if sub in ("n", "new", "start") or session_id not in _wumpus_games:
                _wumpus_games[session_id] = _new_wumpus()
                return _wumpus_status(_wumpus_games[session_id], "Find and shoot the Wumpus before it finds you!")
            game = _wumpus_games[session_id]
            if game["over"]:
                if sub in ("status", "show"):
                    return "Game over. Start another with: games wumpus new"
                return "Game over. Start another with: games wumpus new"
            if sub in ("q", "quit", "exit"):
                del _wumpus_games[session_id]
                return "Hunt ended. Start again with: games wumpus new"
            if sub in ("m", "move") and len(args) >= 3:
                try:
                    destination = int(args[2])
                except ValueError:
                    return "Room must be a number from 1 to 20."
                if destination not in _CAVE[game["player"] - 1]:
                    return f"Room {destination} is not connected to room {game['player']}. Choose: {', '.join(map(str, _CAVE[game['player'] - 1]))}."
                game["player"] = destination
                if destination in game["pits"]:
                    game["over"] = True
                    return "You fall into a bottomless pit! Game over.\n" + _wumpus_status(game)
                if destination == game["wumpus"]:
                    game["over"] = True
                    return "The Wumpus eats you! Game over.\n" + _wumpus_status(game)
                notice = ""
                if destination in game["bats"]:
                    game["player"] = random.choice([n for n in range(1, 21) if n not in game["pits"] and n not in game["bats"] and n != game["wumpus"]])
                    notice = f"Super bats carry you to room {game['player']}!"
                if random.randrange(4) == 0:
                    game["wumpus"] = random.choice((game["wumpus"], *_CAVE[game["wumpus"] - 1]))
                    if game["wumpus"] == game["player"]:
                        game["over"] = True
                        return "The Wumpus wanders into your room and eats you! Game over.\n" + _wumpus_status(game)
                return _wumpus_status(game, notice)
            if sub in ("s", "shoot") and len(args) >= 3:
                raw_path = " ".join(args[2:]).replace(",", " ").split()
                try:
                    path = [int(room) for room in raw_path]
                except ValueError:
                    return "Use room numbers, for example: games wumpus shoot 4,7,9"
                if not 1 <= len(path) <= 3 or any(room < 1 or room > 20 for room in path):
                    return "An arrow travels through 1 to 3 rooms, numbered 1 to 20."
                game["arrows"] -= 1
                arrow_room = game["player"]
                for target in path:
                    if target not in _CAVE[arrow_room - 1]:
                        target = random.choice(_CAVE[arrow_room - 1])
                    arrow_room = target
                    if arrow_room == game["wumpus"]:
                        game["over"] = True
                        return "Your arrow finds the Wumpus! YOU WIN!\n" + _wumpus_status(game)
                    if arrow_room == game["player"]:
                        game["over"] = True
                        return "Your arrow turns around and hits you! Game over.\n" + _wumpus_status(game)
                if game["arrows"] <= 0:
                    game["over"] = True
                    return "You are out of arrows. The Wumpus wins.\n" + _wumpus_status(game)
                if random.randrange(4) == 0:
                    game["wumpus"] = random.choice((game["wumpus"], *_CAVE[game["wumpus"] - 1]))
                    if game["wumpus"] == game["player"]:
                        game["over"] = True
                        return "The Wumpus hears your arrow and eats you! Game over.\n" + _wumpus_status(game)
                return _wumpus_status(game, "Missed! The Wumpus heard the arrow.")
            if sub in ("", "i", "status", "show", "board"):
                return _wumpus_status(game)
            return "Usage: games wumpus [N|M <room>|S <room>[,<room>,<room>]|Q]"
        if name in ("lander", "lunarlander"):
            sub = args[1].lower() if len(args) > 1 else ""
            if sub in ("n", "new", "start") or session_id not in _lander_games:
                _lander_games[session_id] = _new_lander()
                return _lander_status(_lander_games[session_id], "Descent initiated. Keep your landing speed under 2 m/s.")
            game = _lander_games[session_id]
            if sub in ("q", "quit", "exit"):
                del _lander_games[session_id]
                return "Flight computer disengaged."
            if game["over"]:
                return "Flight ended. Start another with: games lander new"
            if sub in ("", "i", "status", "show"):
                return _lander_status(game)
            if sub in ("b", "burn") and len(args) == 3:
                try:
                    burn = int(args[2])
                except ValueError:
                    return "Burn must be a whole number from 0 to 4."
                if not 0 <= burn <= 4:
                    return "Burn must be from 0 to 4."
                if burn > game["fuel"]:
                    return f"Only {game['fuel']} fuel units remain."
                game["fuel"] -= burn
                game["turn"] += 1
                acceleration = 1.6 - burn * 1.1
                game["altitude"] -= game["velocity"] + acceleration / 2
                game["velocity"] += acceleration
                if game["altitude"] <= 0:
                    game["altitude"] = 0
                    game["over"] = True
                    if 0 <= game["velocity"] <= 2:
                        game["landed"] = True
                        return _lander_status(game, f"Touchdown! Safe landing in {game['turn']} turns. Congratulations, pilot!")
                    return _lander_status(game, f"CRASH! Impact speed: {abs(game['velocity']):.1f} m/s. Try again with 'new'.")
                if game["fuel"] == 0 and game["velocity"] > 0:
                    return _lander_status(game, "Fuel exhausted. You are coasting toward the surface.")
                return _lander_status(game)
            return "Usage: games lander [B <0-4>|N|I|Q]"
        if name in ("minesweeper", "mines"):
            sub = args[1].lower() if len(args) > 1 else ""
            if not sub or sub in ("board", "show"):
                if session_id not in _mines:
                    defaults = (8, min(16, context.session.cols - 2), 10)
                    _mines[session_id] = _new_minesweeper(*defaults)
                return _mine_board(_mines[session_id])

            if sub in ("n", "new"):
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
            if (len(args) > 1 and args[1].lower() in ("n", "new")) or session_id not in _cards:
                _cards[session_id] = _new_solitaire()
                return _solitaire_status(_cards[session_id], context.session.cols)
            game = _cards[session_id]
            sub = args[1].lower() if len(args) > 1 else ""
            if not sub or sub in ("board", "status", "show"):
                return _solitaire_status(game, context.session.cols)
            if sub in ("draw", "d"):
                if game["stock"]:
                    game["waste"].append(game["stock"].pop())
                elif game["waste"]:
                    game["stock"] = list(reversed(game["waste"]))
                    game["waste"] = []
                return _solitaire_status(game, context.session.cols)
            if sub in ("auto", "a"):
                moved = _solitaire_auto_move(game)
                msg = "Moved cards to foundation.\n" if moved else "No cards can be moved to foundation.\n"
                if sum(map(len, game["foundations"])) == 52:
                    return "*** CONGRATULATIONS! You won Solitaire! ***\n" + _solitaire_status(game, context.session.cols)
                return msg + _solitaire_status(game, context.session.cols)
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
                    return "All cards moved to the foundations. You win!\n" + _solitaire_status(game, context.session.cols)
                return _solitaire_status(game, context.session.cols)
            return "Usage: games solitaire [new|draw|auto|move <source> <destination>]"
        return "Choose minesweeper, solitaire, wumpus, lander, blackjack, mastermind, wordguess, or trek."
    registry.register_command("games", games)
    registry.register_command("minesweeper", lambda args: games(["minesweeper", *args]))
    registry.register_command("mines", lambda args: games(["minesweeper", *args]))
    registry.register_command("solitaire", lambda args: games(["solitaire", *args]))
    registry.register_command("wumpus", lambda args: games(["wumpus", *args]))
    registry.register_command("lander", lambda args: games(["lander", *args]))
    registry.register_command("blackjack", lambda args: games(["blackjack", *args]))
    registry.register_command("mastermind", lambda args: games(["mastermind", *args]))
    registry.register_command("wordguess", lambda args: games(["wordguess", *args]))
    registry.register_command("wordle", lambda args: games(["wordguess", *args]))
    registry.register_command("trek", lambda args: games(["trek", *args]))
    registry.register_command("startrek", lambda args: games(["trek", *args]))


def register_menu(menu):
    menu.append(("games", "Games"))


def handle_event(event):
    return None
