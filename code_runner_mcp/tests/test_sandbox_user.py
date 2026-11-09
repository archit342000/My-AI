"""Uids, limits, environment and the privilege check of the code runner."""
import os

import pytest

import sandbox_user as su


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.delenv("CODE_RUNNER_ALLOW_UNPRIVILEGED", raising=False)


def test_spawn_kwargs_switch_to_the_runner_or_package_uid_when_isolated(isolated):
    runner = su.spawn_kwargs("runner")
    assert runner == {"start_new_session": True, "user": 61001, "group": 61001, "extra_groups": []}
    pkg = su.spawn_kwargs("pkg")
    assert (pkg["user"], pkg["group"], pkg["extra_groups"]) == (61002, 61002, [])


def test_spawn_kwargs_do_not_switch_in_the_unprivileged_dev_mode():
    assert su.spawn_kwargs("runner") == {"start_new_session": True}
    assert su.limited(["python3", "x.py"]) == ["python3", "x.py"]


def test_limited_wraps_with_prlimit_after_the_switch_and_never_limits_address_space(isolated):
    argv = su.limited(["java", "Main"])
    assert argv[0] == "prlimit" and argv[-2:] == ["java", "Main"]
    assert f"--nproc={su.NPROC_LIMIT}" in argv and f"--nofile={su.NOFILE_LIMIT}" in argv
    assert not any(a.startswith("--as") for a in argv)


def test_run_env_puts_home_and_tmp_in_the_sandbox_and_packages_on_the_language_paths():
    env = su.run_env("/tmp/sandbox/abc")
    assert env["HOME"] == "/tmp/sandbox/abc/home" and env["TMPDIR"] == "/tmp/sandbox/abc/tmp"
    assert env["PYTHONPATH"] == "/opt/runner/python" and env["NODE_PATH"] == "/opt/runner/node/node_modules"
    assert "PIP_INDEX_URL" not in env  # the package proxy settings reach installs, not user code


def test_pkg_env_gives_pip_only_path_and_npm_a_writable_home(monkeypatch):
    monkeypatch.setenv("PIP_INDEX_URL", "http://pkg-proxy:8080/pypi/simple/")
    monkeypatch.setenv("npm_config_registry", "http://pkg-proxy:8080/npm/")
    monkeypatch.setenv("SECRET_THING", "x")
    pip, npm = su.pkg_env("pip"), su.pkg_env("npm")
    assert "HOME" not in pip and pip["PIP_INDEX_URL"].startswith("http://pkg-proxy")
    assert npm["HOME"] == "/opt/runner/pkg-home" and npm["npm_config_cache"] == "/opt/runner/pkg-home/.npm"
    assert npm["npm_config_registry"].startswith("http://pkg-proxy") and "SECRET_THING" not in npm


def test_isolated_uids_follow_the_mode(isolated, monkeypatch):
    assert su.isolated_uids() == (61001, 61002)
    monkeypatch.setenv("CODE_RUNNER_ALLOW_UNPRIVILEGED", "1")
    assert su.isolated_uids() == (os.getuid(),)


class TestCheckPrivilege:
    def test_root_with_the_three_capabilities_is_accepted(self):
        su.check_privilege(euid=0, cap_eff=su.REQUIRED_CAPS, flag=False)

    @pytest.mark.parametrize("missing", [su.CAP_KILL, su.CAP_SETGID, su.CAP_SETUID])
    def test_root_without_a_required_capability_refuses_to_start(self, missing):
        with pytest.raises(RuntimeError, match="SETUID, SETGID and KILL"):
            su.check_privilege(euid=0, cap_eff=su.REQUIRED_CAPS & ~(1 << missing), flag=False)

    def test_root_with_an_extra_capability_refuses_to_start(self):
        with pytest.raises(RuntimeError, match="exactly"):
            su.check_privilege(euid=0, cap_eff=su.REQUIRED_CAPS | (1 << 1), flag=False)  # CAP_DAC_OVERRIDE

    def test_root_with_the_unprivileged_flag_refuses_to_start(self):
        with pytest.raises(RuntimeError, match="must not be set for a root server"):
            su.check_privilege(euid=0, cap_eff=su.REQUIRED_CAPS, flag=True)

    def test_non_root_needs_the_flag(self):
        su.check_privilege(euid=1000, flag=True)
        with pytest.raises(RuntimeError, match="must start as root"):
            su.check_privilege(euid=1000, flag=False)


class TestUids:
    @pytest.mark.parametrize("name", ["RUNNER_UID", "RUNNER_GID", "PKG_UID", "PKG_GID"])
    @pytest.mark.parametrize("value", [0, 1, 999])
    def test_a_privileged_or_system_id_refuses_to_start(self, monkeypatch, name, value):
        monkeypatch.setattr(su, name, value)
        with pytest.raises(RuntimeError, match="at least 1000"):
            su.check_privilege(euid=0, cap_eff=su.REQUIRED_CAPS, flag=False)

    def test_the_runner_and_package_uids_must_differ(self, monkeypatch):
        monkeypatch.setattr(su, "PKG_UID", su.RUNNER_UID)
        with pytest.raises(RuntimeError, match="must differ"):
            su.check_privilege(euid=0, cap_eff=su.REQUIRED_CAPS, flag=False)


class TestCapabilityFile:
    def test_cap_eff_is_parsed_from_the_status_file_and_used_by_default(self, tmp_path, monkeypatch):
        status = tmp_path / "status"
        status.write_text("Name:\tx\nCapEff:\t00000000000000e0\nCapBnd:\t0\n")
        monkeypatch.setattr(su, "STATUS_PATH", str(status))
        assert su.read_cap_eff() == 0xE0
        su.check_privilege(euid=0, flag=False)  # reads the file when cap_eff is not injected
        status.write_text("CapEff:\t00000000000000ff\n")
        with pytest.raises(RuntimeError, match="exactly"):
            su.check_privilege(euid=0, flag=False)

    def test_a_status_file_without_cap_eff_is_an_error(self, tmp_path, monkeypatch):
        status = tmp_path / "status"
        status.write_text("Name:\tx\n")
        monkeypatch.setattr(su, "STATUS_PATH", str(status))
        with pytest.raises(RuntimeError, match="CapEff not found"):
            su.read_cap_eff()


def test_only_the_value_1_enables_the_unprivileged_mode(monkeypatch):
    for value in ("true", "0", "yes", ""):
        monkeypatch.setenv("CODE_RUNNER_ALLOW_UNPRIVILEGED", value)
        assert su.allow_unprivileged() is False
    monkeypatch.setenv("CODE_RUNNER_ALLOW_UNPRIVILEGED", "1")
    assert su.allow_unprivileged() is True
