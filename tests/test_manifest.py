from pathlib import Path

import pytest

from devman.manifest import OnEntry, Project, load, matches

FIXTURES = Path(__file__).parent / "fixtures" / "manifests"


def parse(tmp_path: Path, text: str):
    file = tmp_path / "projects.toml"
    file.write_text(text)
    return load(file)


def one_error(tmp_path: Path, text: str, project: str = "p") -> list[str]:
    manifest = parse(tmp_path, text)
    assert project not in manifest.projects
    return manifest.errors[project]


def test_the_concept_example_parses() -> None:
    manifest = load(FIXTURES / "example.toml")
    assert manifest.errors == {}
    assert manifest.projects["devman"] == Project(
        name="devman",
        path=Path("/work/devman"),
        take=("check", "test", "format"),
        on=(
            OnEntry("save", ("**/*.py",), (".scratch/**",), "format"),
            OnEntry("land", ("main", "release/*"), (), "check"),
        ),
    )
    assert manifest.projects["gitman"].on == ()


def test_a_bad_table_refuses_only_its_own_project() -> None:
    manifest = load(FIXTURES / "mixed.toml")
    assert list(manifest.projects) == ["good"]
    assert manifest.errors == {"typo": ["unknown key tkae"]}


def test_a_toml_syntax_error_refuses_the_file(tmp_path: Path) -> None:
    manifest = parse(tmp_path, "[p\npath = 1")
    assert manifest.projects == {}
    assert "is not valid TOML" in manifest.errors[""][0]


def test_a_missing_file_is_a_file_level_error(tmp_path: Path) -> None:
    manifest = load(tmp_path / "none.toml")
    assert manifest.projects == {}
    assert manifest.errors[""][0].startswith("cannot read ")


def test_rule_1_a_top_level_item_must_be_a_table(tmp_path: Path) -> None:
    manifest = parse(tmp_path, 'stray = 1\n[p]\npath = "/p"\n')
    assert manifest.errors == {"": ["stray is not a table"]}
    assert "p" in manifest.projects


def test_rule_2_project_name(tmp_path: Path) -> None:
    reasons = one_error(tmp_path, '["-bad"]\npath = "/p"\n', "-bad")
    assert reasons == ["project name -bad does not match [A-Za-z0-9][A-Za-z0-9._-]*"]
    assert "loci.nvim" in parse(tmp_path, '["loci.nvim"]\npath = "/p"\n').projects


def test_rule_3_unknown_keys(tmp_path: Path) -> None:
    assert one_error(tmp_path, '[p]\npath = "/p"\nextra = 1\n') == ["unknown key extra"]
    text = (
        '[p]\npath = "/p"\n[[p.on]]\nevent = "save"\nmatch = "*"\nrun = "a"\nrunn = 1\n'
    )
    assert one_error(tmp_path, text) == ["unknown key runn"]


def test_rule_4_workflow_names(tmp_path: Path) -> None:
    assert one_error(tmp_path, '[p]\npath = "/p"\ntake = ["a.b"]\n') == [
        "workflow name a.b must not contain a dot"
    ]
    assert one_error(tmp_path, '[p]\npath = "/p"\ntake = ["-a"]\n') == [
        "workflow name -a does not match [A-Za-z0-9][A-Za-z0-9_-]*"
    ]
    text = '[p]\npath = "/p"\n[[p.on]]\nevent = "save"\nmatch = "*"\nrun = "a.b"\n'
    assert one_error(tmp_path, text) == ["workflow name a.b must not contain a dot"]


def test_rule_5_path(tmp_path: Path) -> None:
    assert one_error(tmp_path, "[p]\n") == ["path is required"]
    assert one_error(tmp_path, "[p]\npath = 3\n") == ["path must be a string"]
    assert one_error(tmp_path, '[p]\npath = "rel/dir"\n') == [
        "path rel/dir is not absolute"
    ]


def test_rule_5_tilde_expands_and_the_disk_is_not_checked(tmp_path: Path) -> None:
    manifest = parse(tmp_path, '[p]\npath = "~/no/such/dir/"\n')
    assert manifest.projects["p"].path == Path.home() / "no/such/dir"


def test_rule_6_a_shared_path_refuses_both(tmp_path: Path) -> None:
    manifest = parse(
        tmp_path, '[a]\npath = "/x"\n[b]\npath = "/x/"\n[c]\npath = "/x/c"\n'
    )
    assert manifest.errors == {"a": ["path shared with b"], "b": ["path shared with a"]}
    assert list(manifest.projects) == ["c"]  # a nested path is allowed


def test_rule_7_event_and_globs(tmp_path: Path) -> None:
    head = '[p]\npath = "/p"\n[[p.on]]\n'
    assert one_error(tmp_path, head + 'event = "Save"\nmatch = "*"\nrun = "a"\n') == [
        "on[0] event Save does not match [a-z][a-z0-9._-]*"
    ]
    bad_match = "on[0] match must be a string or a list of strings, none empty"
    for match in ('""', "[]", '[""]', "3"):
        text = head + f'event = "save"\nmatch = {match}\nrun = "a"\n'
        assert one_error(tmp_path, text) == [bad_match]
    text = head + 'event = "save"\nmatch = "*"\nexclude = [""]\nrun = "a"\n'
    assert one_error(tmp_path, text) == [
        "on[0] exclude must be a list of non-empty strings"
    ]
    assert one_error(tmp_path, head + 'event = "save"\n') == [
        "on[0] needs match",
        "on[0] needs run",
    ]


def test_rule_9_a_done_failed_loop_is_refused(tmp_path: Path) -> None:
    text = (
        '[p]\npath = "/p"\n[[p.on]]\nevent = "done"\nmatch = "check"\nrun = "check"\n'
    )
    assert one_error(tmp_path, text) == ["on entries form a loop: check -> check"]


def test_rule_9_a_two_step_loop_names_the_cycle(tmp_path: Path) -> None:
    text = (
        '[p]\npath = "/p"\n'
        '[[p.on]]\nevent = "done"\nmatch = "check"\nrun = "test"\n'
        '[[p.on]]\nevent = "failed"\nmatch = "test"\nrun = "check"\n'
    )
    assert one_error(tmp_path, text) == [
        "on entries form a loop: check -> test -> check"
    ]


def test_a_done_chain_without_a_cycle_parses(tmp_path: Path) -> None:
    text = '[p]\npath = "/p"\n[[p.on]]\nevent = "done"\nmatch = "check"\nrun = "test"\n'
    assert "p" in parse(tmp_path, text).projects


def test_a_save_entry_never_counts_as_a_loop_edge(tmp_path: Path) -> None:
    text = '[p]\npath = "/p"\n[[p.on]]\nevent = "save"\nmatch = "**"\nrun = "format"\n'
    assert "p" in parse(tmp_path, text).projects


@pytest.mark.parametrize(
    ("entry", "subject", "expected"),
    [
        (OnEntry("save", ("**/*.py",), (), "f"), "a.py", True),
        (OnEntry("save", ("**/*.py",), (), "f"), "src/a.py", True),
        (OnEntry("save", ("**/*.py",), (), "f"), "src/a.txt", False),
        (OnEntry("save", ("*.py",), (), "f"), "src/a.py", False),
        (
            OnEntry("save", ("**/*.py",), (".scratch/**",), "f"),
            ".scratch/x/a.py",
            False,
        ),
        (OnEntry("land", ("main",), (), "c"), "main", True),
        (OnEntry("land", ("main",), (), "c"), "main2", False),
        (OnEntry("land", ("main", "dev"), (), "c"), "dev", True),
        (OnEntry("manual", ("**",), (), "c"), "", True),
    ],
)
def test_matches(entry: OnEntry, subject: str, expected: bool) -> None:
    assert matches(entry, subject) is expected
