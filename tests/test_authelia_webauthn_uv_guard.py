"""Guard Authelia's experimental passkey UV behavior and rendered WebAuthn policy."""

from pathlib import Path

from jinja2 import Environment, StrictUndefined
import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "roles/authelia/defaults/main/00-core.yml"
TEMPLATE = ROOT / "roles/authelia/templates/configuration.yml.j2"
UPSTREAM_WEBAUTHN_URL = "https://www.authelia.com/configuration/second-factor/webauthn/"


def _load_defaults_and_render_webauthn():
    defaults = yaml.safe_load(DEFAULTS.read_text())
    lines = TEMPLATE.read_text().splitlines()
    section_start = lines.index("webauthn:")
    section_end = next(
        index
        for index in range(section_start + 1, len(lines))
        if lines[index] and not lines[index][0].isspace()
    )
    section = "\n".join(lines[section_start:section_end])
    rendered = Environment(undefined=StrictUndefined).from_string(section).render(**defaults)
    return defaults, yaml.safe_load(rendered)["webauthn"]


def test_experimental_uv_two_factors_flag_version_is_reviewed():
    defaults, webauthn = _load_defaults_and_render_webauthn()

    if webauthn.get("experimental_enable_passkey_uv_two_factors") is True:
        assert defaults["authelia_version"] == defaults[
            "authelia_webauthn_uv_two_factors_reviewed_version"
        ], (
            f"{UPSTREAM_WEBAUTHN_URL}: reread the WebAuthn page, confirm the "
            f"experimental flag still starts in Authelia {defaults['authelia_version']}, "
            "then bump authelia_webauthn_uv_two_factors_reviewed_version."
        )


def test_rendered_passkey_requires_user_verification():
    _, webauthn = _load_defaults_and_render_webauthn()

    assert webauthn["enable_passkey_login"] is True
    assert webauthn["selection_criteria"]["user_verification"] == "required"
