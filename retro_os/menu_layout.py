"""Small presentation helpers shared by terminal tool screens."""


def spaced_result(tool, result):
    """Separate a command's usage line from its explanatory paragraph."""
    text = str(result)
    usage, separator, description = text.partition('\n')
    if separator and usage.casefold().startswith(tool.casefold() + ' ') and description and not description.startswith('\n'):
        return usage + '\n\n' + description
    return text
