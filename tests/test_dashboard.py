"""Dashboard: the state it serves comes from the guards' own parsers, and the server
behind it can only read."""
import http.client
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import urllib.request
from urllib.parse import quote

import pytest
from conftest import HOOKS, phase, phase_log

sys.path.insert(0, HOOKS)
import checkpoint  # noqa: E402
import dashboard  # noqa: E402
import status  # noqa: E402

LONG_TEXT_KEYS = {"spec", "plan", "config", "checkpoints", "actions", "evidence"}


def make_features(root):
    features = root / ".dev-workflow" / "features"
    (features / "alpha").mkdir(parents=True)
    (features / "beta").mkdir()
    (features / "alpha" / "phase-log.md").write_text(phase_log(
        phase("Phase 1 — parser", approved=True, evidence="pytest -q -> 12 passed"),
        phase("Phase 2 — server", reviewed=True),
        feature="Alpha feature"))
    (features / "beta" / "phase-log.md").write_text(phase_log(phase("Phase 1 — only")))
    (root / ".dev-workflow" / "active").write_text("alpha\n")


def write_feature(root, slug, *sections):
    feature_dir = root / ".dev-workflow" / "features" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "phase-log.md").write_text(phase_log(*sections, feature=slug.title()))


def write_registry(roots):
    path = status.registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump([str(root) for root in roots], fh)


@pytest.fixture
def served(tmp_path, monkeypatch):
    """A live server on a thread; yields a GET helper returning (status, body)."""
    monkeypatch.setattr(dashboard, "IDLE_SECONDS", 1.0)
    with dashboard.make_server(str(tmp_path)) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=dashboard.serve, args=(server,))
        thread.start()

        def request(path, method="GET", host="127.0.0.1:%d" % port):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request(method, path, headers={"Host": host})
            response = conn.getresponse()
            result = response.status, response.read()
            conn.close()
            return result

        yield request
        thread.join(timeout=5)


def test_collect_reads_features_and_phases_through_the_workflow_parsers(git_repo):
    make_features(git_repo)
    ref = checkpoint.snapshot(str(git_repo), "Edit", force=True).replace("refs/", "", 1)
    state = dashboard.collect(str(git_repo))

    assert [(f["slug"], f["active"], f["approved"], f["total"]) for f in state["features"]] == [
        ("alpha", True, 1, 2), ("beta", False, 0, 1)]
    assert state["selected"] == "alpha"
    assert state["title"] == "Alpha feature"
    done, current = state["phases"]
    assert done["approved"] and not done["current"] and not done["evidence_empty"]
    assert current["current"] and current["evidence_empty"]
    assert current["status"].startswith("[x] coded  [x] code-reviewed")
    assert [w for w in state["warnings"] if "'Phase 2 — server'" in w]
    assert state["gate"] == "no gate file"
    project = shlex.quote(str(git_repo))
    assert state["actions"]["rollback"] == {ref: "! cd %s && CLAUDE_PROJECT_DIR=%s python3 %s rollback %s" % (
        project, project, shlex.quote(os.path.join(HOOKS, "checkpoint.py")), shlex.quote(ref))}

    assert dashboard.collect(str(git_repo), "beta")["selected"] == "beta"
    assert dashboard.collect(str(git_repo), "../..")["selected"] == "alpha"

    alpha, beta = state["features"]
    assert (alpha["title"], alpha["current"], alpha["waiting"]) == ("Alpha feature", "Phase 2 — server", True)
    assert alpha["track"] == ["done", "waiting"]
    assert (beta["current"], beta["waiting"], beta["coded"]) == ("Phase 1 — only", False, True)

    write_feature(git_repo, "gamma", phase("Phase 1 — all", approved=True, evidence="\n  - a\n  - b"))
    write_feature(git_repo, "delta", phase("Phase 1 — draft", coded=False))
    write_feature(git_repo, "epsilon", phase("Phase 1 — <title>", coded=False))
    states = {f["slug"]: f["state"] for f in dashboard.list_features(str(git_repo), "alpha")}
    assert states == {
        "alpha": "Needs approval",
        "beta": "Phase 1, in review",
        "delta": "Phase 1, in progress",
        "epsilon": "No phases yet",
        "gamma": "Done",
    }
    assert dashboard.collect(str(git_repo), "gamma")["phases"][0]["evidence"] == "- a\n- b"


def test_overview_shows_each_live_project_once_waiting_first(tmp_path):
    quiet = tmp_path / "quiet"
    write_feature(quiet, "one", phase("Phase 1 — a"))
    busy = tmp_path / "busy"
    make_features(busy)
    write_feature(busy, "aaa", phase("Phase 1 — a"))
    gone = tmp_path / "gone"
    gone.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(busy)
    write_registry([alias, gone, busy])

    board = dashboard.overview(str(quiet))["projects"]
    assert [project["root"] for project in board] == [os.path.realpath(busy), os.path.realpath(quiet)]
    assert [feature["slug"] for feature in board[0]["features"]] == ["alpha", "aaa", "beta"]
    assert board[0]["name"] == "busy"
    assert board[0]["resume"] == "cd %s && claude --continue" % shlex.quote(os.path.realpath(busy))


def test_a_failing_section_does_not_take_the_others_down(tmp_path, monkeypatch):
    make_features(tmp_path)

    def broken_show(root):
        raise ValueError("config exploded")

    monkeypatch.setattr(dashboard.config, "show", broken_show)
    state = dashboard.collect(str(tmp_path))
    assert state["config"] == {"error": "config exploded"}
    assert len(state["phases"]) == 2
    assert state["features"][0]["slug"] == "alpha"


def test_the_server_serves_the_page_and_live_state_and_nothing_else(tmp_path, served):
    make_features(tmp_path)
    log_path = tmp_path / ".dev-workflow" / "features" / "alpha" / "phase-log.md"

    code, page = served("/")
    assert code == 200 and b"/api/state" in page
    code, before = served("/api/state")
    assert code == 200 and json.loads(before)["selected"] == "alpha"

    log_path.write_text(log_path.read_text().replace("[ ] USER APPROVED", "[x] USER APPROVED"))
    code, after = served("/api/state?feature=alpha")
    assert all(p["approved"] for p in json.loads(after)["phases"])

    assert served("/", host="evil.example:80")[0] == 403
    assert served("/api/state", method="POST")[0] == 501

    other = tmp_path / "other"
    make_features(other)
    status.register(str(other))
    unregistered = tmp_path / "unregistered"
    make_features(unregistered)
    code, body = served("/api/overview")
    board = json.loads(body)["projects"]
    assert code == 200 and len(board) == 2
    for project in board:
        assert not LONG_TEXT_KEYS & set(project)
        assert not any(LONG_TEXT_KEYS & set(feature) for feature in project["features"])

    for foreign in ("/etc", "..", str(unregistered)):
        assert served("/api/state?project=" + quote(foreign))[0] == 404
    code, body = served("/api/state?project=%s&feature=beta" % quote(os.path.realpath(other)))
    assert code == 200 and json.loads(body)["selected"] == "beta"


def tree_fingerprint(root):
    fingerprint = {}
    for directory, _subdirs, files in os.walk(root):
        for name in files:
            path = os.path.join(directory, name)
            with open(path, "rb") as fh:
                fingerprint[path] = (os.stat(path).st_mtime_ns, fh.read())
    return fingerprint


def test_hitting_every_route_writes_nothing_not_even_in_git(git_repo, served):
    make_features(git_repo)
    (git_repo / ".approval-gate").write_text("LOCKED\n")
    assert checkpoint.snapshot(str(git_repo), "Edit", force=True)
    status.register(str(git_repo))
    home = os.environ["HOME"]
    before = tree_fingerprint(git_repo)
    home_before = tree_fingerprint(home)

    code, body = served("/api/state")
    assert len(json.loads(body)["checkpoints"]) == 1
    project = quote(os.path.realpath(git_repo))
    for path in ("/", "/api/state?feature=beta", "/missing", "/api/overview",
                 "/api/state?project=%s&feature=beta" % project, "/api/state?project=/etc"):
        served(path)
    served("/api/state", method="POST")
    served("/api/state", host="evil.example")

    assert tree_fingerprint(git_repo) == before
    assert home_before and tree_fingerprint(home) == home_before


@pytest.mark.skipif(not hasattr(os, "fork"), reason="--detach needs fork")
def test_detach_returns_at_once_and_leaves_a_server_running(tmp_path):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    proc = subprocess.run([sys.executable, os.path.join(HOOKS, "dashboard.py"), "--detach"],
                          stdout=subprocess.PIPE, text=True, env=env, timeout=5)
    match = re.search(r"(http://127\.0\.0\.1:\d+/) \(pid (\d+);", proc.stdout)
    assert match, proc.stdout
    url, pid = match.group(1), int(match.group(2))
    try:
        os.kill(pid, 0)
        with urllib.request.urlopen(url + "api/state", timeout=5) as response:
            assert json.loads(response.read())["root"] == str(tmp_path)
    finally:
        os.kill(pid, signal.SIGTERM)


def test_serve_returns_once_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "IDLE_SECONDS", 0.3)
    with dashboard.make_server(str(tmp_path)) as server:
        thread = threading.Thread(target=dashboard.serve, args=(server,))
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
