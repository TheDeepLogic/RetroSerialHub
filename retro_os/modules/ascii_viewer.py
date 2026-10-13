"""Optional image-to-ASCII renderer for terminal-sized previews."""

import pathlib

_context = None
_RAMP = " .:-=+*#%@"


def init(context):
    global _context
    _context = context


def register_commands(registry):
    context = _context

    def preview(args):
        if not args:
            return "Usage: ascii <image_path>"
        raw_target = " ".join(args).strip().strip('"').strip("'")
        path = pathlib.Path(raw_target).expanduser()
        if not path.is_file():
            # Check relative to files directory if available
            files_dir = getattr(context, "fs", {}).get("files")
            if files_dir and (pathlib.Path(files_dir) / raw_target).is_file():
                path = pathlib.Path(files_dir) / raw_target
            else:
                return f"Image file not found: {raw_target}"
        try:
            from PIL import Image
        except ImportError:
            return "Image preview requires the optional 'Pillow' package. Install with 'pip install Pillow'."
        try:
            cols = getattr(context.session, "cols", 80) or 80
            # Use cols - 1 so terminal auto-wrap does not trigger before \r\n,
            # which causes alternating blank lines on retro hardware / terminal emulators.
            width = max(1, cols - 1)
            if len(args) >= 2 and args[-1].isdigit():
                try:
                    width = max(1, int(args[-1]))
                except Exception:
                    pass

            image = Image.open(path).convert("L")
            height = max(1, round(image.height * width / image.width * 0.45))
            image = image.resize((width, height))
            pixels = image.load()
            return "\n".join(
                "".join(_RAMP[pixels[x, y] * (len(_RAMP) - 1) // 255] for x in range(width))
                for y in range(height)
            )
        except Exception as exc:
            return f"Failed to render image: {exc}"

    registry.register_command("ascii", preview)
    registry.register_command("ascii_viewer", preview)


def register_menu(menu):
    menu.append(("ascii_viewer", "ASCII image viewer"))


def handle_event(event):
    return None
