"""Small API adapter for existing interactive Retro Serial Hub features."""


def setup(module_name, context, shell):
    def activate(args):
        if args:
            return f"Usage: {module_name}"
        if context.activate_module is None:
            return f"{module_name} is available from the Retro Serial Hub menu."
        context.session.active_module = module_name
        context.activate_module(module_name)
        return f"Opening {module_name}..."

    shell.register_command(module_name, activate)


def handle(_event):
    return None
