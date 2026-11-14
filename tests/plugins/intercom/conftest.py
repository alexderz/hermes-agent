"""The intercom plugin source for the owner E2E (``test_e2e_owner.py``).

The plugin is installed from the checkout named by ``--intercom-src`` when one is given: that is how
a plugin change is proved before it is pulled into ``plugins/intercom``. Without the option, from
``plugins/intercom`` once it is vendored. With neither the E2E skips with that reason
(``--fail-on-skip`` turns the skip into a failure). No environment variable is read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

VENDORED = Path(__file__).resolve().parents[3] / "plugins" / "intercom"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--intercom-src", default=None, metavar="PATH",
                     help="An intercom checkout to install instead of the vendored plugins/intercom.")


@pytest.fixture(scope="session")
def intercom_src(request: pytest.FixtureRequest) -> Path:
    given = request.config.getoption("--intercom-src", default=None)
    if given:
        src = Path(given).expanduser().resolve()
        if not (src / "plugin.yaml").is_file():
            pytest.fail(f"--intercom-src is not an intercom checkout (no plugin.yaml): {src}")
        return src
    if (VENDORED / "plugin.yaml").is_file():
        return VENDORED
    pytest.skip("intercom is not vendored at plugins/intercom and no --intercom-src was given")
