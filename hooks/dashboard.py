#!/usr/bin/env python3
"""CLI behind /dev-workflow:dashboard: a read-only local web view of the workflow.

Read-only is the invariant: a browser request is no Claude tool call, so gate.py never
sees it, and any route that writes a file or a git ref would bypass the approval gate.

Never call checkpoint.working_tree / snapshot / since_ship (they write git objects) or
any hook's main(); actions are shown as `!` commands for the user's own shell.
"""
import json
import os
import select
import shlex
import sys
import textwrap
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

import _workflow
import checkpoint
import config
import evidence_guard
import plan_guard
import status

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
PAGE_PATH = os.path.join(HOOKS_DIR, "dashboard.html")
CHECKPOINT_CLI = os.path.join(HOOKS_DIR, "checkpoint.py")
GATE_NAME = ".approval-gate"
IDLE_SECONDS = 1800
RECENT_CHECKPOINTS = 10
TEMPLATE_TITLE = "<title>"


def projects(start_root):
    live_roots = []
    for candidate in [start_root] + status.registered():
        root = os.path.realpath(candidate)
        if root not in live_roots and os.path.isdir(os.path.join(root, _workflow.STATE_DIR)):
            live_roots.append(root)
    return live_roots


def overview(start_root):
    boards = [project_board(root) for root in projects(start_root)]
    waiting_boards = [board for board in boards if has_waiting(board["features"])]
    other_boards = [board for board in boards if not has_waiting(board["features"])]
    return {"projects": waiting_boards + other_boards}


def project_board(root):
    active_slug = _workflow.docs_dir(root)[1]
    features = guarded(list_features, root, active_slug)
    if isinstance(features, list):
        waiting = [feature for feature in features if feature["waiting"]]
        others = [feature for feature in features if not feature["waiting"]]
        features = waiting + others
    return {"root": root, "name": os.path.basename(root), "features": features,
            "resume": "cd %s && claude --continue" % shlex.quote(root)}


def has_waiting(features):
    return isinstance(features, list) and any(feature["waiting"] for feature in features)


def collect(root, requested_slug=None):
    active_dir, active_slug = _workflow.docs_dir(root)
    features = guarded(list_features, root, active_slug)
    listed_slugs = [feature["slug"] for feature in features] if isinstance(features, list) else []
    if requested_slug in listed_slugs:
        slug = requested_slug
        feature_dir = os.path.join(root, _workflow.STATE_DIR, "features", slug)
    else:
        slug = active_slug
        feature_dir = active_dir

    log = read_doc(feature_dir, "phase-log.md")
    spec = read_doc(feature_dir, "spec.md")
    plan = read_doc(feature_dir, "plan.md")
    checkpoints = guarded(recent_checkpoints, root)
    return {
        "root": root,
        "features": features,
        "selected": slug,
        "title": guarded(feature_title, log, spec, slug),
        "phases": guarded(phase_cards, log),
        "spec": spec,
        "plan": plan,
        "warnings": guarded(guard_warnings, log, plan, root),
        "gate": guarded(gate_state, root),
        "checkpoints": checkpoints,
        "config": guarded(config.show, root),
        "actions": guarded(copyable_actions, root, checkpoints),
    }


def guarded(build, *args):
    try:
        return build(*args)
    except Exception as exc:
        return {"error": str(exc) or type(exc).__name__}


def read_doc(feature_dir, name):
    return _workflow.read(os.path.join(feature_dir, name)) or ""


def list_features(root, active_slug):
    features_dir = os.path.join(root, _workflow.STATE_DIR, "features")
    if not os.path.isdir(features_dir):
        return []
    slugs = [slug for slug in sorted(os.listdir(features_dir))
             if os.path.isdir(os.path.join(features_dir, slug))]
    return [feature_summary(os.path.join(features_dir, slug), slug, active_slug)
            for slug in slugs]


def feature_summary(feature_dir, slug, active_slug):
    log = read_doc(feature_dir, "phase-log.md")
    sections = list(_workflow.iter_phases(log))
    approved = [title for title, _body, is_approved in sections if is_approved]
    current_title, current_body = first_unapproved(sections) or (None, "")
    feature = {
        "slug": slug,
        "active": slug == active_slug,
        "title": feature_title(log, read_doc(feature_dir, "spec.md"), slug),
        "approved": len(approved),
        "total": len(sections),
        "current": current_title,
        "waiting": bool(evidence_guard.REVIEW_DONE.search(current_body)),
        "coded": "[x] coded" in (field(current_body, "Status") or "").lower(),
    }
    feature["state"] = row_state(sections, feature)
    feature["track"] = phase_track(sections, feature["waiting"])
    return feature


def first_unapproved(sections):
    return next(((title, body) for title, body, approved in sections if not approved), None)


def row_state(sections, feature):
    if not sections or TEMPLATE_TITLE in sections[0][0]:
        return "No phases yet"
    if feature["current"] is None:
        return "Done"
    if feature["waiting"]:
        return "Needs approval"
    if feature["coded"]:
        return short_title(feature["current"]) + ", in review"
    return short_title(feature["current"]) + ", in progress"


def short_title(section_title):
    return section_title.split(" — ", 1)[0]


def phase_track(sections, is_waiting):
    current_index = next((index for index, (_title, _body, is_approved) in enumerate(sections)
                          if not is_approved), None)
    return [track_segment(is_approved, index == current_index, is_waiting)
            for index, (_title, _body, is_approved) in enumerate(sections)]


def track_segment(is_approved, is_current, is_waiting):
    if is_approved:
        return "done"
    if not is_current:
        return "todo"
    if is_waiting:
        return "waiting"
    return "current"


def feature_title(log, spec, slug):
    return (status.title_from(log, "Phase log:")
            or status.title_from(spec, "Spec:")
            or slug or "(unnamed)")


def phase_cards(log):
    cards = [phase_card(title, body, approved)
             for title, body, approved in _workflow.iter_phases(log)]
    current = next((card for card in cards if not card["approved"]), None)
    if current:
        current["current"] = True
    return cards


def phase_card(title, body, approved):
    return {
        "title": title,
        "approved": approved,
        "current": False,
        "status": field(body, "Status"),
        "review_rounds": field(body, "Review rounds"),
        "unresolved": field(body, "Unresolved"),
        "evidence": field(body, "Evidence"),
        "evidence_empty": evidence_guard.evidence_empty(body),
    }


def field(body, name):
    text = _workflow.field_text(body, name)
    return textwrap.dedent(text).strip() if text is not None else None


def guard_warnings(log, plan, root):
    warnings = []
    if plan:
        warnings += plan_guard.plan_findings(plan)
    if log:
        warnings += plan_guard.budget_findings(log)
        warnings += plan_guard.map_findings(log, root)
        warnings += plan_guard.lessons_findings(log)
        warnings += evidence_warnings(log)
    return warnings


def evidence_warnings(log):
    current_section = first_unapproved(_workflow.iter_phases(log))
    if current_section is None:
        return []
    title, body = current_section
    if evidence_guard.REVIEW_DONE.search(body) and evidence_guard.evidence_empty(body):
        return ["'%s' is marked reviewed but its Evidence ledger is empty; the evidence "
                "gate will refuse to end the turn until it cites proof." % title]
    return []


def gate_state(root):
    gate = _workflow.read(os.path.join(root, GATE_NAME))
    if gate is None:
        return "no gate file"
    first = next((line.strip() for line in gate.splitlines() if line.strip()), "")
    return first.upper() or "empty"


def recent_checkpoints(root):
    return checkpoint.list_snapshots(root)[:RECENT_CHECKPOINTS]


def copyable_actions(root, checkpoints):
    in_project = "! cd %s && " % shlex.quote(root)
    # checkpoint.py picks CLAUDE_PROJECT_DIR over cwd, so cd alone does not pin the project.
    pinned_project = "CLAUDE_PROJECT_DIR=%s " % shlex.quote(root)
    listed = checkpoints if isinstance(checkpoints, list) else []
    rollback = {}
    for row in listed:
        rollback[row["ref"]] = in_project + pinned_project + "python3 %s rollback %s" % (
            shlex.quote(CHECKPOINT_CLI), shlex.quote(row["ref"]))
    return {"unlock_gate": in_project + "echo UNLOCKED > " + GATE_NAME,
            "rollback": rollback}


class Handler(BaseHTTPRequestHandler):
    # Per connection: a browser's idle preconnect must not stall this single thread.
    timeout = 5

    def do_GET(self):
        if not self.is_own_host():
            self.send(403, "text/plain; charset=utf-8", b"forbidden host\n")
            return
        url = urlsplit(self.path)
        if url.path == "/":
            with open(PAGE_PATH, "rb") as page:
                self.send(200, "text/html; charset=utf-8", page.read())
        elif url.path == "/api/overview":
            self.send_json(overview(self.server.project_root))
        elif url.path == "/api/state":
            self.send_state(parse_qs(url.query))
        else:
            self.send_not_found()

    def send_state(self, query):
        requested_project = query.get("project", [None])[0]
        requested_slug = query.get("feature", [None])[0]
        if requested_project is None:
            self.send_json(collect(self.server.project_root, requested_slug))
        elif requested_project in projects(self.server.project_root):
            self.send_json(collect(requested_project, requested_slug))
        else:
            self.send_not_found()

    def send_json(self, payload):
        self.send(200, "application/json", json.dumps(payload).encode("utf-8"))

    def send_not_found(self):
        self.send(404, "text/plain; charset=utf-8", b"not found\n")

    def is_own_host(self):
        # Any other Host is a DNS-rebinding page trying to read the state.
        port = self.server.server_address[1]
        allowed = {"127.0.0.1:%d" % port, "localhost:%d" % port}
        return self.headers.get("Host", "") in allowed

    def send(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def make_server(root):
    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.project_root = root
    return server


def serve(server):
    # One request at a time: config.show swaps os.environ while it runs.
    while True:
        ready, _, _ = select.select([server], [], [], IDLE_SECONDS)
        if not ready:
            return
        server.handle_request()


USAGE = "usage: dashboard.py [--detach]"


def announce(url, pid):
    print("Dashboard: %s (pid %d; stops after %d min idle)" % (url, pid, IDLE_SECONDS // 60))
    sys.stdout.flush()


def detach(url):
    child_pid = os.fork()
    if child_pid:
        announce(url, child_pid)
        os._exit(0)
    os.setsid()
    # The launcher reads our stdout until EOF, so the child must let go of the real fds.
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    os.close(devnull)


def main(argv):
    args = argv[1:]
    if args not in ([], ["--detach"]):
        print(USAGE)
        return 2
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    server = make_server(root)
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    if args == ["--detach"] and hasattr(os, "fork"):
        detach(url)
    else:
        announce(url, os.getpid())
    with server:
        serve(server)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
