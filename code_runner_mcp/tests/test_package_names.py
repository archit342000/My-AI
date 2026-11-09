import pytest

from package_names import MAX_PACKAGE_LENGTH, MAX_PACKAGES, validate_packages

PIP_OK = ["requests", "numpy==1.26.4", "pandas>=2.0", "requests[socks]", "zope.interface", "Django~=4.2", "pkg==1.*", "a", "torch==2.1.0+cpu"]
NPM_OK = ["JSONStream", "@Scope/Pkg@1.0.0", "lodash", "lodash@4.17.21", "@types/node", "@babel/core@^7.0.0", "left-pad@latest", "react@>=18", "@scope/pkg-name@1.x"]
BAD = [
    "--index-url=http://evil/simple", "-r", "-e .", "-", "--target=/tmp/x",           # options
    "https://x/y.whl", "git+https://github.com/u/r.git", "github:u/r", "file:../x", "ftp://x/y", "npm:other",   # URLs and aliases
    "./pkg", "../pkg", "/tmp/p", "~/p", ".hidden", "u/r", "a/b/c",                   # paths
    "requests ; os_name=='nt'", "re quests", "requests\n", "\trequests", "pkg;rm",     # whitespace and markers
    "", " ", "pkg==1,<2", "pkg@1 || 2", "pkg[", "pkg]", "päckage",                    # malformed
    "pkg@git+https://evil/r.git", "pkg@file:../x", "pkg@http://evil/x.tgz", "@scope/pkg@git+ssh://evil/r", "pkg@1:2",   # version-URL forms
    "pkg==git+https://evil/r.git", "pkg==file:../x", "pkg==http://evil/x",            # (pip equivalents)
]


@pytest.mark.parametrize("spec", PIP_OK)
def test_pip_accepts_plain_names(spec):
    validate_packages("pip", [spec])


@pytest.mark.parametrize("spec", NPM_OK)
def test_npm_accepts_plain_names(spec):
    validate_packages("npm", [spec])


@pytest.mark.parametrize("manager", ["pip", "npm"])
@pytest.mark.parametrize("spec", BAD)
def test_options_urls_paths_and_malformed_specs_are_rejected(manager, spec):
    with pytest.raises(ValueError):
        validate_packages(manager, [spec])


def test_one_bad_entry_rejects_the_whole_request_and_is_named():
    with pytest.raises(ValueError, match="--index-url"):
        validate_packages("pip", ["requests", "--index-url=http://x", "numpy"])


def test_rejection_message_truncates_a_long_entry():
    with pytest.raises(ValueError) as e:
        validate_packages("pip", ["-" + "x" * 90])
    assert len(str(e.value)) < 80


def test_caps():
    validate_packages("pip", ["a"] * MAX_PACKAGES)
    with pytest.raises(ValueError, match="Too many"):
        validate_packages("pip", ["a"] * (MAX_PACKAGES + 1))
    validate_packages("pip", ["a" * MAX_PACKAGE_LENGTH])
    with pytest.raises(ValueError, match="too long"):
        validate_packages("pip", ["a" * (MAX_PACKAGE_LENGTH + 1)])


def test_pip_forms_are_not_valid_npm_and_the_other_way_round():
    with pytest.raises(ValueError):
        validate_packages("npm", ["numpy==1.26"])      # pip specifier
    with pytest.raises(ValueError):
        validate_packages("pip", ["@types/node"])      # npm scope


def test_unknown_manager_is_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        validate_packages("gem", ["x"])
