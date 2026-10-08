from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_single_head_includes_report_and_auth_branches():
    # Runs without a database: catches merged branches that break `upgrade head`.
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["20261008_11"]
    revisions = {revision.revision for revision in scripts.walk_revisions()}
    assert {"20261006_08", "20261007_08", "20261007_09", "20261007_10"} <= revisions
