import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from backend.auth import cli
from backend.database.init_db import init_db


@pytest.fixture(autouse=True)
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "cli.db")
    with patch("backend.database.db_layer.DB_PATH", db_path), \
         patch("backend.database.init_db.DB_PATH", db_path), \
         patch("backend.database.db_wrapper.DB_PATH", db_path), \
         patch("backend.config.ADMIN_EMAIL", ""):
        yield
    shutil.rmtree(tmp_dir)


def test_add_then_list(capsys):
    assert cli.main(["add", "Alice@X.io"]) == 0
    assert cli.main(["add", "boss@x.io", "--role", "admin"]) == 0
    capsys.readouterr()
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["alice@x.io\tuser\tactive", "boss@x.io\tadmin\tactive"]


def test_add_duplicate_fails(capsys):
    assert cli.main(["add", "a@x.io"]) == 0
    assert cli.main(["add", "A@x.io"]) == 1
    assert "already exists" in capsys.readouterr().err


@pytest.mark.parametrize("email", ["nope", "a b@x.io", "@x.io", "a@"])
def test_add_invalid_email_fails(capsys, email):
    assert cli.main(["add", email]) == 1
    assert "Invalid email" in capsys.readouterr().err


def test_deactivate(capsys):
    cli.main(["add", "a@x.io"])
    assert cli.main(["deactivate", "A@x.io"]) == 0
    capsys.readouterr()
    cli.main(["list"])
    assert capsys.readouterr().out.strip() == "a@x.io\tuser\tinactive"


def test_deactivate_unknown_fails(capsys):
    assert cli.main(["deactivate", "ghost@x.io"]) == 1
    assert "No such user" in capsys.readouterr().err


def test_deactivate_admin_email_is_refused(capsys):
    with patch("backend.config.ADMIN_EMAIL", "boss@x.io"):
        assert cli.main(["deactivate", "BOSS@x.io"]) == 1  # init_db() seeds the admin
    assert "ADMIN_EMAIL" in capsys.readouterr().err
    cli.main(["list"])
    assert "boss@x.io\tadmin\tactive" in capsys.readouterr().out


def test_deactivate_empty_email_with_no_admin_email_is_not_a_refusal(capsys):
    assert cli.main(["deactivate", ""]) == 1
    assert "ADMIN_EMAIL" not in capsys.readouterr().err


def test_add_and_deactivate_are_logged(capsys):
    with patch("backend.auth.cli.log_event") as mock_log:
        cli.main(["add", "a@x.io", "--role", "admin"])
        cli.main(["deactivate", "a@x.io"])
        cli.main(["deactivate", "ghost@x.io"])
    assert [c.args for c in mock_log.call_args_list] == [
        ("user_added", {"email": "a@x.io", "role": "admin"}),
        ("user_deactivated", {"email": "a@x.io"}),
    ]


def test_list_empty(capsys):
    assert cli.main(["list"]) == 0
    assert capsys.readouterr().out == ""


def test_requires_a_command():
    with pytest.raises(SystemExit):
        cli.main([])
