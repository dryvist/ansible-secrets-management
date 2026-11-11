"""Loopback-client AppRoles accept the node-local source in both bound lists.

`openbao_loopback_client_approles` (08b) declares every identity that logs in
over the node-local loopback listener: each enabled `openbao_rotators` entry
plus the snapshot, secret-age-audit and scheduled AppRole secret-id rotation
identity names. `openbao_approle_cli_parameters` appends 127.0.0.1/32 to BOTH
the `secret_id_bound_cidrs` and `token_bound_cidrs` of every listed identity,
so a credential redeemed over loopback is also usable from loopback.

These render the REAL defaults and model the login and the token use with
Python's ipaddress against the rendered lists, never a reimplementation.
"""

import ipaddress
import os
from pathlib import Path
import unittest
from unittest import mock

from test_openbao_hatchet_killtest_policy_reach import REQUIRED_ENV, render, role_defaults

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_DIR = ROOT / "roles" / "openbao" / "defaults" / "main"
LOOPBACK_CIDR = "127.0.0.1/32"
# Documentation-range fixtures for the classes the listed identities live in.
ENV = {"OPENBAO_MANAGEMENT_CIDRS": "192.0.2.0/24", "OPENBAO_WORKSTATION_CIDRS": "198.51.100.0/24"}


def _rendered(expression, overrides=None, **env):
    with mock.patch.dict(os.environ, {**REQUIRED_ENV, **env}):
        return render({**role_defaults(), **(overrides or {})}, "{{ " + expression + " }}")


def _accepts(cidr_csv, source="127.0.0.1"):
    networks = [ipaddress.ip_network(part.strip()) for part in cidr_csv.split(",") if part.strip()]
    return any(ipaddress.ip_address(source) in network for network in networks)


def _params(name, overrides=None, **env):
    return _rendered("openbao_approle_cli_parameters['%s']" % name, overrides, **env)


class LoopbackClients(unittest.TestCase):
    def test_loopback_login_and_use_accepted_for_every_listed_identity(self):
        names = _rendered("openbao_loopback_client_approles", **ENV)
        self.assertGreater(len(names), 0)
        for name in names:
            params = _params(name, **ENV)
            with self.subTest(identity=name):
                # A login from the node-local loopback listener redeems the
                # secret_id ...
                self.assertTrue(_accepts(params["secret_id_bound_cidrs"]))
                # ... and the resulting token is used from the same source.
                self.assertTrue(_accepts(params["token_bound_cidrs"]))

    def test_the_loopback_address_appears_exactly_once_in_each_list(self):
        for name in _rendered("openbao_loopback_client_approles", **ENV):
            params = _params(name, **ENV)
            with self.subTest(identity=name):
                for field in ("secret_id_bound_cidrs", "token_bound_cidrs"):
                    with self.subTest(field=field):
                        self.assertEqual(params[field].split(",").count(LOOPBACK_CIDR), 1)

    def test_an_unlisted_machine_identity_does_not_get_the_loopback_source(self):
        # github-exporter is machine-class per the 08b override map and never
        # a loopback client.
        self.assertNotIn("github-exporter", _rendered("openbao_loopback_client_approles", **ENV))
        params = _params("github-exporter", **ENV)
        for field in ("secret_id_bound_cidrs", "token_bound_cidrs"):
            with self.subTest(field=field):
                self.assertNotIn(LOOPBACK_CIDR, params[field].split(","))
                self.assertFalse(_accepts(params[field]))

    def test_a_disabled_rotator_does_not_add_its_identity(self):
        names = _rendered(
            "openbao_loopback_client_approles",
            {"openbao_slack_rotate_enabled": False, "openbao_splunk_mcp_rotate_enabled": False},
            **ENV,
        )
        self.assertNotIn("slack-admin", names)
        self.assertNotIn("splunk-mcp-rotate", names)
        # The standing loopback clients are unaffected by the rotator knobs.
        self.assertIn("secret-age-audit", names)

    def test_no_defaults_file_hand_writes_the_loopback_suffix(self):
        # The declared list is the only source of the loopback address; a
        # hand-written suffix in any defaults file is a second source.
        for path in sorted(DEFAULTS_DIR.glob("*.yml")):
            with self.subTest(defaults=path.name):
                self.assertNotIn("," + LOOPBACK_CIDR, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
