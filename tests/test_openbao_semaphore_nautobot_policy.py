"""Contract for the Nautobot pipeline read grant on the Semaphore policy."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMAPHORE_POLICY = ROOT / "roles/openbao/templates/semaphore-policy.hcl.j2"
ANSIBLE_CONVERGE_POLICY = (
    ROOT / "roles/openbao/templates/ansible-converge-policy.hcl.j2"
)
PIPELINE_PATH = 'path "{{ openbao_kv_mount }}/data/apps/nautobot/pipeline" {'
PIPELINE_READ = PIPELINE_PATH + '\n  capabilities = ["read"]\n}'


def test_semaphore_has_one_exact_read_grant_for_the_pipeline_token() -> None:
    semaphore_policy = SEMAPHORE_POLICY.read_text(encoding="utf-8")
    assert semaphore_policy.count(PIPELINE_PATH) == 1
    assert PIPELINE_READ in semaphore_policy
    assert (
        'path "{{ openbao_kv_mount }}/data/apps/nautobot/*" {' not in semaphore_policy
    )
    assert (
        'path "{{ openbao_kv_mount }}/data/apps/nautobot/sync-write" {'
        not in semaphore_policy
    )
    assert PIPELINE_PATH not in ANSIBLE_CONVERGE_POLICY.read_text(encoding="utf-8")
