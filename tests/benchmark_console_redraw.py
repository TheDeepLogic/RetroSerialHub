"""Measure console output traffic. Run: python -m tests.benchmark_console_redraw."""

import io, json, os, time
from types import SimpleNamespace
from unittest.mock import patch
from rsh_console import ConsoleDashboard

def dashboard():
    profiles = {name: {"serial_port": f"COM{i+1}", "serial_status": "OPEN",
                      "baud": 19200, "tcp_port": 6400+i, "tcp_status": "LISTENING",
                      "endpoint": f"192.168.7.33:{6400+i}"}
                for i, name in enumerate(("APPLE2", "IBM", "C64", "TRS80"))}
    value = ConsoleDashboard(profiles)
    value._color = True
    value.set_host_terminal(SimpleNamespace(secret_input=False, _rsh_columns=80, _rsh_rows=24))
    for i in range(30):
        value.append_host_output(f"Output row {i}\n")
    value.append_host_output("cli> ")
    return value

def run_benchmark():
    output = io.StringIO()
    clock = ["2026-10-26 12:00:00"]
    with patch("rsh_console.sys.stdout", output), patch("shutil.get_terminal_size",
            return_value=os.terminal_size((150, 40))), patch("rsh_console.time.strftime",
            side_effect=lambda *args: clock[0]):
        value = dashboard()
        value._draw_frame()
        results = {}
        def measure(name, action):
            output.seek(0)
            output.truncate()
            start = time.perf_counter()
            action()
            elapsed = (time.perf_counter() - start)*1000
            data = output.getvalue()
            results[name] = {"bytes": len(data.encode("utf-8")), "row_erases": data.count("\x1b[2K"),
                             "elapsed_ms": round(elapsed, 2)}
        measure("initial_paint", lambda: dashboard()._draw_frame())
        measure("100_idle_refreshes", lambda: [value._draw_frame() for _ in range(100)])
        def typing():
            for char in "calc 123456789 + 987654321":
                value._host_command += char
                value._draw_frame()
        measure("26_typing_refreshes", typing)
        def tick():
            clock[0] = "2026-10-26 12:00:01"
            value._draw_frame()
        measure("clock_tick", tick)
        def status():
            value.profiles["APPLE2"]["serial_status"] = "MISSING"
            value._draw_frame()
        measure("status_change", status)

    return results


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2))
