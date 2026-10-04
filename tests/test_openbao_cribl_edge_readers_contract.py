"""Cribl Edge generated fields and path-exact readers stay isolated."""

from __future__ import annotations

import re
from pathlib import Path
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/openbao/defaults/main"
TEMPLATES = ROOT / "roles/openbao/templates"
FIELDS = "roles/openbao/defaults/main/01c-app-secrets-generated.yml"
SEED = ROOT / "roles/openbao/tasks/seed_generated_app_secret.yml"
APPS_POLICY = TEMPLATES / "apps-policy.hcl.j2"
EDGE_POLICY = TEMPLATES / "cribl-edge-reader-policy.hcl.j2"
POLICY_GRANT = re.compile(
    r'path\s+"([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^]]*)\]\s*\}',
    re.DOTALL,
)
EXPECTED_READERS = {
    "cribl-edge-mac-a": "cribl-edge-macbook",
    "cribl-edge-mac-b": "cribl-edge-mac-studio",
}


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _render(source: str, values: dict):
    templar = Templar(loader=DataLoader())
    templar.available_variables = values
    return templar.template(trust_as_template(source))


def _grants(source: str) -> list[tuple[str, tuple[str, ...]]]:
    return [
        (match.group(1), tuple(re.findall(r'"([^"]+)"', match.group(2))))
        for match in POLICY_GRANT.finditer(source)
    ]


def _apps_reader_policy(apps: set[str]) -> str:
    return _render(
        APPS_POLICY.read_text(encoding="utf-8"),
        {
            "ansible_managed": "Ansible managed",
            "openbao_kv_mount": "secret",
            "openbao_apps_read_apps": sorted(apps),
        },
    )


def _reader_policy(bucket: str) -> str:
    return _render(
        EDGE_POLICY.read_text(encoding="utf-8"),
        {
            "ansible_managed": "Ansible managed",
            "openbao_kv_mount": "secret",
            "item": {"bucket": bucket},
        },
    )


def _read_apps() -> set[str]:
    names = _yaml(DEFAULTS / "05c-terrakube-and-remaining-domain-names.yml")
    edge = _yaml(DEFAULTS / "05h-cribl-edge-readers.yml")
    generated_defaults = _yaml(DEFAULTS / "01c-app-secrets-generated.yml")
    generated = generated_defaults["openbao_generated_app_secrets"]
    promoted = _yaml(DEFAULTS / "01b-app-secrets.yml")["openbao_promoted_app_secrets"]
    values = {
        "openbao_generated_app_secrets": generated,
        "openbao_promoted_app_secrets": promoted,
        "openbao_router_key_catalog": generated_defaults["openbao_router_key_catalog"],
        "openbao_apps_read_published_apps": names[
            "openbao_apps_read_published_apps"
        ],
        "openbao_cribl_edge_mac_a_app": edge["openbao_cribl_edge_mac_a_app"],
        "openbao_cribl_edge_mac_b_app": edge["openbao_cribl_edge_mac_b_app"],
    }
    resolver = Templar(loader=DataLoader())
    resolver.available_variables = values
    values["openbao_apps_read_excluded_generated_apps"] = [
        resolver.template(trust_as_template(app))
        for app in edge["openbao_apps_read_excluded_generated_apps"]
    ]
    return set(_render(names["openbao_apps_read_apps"], values))


def _matches_apps_reader_contract(policy: str, apps: set[str]) -> bool:
    expected = {
        (f"secret/data/apps/{app}", ("read",)) for app in apps
    } | {
        (f"secret/metadata/apps/{app}", ("read", "list")) for app in apps
    } | {
        ("secret/data/infrastructure/unifi", ("read",)),
        ("secret/metadata/infrastructure/unifi", ("read",)),
    }
    return sorted(_grants(policy)) == sorted(expected)


def _matches_exact_reader_contract(policy: str, bucket: str) -> bool:
    return _grants(policy) == [(f"secret/data/apps/{bucket}", ("read",))]


def _seconds(value: str) -> int:
    match = re.fullmatch(r"(\d+)(s|m|h|d)", str(value))
    if not match:
        raise AssertionError(f"not a finite duration: {value}")
    amount, unit = match.groups()
    return int(amount) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


class CriblEdgeReaderContract(unittest.TestCase):
    def setUp(self):
        self.edge = _yaml(DEFAULTS / "05h-cribl-edge-readers.yml")
        self.generated = _yaml(DEFAULTS / "01c-app-secrets-generated.yml")[
            "openbao_generated_app_secrets"
        ]

    def test_three_password_fields_use_generate_if_absent_seed_logic(self):
        tunables = _yaml(DEFAULTS / "01b-app-secret-generation.yml")
        fields = {"cribl-edge", *EXPECTED_READERS.values()}
        for bucket in fields:
            with self.subTest(bucket=bucket):
                self.assertIn("cribl_admin_password", self.generated[bucket])

        generate = next(
            task
            for task in yaml.safe_load(SEED.read_text(encoding="utf-8"))
            if task.get("name") == "Generate a random value for each field that is not yet stored"
        )
        conditions = generate["when"]
        if isinstance(conditions, str):
            conditions = [conditions]
        for stored in (False, True):
            data = {"cribl_admin_password": "present"} if stored else {}
            values = {
                **tunables,
                "item": "cribl_admin_password",
                "openbao_seed_current_data": data,
                "openbao_seed_rotate_fields": [],
            }
            outcomes = [
                _render("{{ " + condition + " }}", values)
                for condition in conditions
            ]
            self.assertEqual(all(bool(value) for value in outcomes), not stored)

    def test_apps_reader_has_exact_existing_grants_including_linux_bucket_only(self):
        apps = _read_apps()
        policy = _apps_reader_policy(apps)
        self.assertTrue(_matches_apps_reader_contract(policy, apps))
        self.assertIn("cribl-edge", apps)
        self.assertNotIn(self.edge["openbao_cribl_edge_mac_a_app"], apps)
        self.assertNotIn(self.edge["openbao_cribl_edge_mac_b_app"], apps)

    def test_each_mac_policy_and_approle_names_one_bucket_exactly(self):
        policy_rows = _yaml(DEFAULTS / "07c-base-policies.yml")[
            "openbao_base_policies_static"
        ]
        workstation_roles = _yaml(DEFAULTS / "07f-workstation-approles.yml")[
            "openbao_workstation_approles"
        ]

        for role_name, bucket in EXPECTED_READERS.items():
            with self.subTest(role=role_name):
                suffix = role_name.removeprefix("cribl-edge-").replace("-", "_")
                app_var = f"openbao_cribl_edge_{suffix}_app"
                policy_var = f"openbao_cribl_edge_{suffix}_policy_name"
                approle_var = f"openbao_cribl_edge_{suffix}_approle_name"
                self.assertEqual(self.edge[app_var], bucket)
                self.assertEqual(self.edge[policy_var], role_name)
                self.assertEqual(self.edge[approle_var], role_name)

                policy_row = next(
                    row for row in policy_rows if row.get("name") == f"{{{{ {policy_var} }}}}"
                )
                self.assertEqual(policy_row["template"], EDGE_POLICY.name)
                self.assertEqual(policy_row["bucket"], bucket)
                role = next(
                    row
                    for row in workstation_roles
                    if row.get("name") == f"{{{{ {approle_var} }}}}"
                )
                self.assertEqual(role["policy"], f"{{{{ {policy_var} }}}}")
                policy = _reader_policy(policy_row["bucket"])
                self.assertTrue(_matches_exact_reader_contract(policy, bucket))

    def test_mac_readers_cannot_read_any_other_cribl_bucket(self):
        buckets = ["cribl-edge", *EXPECTED_READERS.values()]
        for role_name, own_bucket in EXPECTED_READERS.items():
            policy = _reader_policy(own_bucket)
            granted = {path for path, _ in _grants(policy)}
            with self.subTest(role=role_name):
                self.assertEqual(granted, {f"secret/data/apps/{own_bucket}"})
                for other_bucket in buckets:
                    if other_bucket != own_bucket:
                        self.assertNotIn(f"secret/data/apps/{other_bucket}", granted)

    def test_each_policy_contract_rejects_a_widened_variant(self):
        apps = _read_apps()
        widened_apps = _apps_reader_policy(apps) + '\npath "secret/data/apps/*" {\n  capabilities = ["read"]\n}\n'
        self.assertFalse(_matches_apps_reader_contract(widened_apps, apps))

        for own_bucket, other_bucket in (
            ("cribl-edge-macbook", "cribl-edge-mac-studio"),
            ("cribl-edge-mac-studio", "cribl-edge"),
        ):
            widened = _reader_policy(own_bucket) + (
                f'\npath "secret/data/apps/{other_bucket}" {{\n'
                '  capabilities = ["read"]\n}\n'
            )
            with self.subTest(own_bucket=own_bucket):
                self.assertFalse(_matches_exact_reader_contract(widened, own_bucket))

    def test_roles_have_finite_workstation_bounds_and_rotation(self):
        ttl_defaults = _yaml(DEFAULTS / "08a-admin-and-ttls.yml")
        cidr_defaults = _yaml(DEFAULTS / "08b-cidr-and-unlock.yml")
        approle_defaults = _yaml(DEFAULTS / "07f-workstation-approles.yml")
        rotation_names_expression = _yaml(
            DEFAULTS / "05c-terrakube-and-remaining-domain-names.yml"
        )["openbao_secrets_domain_approle_names"]
        rotation_values = {}
        for defaults_file in (
            "05b-domain-policy-approle-names.yml",
            "05c-terrakube-and-remaining-domain-names.yml",
            "05c-ai-agent-names.yml",
            "05-ssh-ca-engine.yml",
        ):
            rotation_values.update(_yaml(DEFAULTS / defaults_file))
        resolver = Templar(loader=DataLoader())
        resolver.available_variables = {**rotation_values, **self.edge}
        rotated_cribl_roles = [
            resolver.template(trust_as_template(role))
            for role in self.edge["openbao_cribl_edge_mac_approle_names"]
        ]
        rotation_values.update(
            openbao_cribl_edge_mac_approle_names=rotated_cribl_roles,
            openbao_hermes_private_agent_secret_id_cidr="",
        )
        rotated_roles = _render(rotation_names_expression, rotation_values)

        self.assertIn("OPENBAO_WORKSTATION_CIDRS", cidr_defaults["openbao_workstation_cidrs"])
        self.assertEqual(
            cidr_defaults["openbao_approle_cidr_classes"]["workstation"],
            "{{ openbao_workstation_cidrs }}",
        )
        self.assertEqual(_seconds(ttl_defaults["openbao_approle_token_ttl"]), 3600)
        self.assertEqual(_seconds(ttl_defaults["openbao_approle_token_max_ttl"]), 14400)

        roles = approle_defaults["openbao_workstation_approles"]
        for suffix in ("a", "b"):
            role_name = f"cribl-edge-mac-{suffix}"
            with self.subTest(role=role_name):
                row = next(
                    role
                    for role in roles
                    if role.get("name") == f"{{{{ openbao_cribl_edge_mac_{suffix}_approle_name }}}}"
                )
                self.assertEqual(row["secret_id_num_uses"], 100)
                self.assertEqual(
                    ttl_defaults["openbao_approle_secret_id_ttl_overrides"][role_name],
                    "{{ openbao_rotated_domain_secret_id_ttl }}",
                )
                self.assertEqual(_seconds(ttl_defaults["openbao_rotated_domain_secret_id_ttl"]), 129600)
                self.assertEqual(cidr_defaults["openbao_approle_cidr_class_overrides"][role_name], "workstation")
                self.assertNotIn(role_name, rotated_roles)

    def test_bounds_contract_rejects_unbounded_or_broader_values(self):
        def valid(secret_id_ttl: str, uses: int, cidr_class: str) -> bool:
            try:
                finite_ttl = _seconds(secret_id_ttl) > 0
            except AssertionError:
                finite_ttl = False
            return finite_ttl and uses == 100 and cidr_class == "workstation"

        self.assertFalse(valid("0s", 100, "workstation"))
        self.assertFalse(valid("36h", 0, "workstation"))
        self.assertFalse(valid("36h", 100, "machine_or_workstation"))


if __name__ == "__main__":
    unittest.main()
