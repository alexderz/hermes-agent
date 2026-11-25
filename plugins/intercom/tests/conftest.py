"""Make the intercom plugin's flat module layout importable under pytest.

The plugin's modules (``frame``, ``route``, ``peers``, …) are imported as top-level names, which
works when the tests are run from this directory as ``unittest`` modules. A repo-wide
``scripts/run_tests.sh`` run collects from the checkout root instead, so this file (the only
place pytest adds to ``sys.path`` for the suite) puts the plugin directory there too.
"""

import sys
from pathlib import Path

plugin = Path(__file__).resolve().parent.parent
if str(plugin) not in sys.path:
    sys.path.insert(0, str(plugin))
