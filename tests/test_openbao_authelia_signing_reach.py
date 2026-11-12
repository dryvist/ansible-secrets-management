"""Ask OpenBao itself which identities can read Authelia's signing leaf.

The leaf holds the OIDC key that signs elevation tokens, which
auth/authelia/role/elevate-* trusts. Every declared policy is rendered and
written to a real OpenBao dev server. Each AppRole then gets a token carrying
its whole policy list, so a deny in one policy overrides a grant in another
exactly as it does in production, and sys/capabilities answers. The reader set
is exact: a new reader fails here until it is added on purpose.
"""

import os
from pathlib import Path
from unittest import mock

import pytest
from test_openbao_hatchet_killtest_policy_reach import (
    REQUIRED_ENV,
    _call,
    _dev_server,
    render,
    role_defaults,
)

ROLE = Path(__file__).resolve().parents[1] / "roles/openbao"
DATA = "secret/data/apps/authelia-signing"
# Break-glass and human-unlocked identities, the human operator, and the apps/*
# writers (the Authelia signing writer, apps seed and rotation). No standing AI reader:
# ai-readonly and ai-elevated carry ai-global-read, whose deny on this leaf
# overrides read-apps. The standing CI deploy identity is denied explicitly.
READERS = {
    "admin",
    "ai-admin",
    "ai-admin-session",
    "ai-apply-all",
    "ai-apply-apps",
    "apps-rotate",
    "apps-seed",
    "operator-workstation",
}
# Policies no reader of a client secret may combine into a key read: the
# uicheck CI job and the Terrakube workspaces read secret/apps/authelia only.
CLIENT_SECRET_READERS = ("uicheck", "terrakube-iac-platform")


def _policies(role):
    names = role.get("token_policies") or [role["policy"]]
    return [names] if isinstance(names, str) else list(names)


@pytest.fixture(scope="module")
def reach_by_approle():
    with mock.patch.dict(os.environ, REQUIRED_ENV):
        variables = role_defaults()
        writer_name = variables["openbao_authelia_signing_writer_approle_name"]
        approles = render(variables, "{{ openbao_approles }}")
        rendered = {
            policy["name"]: render(
                {**variables, "item": policy},
                (ROLE / "templates" / policy["template"]).read_text(encoding="utf-8"),
            )
            for policy in render(variables, "{{ openbao_policies }}")
        }
    server, base = _dev_server()
    try:
        for name, text in rendered.items():
            status, body = _call(base, "root", "PUT", f"sys/policies/acl/{name}", {"policy": text})
            assert status == 204, (name, body)
        caps = {}
        policy_caps = {}
        for name in rendered:
            status, body = _call(base, "root", "POST", "auth/token/create",
                                 {"policies": [name], "no_default_policy": True})
            assert status == 200, (name, body)
            status, body = _call(base, "root", "POST", "sys/capabilities",
                                 {"token": body["auth"]["client_token"], "paths": [DATA]})
            assert status == 200, (name, body)
            policy_caps[name] = sorted(body[DATA])
        for role in approles:
            status, body = _call(base, "root", "POST", "auth/token/create",
                                 {"policies": _policies(role), "no_default_policy": True})
            assert status == 200, (role["name"], body)
            status, body = _call(base, "root", "POST", "sys/capabilities",
                                 {"token": body["auth"]["client_token"], "paths": [DATA]})
            assert status == 200, (role["name"], body)
            caps[role["name"]] = sorted(body[DATA])
    finally:
        server.terminate()
        server.wait(timeout=30)
    return caps, policy_caps, writer_name


def test_the_approles_that_can_read_the_signing_key_are_exact(reach_by_approle):
    caps, _, writer_name = reach_by_approle
    readers = {name for name, held in caps.items() if "read" in held or "root" in held}
    assert readers == READERS | {writer_name}


def test_the_authelia_signing_writer_holds_exactly_create_read_update_on_the_signing_key(
    reach_by_approle,
):
    caps, _, writer_name = reach_by_approle
    assert caps[writer_name] == ["create", "read", "update"]


def test_no_standing_ai_reader_reaches_the_signing_key(reach_by_approle):
    caps, _, _writer_name = reach_by_approle
    for name in ("ai-readonly", "ai-elevated", "ai-orchestrator", "semaphore", "ansible-converge"):
        assert caps[name] == ["deny"], name


def test_client_secret_readers_cannot_reach_the_signing_key(reach_by_approle):
    _, policy_caps, _writer_name = reach_by_approle
    for name in CLIENT_SECRET_READERS:
        assert policy_caps[name] == ["deny"], name


def test_the_standing_ci_deploy_identity_is_denied_the_signing_key(reach_by_approle):
    # iac-platform-deploy reads apps/* through read-apps, so it holds a client-secret
    # read on the same leaf family. Denied at the AppRole's full policy list.
    caps, _, _writer_name = reach_by_approle
    assert caps["iac-platform-deploy"] == ["deny"]
