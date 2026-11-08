import pytest
from executor import CodeExecutor

def test_execute_python_success():
    res = CodeExecutor.execute(
        language="python",
        code="print('Hello from sandbox')"
    )
    assert res.exit_code == 0
    assert "Hello from sandbox" in res.stdout
    assert res.stderr == ""
    assert not res.timed_out

def test_execute_python_error():
    res = CodeExecutor.execute(
        language="python",
        code="raise ValueError('Intentional error')"
    )
    assert res.exit_code != 0
    assert "ValueError: Intentional error" in res.stderr
    assert not res.timed_out

def test_execute_python_timeout():
    res = CodeExecutor.execute(
        language="python",
        code="import time\ntime.sleep(2)",
        timeout=1
    )
    assert res.timed_out
    assert "timed out" in res.error

def test_execute_python_multi_file():
    files = [
        {"path": "main.py", "content": "from helpers.utils import add\nprint(add(2, 3))"},
        {"path": "helpers/__init__.py", "content": ""},
        {"path": "helpers/utils.py", "content": "def add(a, b): return a + b"}
    ]
    res = CodeExecutor.execute(
        language="python",
        files=files,
        entry_file="main.py"
    )
    assert res.exit_code == 0
    assert "5" in res.stdout

def test_execute_sqlite():
    import shutil
    if not shutil.which("sqlite3"):
        pytest.skip("sqlite3 executable not found in path")
    res = CodeExecutor.execute(
        language="sql",
        code="CREATE TABLE test (val TEXT);\nINSERT INTO test VALUES ('hello');\nSELECT * FROM test;",
        sql_target="sqlite"
    )
    assert res.exit_code == 0
    assert "hello" in res.stdout

def test_execute_sql_mysql_is_rejected(monkeypatch):
    import os
    import executor as executor_module
    # Pin the sandbox id so the test can check that execute() removes that directory.
    monkeypatch.setattr(executor_module.uuid, "uuid4", lambda: type("U", (), {"hex": "mysqlreject"})())
    res = CodeExecutor.execute(
        language="sql",
        code="SELECT 1;",
        sql_target="mysql"
    )
    assert res.exit_code == 1
    assert "MySQL is not available" in res.error
    assert not res.timed_out
    assert not os.path.exists("/tmp/sandbox/mysqlreject")

def test_prepare_sandbox_mysql_error_returns_sandbox_dir_for_cleanup():
    import os
    import shutil
    prep = CodeExecutor.prepare_sandbox(
        language="sql",
        code="SELECT 1;",
        sql_target="mysql"
    )
    assert "MySQL is not available" in prep["error"]
    assert os.path.isdir(prep["sandbox_dir"])
    shutil.rmtree(prep["sandbox_dir"], ignore_errors=True)

def test_execute_cpp():
    import shutil
    if not shutil.which("g++"):
        pytest.skip("g++ not found in path")
    res = CodeExecutor.execute(
        language="cpp",
        code='#include <iostream>\nint main() {\n    std::cout << "Hello from C++" << std::endl;\n    return 0;\n}'
    )
    assert res.exit_code == 0
    assert "Hello from C++" in res.stdout

