"""The domain->groups scoping map names only real domains and real groups.

playbooks/site/00-load-and-telemetry.yml's "Pre-fetch resource-domain
secrets from OpenBao" play declares openbao_secrets_domain_groups (which
domains this run's hosts need, per group) as hand-maintained data,
independent of the domain list in roles/openbao_secrets/defaults/main/ and
of the group names in that same play's own `hosts:` pattern plus the two
small scope-detection plays immediately above it (media_group; the deadman
watchdog group set). A typo or a renamed/removed domain or group on either
side would make roles/openbao_secrets/tasks/narrow_domains.yml silently
decide a domain is never needed -- exactly the empty-secret-over-a-live-one
failure class this scoping was built not to reintroduce.

The functional behaviour of the narrowing gate itself is proven against the
production task file in tests/openbao_secrets/verify_domain_scoping.yml;
this test only pins the real map's own vocabulary.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK = ROOT / "playbooks" / "site" / "00-load-and-telemetry.yml"
DOMAIN_GROUPS_FILE = ROOT / "playbooks" / "site" / "vars" / "openbao_secrets_domain_groups.yml"
DOMAINS_FILE = ROOT / "roles" / "openbao_secrets" / "defaults" / "main" / "01-domains.yml"

PREFETCH_PLAY_NAME = "Pre-fetch resource-domain secrets from OpenBao"
MEDIA_SCOPE_GROUP = "media_group"
DEADMAN_SCOPE_GROUPS = {
    "technitium_dns_group",
    "traefik_group",
    "haproxy_group",
    "openbao_group",
    "docker_vms",
}


def _load_plays() -> list[dict]:
    with PLAYBOOK.open() as f:
        return yaml.safe_load(f)


def _prefetch_play() -> dict:
    plays = _load_plays()
    for play in plays:
        if play.get("name") == PREFETCH_PLAY_NAME:
            return play
    raise AssertionError(f"could not find the {PREFETCH_PLAY_NAME!r} play")


def _hosts_pattern_groups(hosts_value: str) -> set[str]:
    return {group for group in re.split(r"[\s:]+", hosts_value) if group}


def _domain_groups() -> dict:
    with DOMAIN_GROUPS_FILE.open() as f:
        return yaml.safe_load(f)["openbao_secrets_domain_groups"]


def _declared_domain_names() -> set[str]:
    with DOMAINS_FILE.open() as f:
        data = yaml.safe_load(f)
    return {domain["name"] for domain in data["openbao_secrets_domains"]}


def test_every_mapped_domain_is_a_real_declared_domain():
    mapped_domains = set(_domain_groups().keys())
    declared_domains = _declared_domain_names()

    unknown = mapped_domains - declared_domains
    assert not unknown, (
        f"openbao_secrets_domain_groups names domain(s) {sorted(unknown)} that "
        f"are not in roles/openbao_secrets/defaults/main/01-domains.yml's "
        f"openbao_secrets_domains ({sorted(declared_domains)}) -- a typo here "
        "makes narrow_domains.yml silently ignore that entry."
    )


def test_every_mapped_group_is_reachable_by_the_scoping_gate():
    play = _prefetch_play()
    in_play_groups = _hosts_pattern_groups(play["hosts"])
    reachable_groups = in_play_groups | {MEDIA_SCOPE_GROUP} | DEADMAN_SCOPE_GROUPS

    all_mapped_groups: set[str] = set()
    for groups in _domain_groups().values():
        all_mapped_groups.update(groups)

    unreachable = all_mapped_groups - reachable_groups
    assert not unreachable, (
        f"openbao_secrets_domain_groups names group(s) {sorted(unreachable)} "
        "that the scoping gate can never see as active: they are neither in "
        "the pre-fetch play's own `hosts:` pattern nor one of the two "
        "out-of-play scope groups (media_group, the deadman watchdog set) "
        "detected by the plays immediately above it -- any domain mapped "
        "ONLY to such a group would never be fetched, on any run."
    )


def test_domains_with_no_traced_consumer_are_left_unmapped_not_guessed():
    # observability and local-cloud have no consumer anywhere in this repo
    # today (see the map's own comment) -- they must be ABSENT from the map
    # (the "always fetch" safe default), never present with a guessed,
    # unverified group list.
    mapped_domains = set(_domain_groups().keys())
    for unconsumed in ("observability", "local-cloud"):
        assert unconsumed not in mapped_domains, (
            f"{unconsumed!r} has no traced consumer in this repo and must stay "
            "out of openbao_secrets_domain_groups so it is always fetched, not "
            "gated on a guessed group list"
        )


# ---------------------------------------------------------------------------
# Reverse direction: does every domain a pre-fetch play group ACTUALLY
# consumes appear in the map? The tests above only catch a map entry that
# points at something unreal; they can't catch a map entry that is simply
# missing. This walks the real evidence trail instead (group_vars + the
# roles each group's own play(s) run) and flags any (domain, group) pair it
# finds that the map doesn't declare.
#
# Scope, matching narrow_domains.yml's own scoping mechanism: only roles
# named directly by a `roles:` list or a top-level `include_role`/
# `import_role` task in a play whose `hosts:` contains the group. A role
# that reaches a domain fact only via a further include_role/import_role
# inside ANOTHER role is not followed -- see the module docstring above for
# why (narrow_domains.yml itself doesn't need that either).
# ---------------------------------------------------------------------------

SITE_DIR = ROOT / "playbooks" / "site"
ROLES_DIR = ROOT / "roles"
GROUP_VARS_DIR = ROOT / "inventory" / "group_vars"


def _fact_name_for_domain(domain: str) -> str:
    return f"bao_{domain.replace('-', '_')}_secrets"


def _references_domain(text: str, domain: str) -> bool:
    return re.search(rf"\b{re.escape(_fact_name_for_domain(domain))}\b", text) is not None


def _iter_tasks(tasks) -> list[dict]:
    out = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        out.append(task)
        for key in ("block", "rescue", "always"):
            out.extend(_iter_tasks(task.get(key)))
    return out


def _roles_named_in_play(play: dict) -> set[str]:
    names: set[str] = set()
    for entry in play.get("roles") or []:
        name = entry.get("role") if isinstance(entry, dict) else entry
        if name:
            names.add(name)
    tasks = []
    for key in ("pre_tasks", "tasks", "post_tasks"):
        tasks.extend(_iter_tasks(play.get(key)))
    for task in tasks:
        for key in ("ansible.builtin.include_role", "ansible.builtin.import_role", "include_role", "import_role"):
            spec = task.get(key)
            if isinstance(spec, dict) and spec.get("name"):
                names.add(spec["name"])
    return names


def _plays_targeting_group(group: str) -> list[dict]:
    # Excludes the pre-fetch play itself: its own `hosts:` lists every group
    # only because it is the play DOING the fetch, and its include_role of
    # openbao_secrets naturally mentions every domain name generically --
    # that is not evidence any one of those groups consumes a domain.
    matches = []
    for playbook in sorted(SITE_DIR.glob("*.yml")):
        plays = yaml.safe_load(playbook.read_text())
        if not isinstance(plays, list):
            continue
        for play in plays:
            if not isinstance(play, dict) or "hosts" not in play:
                continue
            if play.get("name") == PREFETCH_PLAY_NAME:
                continue
            groups = {g.lstrip("!") for g in _hosts_pattern_groups(str(play["hosts"]))}
            if group in groups:
                matches.append(play)
    return matches


def _domains_consumed_by_group(group: str, declared_domains: set[str]) -> set[str]:
    texts = []
    group_vars_file = GROUP_VARS_DIR / f"{group}.yml"
    if group_vars_file.is_file():
        texts.append(group_vars_file.read_text())
    for play in _plays_targeting_group(group):
        for role in _roles_named_in_play(play):
            role_dir = ROLES_DIR / role
            if not role_dir.is_dir():
                continue  # e.g. an external collection FQCN -- not resolvable locally
            for path in role_dir.rglob("*"):
                if path.is_file():
                    texts.append(path.read_text(errors="ignore"))
    return {d for d in declared_domains if any(_references_domain(t, d) for t in texts)}


def test_every_domain_a_group_actually_consumes_is_declared_in_the_map():
    play = _prefetch_play()
    in_play_groups = _hosts_pattern_groups(play["hosts"])
    declared_domains = _declared_domain_names()
    domain_groups = _domain_groups()

    missing = sorted(
        (domain, group)
        for group in in_play_groups
        for domain in _domains_consumed_by_group(group, declared_domains)
        if group not in domain_groups.get(domain, [])
    )
    assert not missing, (
        f"these (domain, group) pairs are actually consumed (per group_vars/role "
        f"evidence) but missing from openbao_secrets_domain_groups: {missing} -- "
        "narrow_domains.yml would silently skip fetching that domain for that group"
    )
