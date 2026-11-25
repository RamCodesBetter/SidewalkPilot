"""Shared source locations for direct CLI entry points and flat module imports."""
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent
SERIES5 = TOOLS.parent
CONFIGS = TOOLS / "configs"
CATEGORIES = ("labeling", "datasets", "evaluation", "models", "review")


def activate():
    for directory in (SERIES5, TOOLS, *(TOOLS / name for name in CATEGORIES)):
        value = str(directory)
        if value not in sys.path:
            sys.path.insert(0, value)


def source_path(name):
    """Resolve one source/config filename; never guess between duplicates."""
    if not isinstance(name, str) or Path(name).name != name or "\\" in name:
        raise ValueError(f"Expected a plain source filename: {name!r}")
    locations = (SERIES5, TOOLS, CONFIGS, TOOLS / "review/assets", *(TOOLS / part for part in CATEGORIES))
    matches = [root / name for root in locations if (root / name).is_file()]
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one source file for {name!r}, found {len(matches)}")
    return matches[0]
