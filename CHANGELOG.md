# Changelog

## [0.15.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.14.0...v0.15.0) (2026-10-13)


### Features

* **openbao:** let the semaphore role mint the jpe-cribl read token ([#142](https://github.com/dryvist/ansible-secrets-management/issues/142)) ([296a0c7](https://github.com/dryvist/ansible-secrets-management/commit/296a0c786bf86323aa070374f596e012f516172a))

## [0.14.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.13.0...v0.14.0) (2026-10-13)


### Features

* **openbao:** add sandbox agent AppRoles and identity classes ([#128](https://github.com/dryvist/ansible-secrets-management/issues/128)) ([1fbcca7](https://github.com/dryvist/ansible-secrets-management/commit/1fbcca78cf78532177dde2ebe3ed9cbce6fdd99c))


### Bug Fixes

* **openbao:** keep the internal Z.ai copy until the external leaf is seeded ([#139](https://github.com/dryvist/ansible-secrets-management/issues/139)) ([d7f28eb](https://github.com/dryvist/ansible-secrets-management/commit/d7f28eb5f6df9179d9f1835b4bb3b43142e7b9d9))

## [0.13.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.12.0...v0.13.0) (2026-10-13)


### Features

* **openbao:** add the hermes orchestrator generated app secret ([#129](https://github.com/dryvist/ansible-secrets-management/issues/129)) ([dba4b84](https://github.com/dryvist/ansible-secrets-management/commit/dba4b84927d706a3cc32fafaebe764bc4ef97f62))
* **openbao:** grant the apps read for the hermes orchestrator leaf ([a679589](https://github.com/dryvist/ansible-secrets-management/commit/a6795893cc95d850d049aaf3d24eb4e06d91ec74))

## [0.12.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.11.0...v0.12.0) (2026-10-12)


### Features

* **openbao:** add per-organisation repo-create permission sets ([7742019](https://github.com/dryvist/ansible-secrets-management/commit/7742019de807a0ce1fdd7f51f4cf432a2a88b384))
* **openbao:** add per-organisation repo-create permission sets ([#123](https://github.com/dryvist/ansible-secrets-management/issues/123)) ([1ea7e1a](https://github.com/dryvist/ansible-secrets-management/commit/1ea7e1af92f713b8056b88c8187d6dcc4d2043ad))

## [0.11.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.10.1...v0.11.0) (2026-10-12)


### Features

* **openbao:** add the azure-iac-admin AppRole and policy ([#119](https://github.com/dryvist/ansible-secrets-management/issues/119)) ([e2e5065](https://github.com/dryvist/ansible-secrets-management/commit/e2e5065a388f861d480ff9a2a0d7a6f499808a32))

## [0.10.1](https://github.com/dryvist/ansible-secrets-management/compare/v0.10.0...v0.10.1) (2026-10-12)


### Bug Fixes

* **openbao:** send subscription_id in the Azure engine config ([35d95a3](https://github.com/dryvist/ansible-secrets-management/commit/35d95a315063ef0f619fdc4bb5f33006236ecddd))
* **openbao:** send subscription_id in the Azure engine config ([#114](https://github.com/dryvist/ansible-secrets-management/issues/114)) ([f95dcaf](https://github.com/dryvist/ansible-secrets-management/commit/f95dcafc1918ded4838293c8e802d2fae61d8dbb))

## [0.10.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.9.1...v0.10.0) (2026-10-12)


### Features

* **openbao:** add per-engine component tags ([#105](https://github.com/dryvist/ansible-secrets-management/issues/105)) ([a883ff2](https://github.com/dryvist/ansible-secrets-management/commit/a883ff2eba591796c68c28ac23bdb4555478acf2))
* **openbao:** keep plugin staging tasks unchanged ([446d55d](https://github.com/dryvist/ansible-secrets-management/commit/446d55d3461eb12313d47aaa3af9e03542cfe487))


### Bug Fixes

* **openbao:** treat an empty Azure engine client_id as missing config ([04f63ec](https://github.com/dryvist/ansible-secrets-management/commit/04f63ecf5291bc3dd8b2f36bba6ef094b9787bd0))
* **openbao:** treat an empty Azure engine client_id as missing config ([#107](https://github.com/dryvist/ansible-secrets-management/issues/107)) ([a85ff41](https://github.com/dryvist/ansible-secrets-management/commit/a85ff412ad5b4cbf86ac36dc76feb925485e273e))

## [0.9.1](https://github.com/dryvist/ansible-secrets-management/compare/v0.9.0...v0.9.1) (2026-10-12)


### Bug Fixes

* **openbao:** add the Azure engine path to ai-admin-policy.hcl.j2 ([#101](https://github.com/dryvist/ansible-secrets-management/issues/101)) ([9c839cb](https://github.com/dryvist/ansible-secrets-management/commit/9c839cba7da149b7498b7af6e174179e298952af))
* **openbao:** grant the admin policy the Azure engine mount ([0ee360c](https://github.com/dryvist/ansible-secrets-management/commit/0ee360c28e8b3f4c638c6e53a69030818b84850d))

## [0.9.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.8.0...v0.9.0) (2026-10-12)


### Features

* **openbao:** configure the Azure secrets engine ([#93](https://github.com/dryvist/ansible-secrets-management/issues/93)) ([3eb1f05](https://github.com/dryvist/ansible-secrets-management/commit/3eb1f05abf60cb5564c4bab44df3216d455eb888))


### Bug Fixes

* **openbao:** end AppRole rotation before credential use in check mode ([#89](https://github.com/dryvist/ansible-secrets-management/issues/89)) ([6a84836](https://github.com/dryvist/ansible-secrets-management/commit/6a848366c67eb2eaf36b5f4b50583cccba903110))

## [0.8.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.7.1...v0.8.0) (2026-10-12)


### Features

* **openbao_secrets:** drop owned MCP paths from non-owner fetch domains ([#78](https://github.com/dryvist/ansible-secrets-management/issues/78)) ([499d28d](https://github.com/dryvist/ansible-secrets-management/commit/499d28dedcc3b6c27a994cb0f24209ca324ca1aa))
* **openbao:** add azure secrets engine with roles from environment ([#88](https://github.com/dryvist/ansible-secrets-management/issues/88)) ([1242bf2](https://github.com/dryvist/ansible-secrets-management/commit/1242bf2bd980218d54200e6d467d4432c5e1177c))
* **openbao:** add router and gateway reader roles for roster agent keys ([#75](https://github.com/dryvist/ansible-secrets-management/issues/75)) ([39f1a6e](https://github.com/dryvist/ansible-secrets-management/commit/39f1a6ede05ea360d6db6b64684b3242e23a79fd))
* **openbao:** derive roster agent AppRoles and policies ([#73](https://github.com/dryvist/ansible-secrets-management/issues/73)) ([deaaf89](https://github.com/dryvist/ansible-secrets-management/commit/deaaf898e1d8ecae6a21bc0aaaf7ff487c038699))
* **openbao:** drop consumer MCP grants once a roster agent owns the system ([#77](https://github.com/dryvist/ansible-secrets-management/issues/77)) ([5322ffb](https://github.com/dryvist/ansible-secrets-management/commit/5322ffb6e4b681c389d173e0d3c918bf61b47c3d))
* **openbao:** generate an A2A bearer token for the assistant guest ([eab9d97](https://github.com/dryvist/ansible-secrets-management/commit/eab9d97c8ad795574ae23c8883a7cf44d709bd85))
* **openbao:** generate an A2A bearer token for the assistant guest ([#70](https://github.com/dryvist/ansible-secrets-management/issues/70)) ([1539774](https://github.com/dryvist/ansible-secrets-management/commit/1539774706d7f0fb6cb2edb7ff739ceb761f66df))
* **openbao:** leave installation_id unpinned in the write policies ([#83](https://github.com/dryvist/ansible-secrets-management/issues/83)) ([91bb0a2](https://github.com/dryvist/ansible-secrets-management/commit/91bb0a25898a9f13f74e4916336bc8b71c5c9b3c))
* **openbao:** leave installation_id unpinned in the write policies ([#83](https://github.com/dryvist/ansible-secrets-management/issues/83)) ([e1f8f0f](https://github.com/dryvist/ansible-secrets-management/commit/e1f8f0fadb2f41b3a934374523b385d1bf858823))
* **openbao:** provision Qwen Code router key ([#66](https://github.com/dryvist/ansible-secrets-management/issues/66)) ([1d9b9fb](https://github.com/dryvist/ansible-secrets-management/commit/1d9b9fb6c71fec6c5a08b8eefe100ec8c78c93c2))
* **openbao:** seed per-agent router and gateway keys outside the apps grant ([#74](https://github.com/dryvist/ansible-secrets-management/issues/74)) ([243deb1](https://github.com/dryvist/ansible-secrets-management/commit/243deb1cdbbf4817a2da90d5d3f4293ac08b9ae0))
* **openbao:** serve extra installations on the everyday GitHub mount ([#65](https://github.com/dryvist/ansible-secrets-management/issues/65)) ([cdc383e](https://github.com/dryvist/ansible-secrets-management/commit/cdc383e3d34cee6cd115253e2ea7eea10d7a136d))


### Bug Fixes

* **openbao_secrets:** run the endpoint probe in check mode ([#64](https://github.com/dryvist/ansible-secrets-management/issues/64)) ([9c40b51](https://github.com/dryvist/ansible-secrets-management/commit/9c40b51b9fbaaef6b0a455639982c0f818b3f22f))
* **openbao:** do not schedule the ci-resolver policy while its repository list is empty ([7152318](https://github.com/dryvist/ansible-secrets-management/commit/7152318a71fe4a20e626a11526674e36a3ce14fd))
* **openbao:** do not schedule the ci-resolver policy while its repository list is empty ([8749cec](https://github.com/dryvist/ansible-secrets-management/commit/8749cec03fe04cad78e65acb04edda3da58944e6))
* **openbao:** do not schedule the ci-resolver policy while its repository list is empty ([#84](https://github.com/dryvist/ansible-secrets-management/issues/84)) ([09de305](https://github.com/dryvist/ansible-secrets-management/commit/09de30587543c5e90357f6f8d016cdbdb4c02fa4))
* **openbao:** gate the rotation roster load on live roster readers ([#87](https://github.com/dryvist/ansible-secrets-management/issues/87)) ([54419b2](https://github.com/dryvist/ansible-secrets-management/commit/54419b24a91831750310f4b3e01922b67fdd0db4))
* **openbao:** generate the assistant guest router key and grant its apps path ([#67](https://github.com/dryvist/ansible-secrets-management/issues/67)) ([ea24f28](https://github.com/dryvist/ansible-secrets-management/commit/ea24f28cbd5ff926b46a4d06e517da2e8b84ea62))
* **openbao:** generate the donna router key and grant its apps path ([ea24f28](https://github.com/dryvist/ansible-secrets-management/commit/ea24f28cbd5ff926b46a4d06e517da2e8b84ea62))
* **openbao:** leave write installation_id unpinned and skip the empty ci-resolver policy ([#85](https://github.com/dryvist/ansible-secrets-management/issues/85)) ([147b771](https://github.com/dryvist/ansible-secrets-management/commit/147b771e8c7cf3aa3680e087bda693835bf15f82))
* **openbao:** load the agent roster before rotating AppRole secret IDs ([f7259f7](https://github.com/dryvist/ansible-secrets-management/commit/f7259f7aebfd4962a1ce1d34888df7e581b4c341))
* **openbao:** load the agent roster before rotating AppRole secret IDs ([#82](https://github.com/dryvist/ansible-secrets-management/issues/82)) ([48cc113](https://github.com/dryvist/ansible-secrets-management/commit/48cc11363d2f74f4814270319c51c20d7692d4d6))
* **openbao:** require the snapshot unit and skip the restart in check mode ([e7007ef](https://github.com/dryvist/ansible-secrets-management/commit/e7007efbbc167acd8e65b29f66134211aea9f8dd))
* **openbao:** run the init path's read-only probes in check mode ([#71](https://github.com/dryvist/ansible-secrets-management/issues/71)) ([5e37787](https://github.com/dryvist/ansible-secrets-management/commit/5e377873d8bb4ec0f6f8678ee562007f0b3fd435))
* **openbao:** snapshot and restart on a version upgrade ([57ea8ca](https://github.com/dryvist/ansible-secrets-management/commit/57ea8ca17dd597e842bcc23a183eb93416b4ebba))
* **openbao:** snapshot and restart on a version upgrade ([#90](https://github.com/dryvist/ansible-secrets-management/issues/90)) ([29994ea](https://github.com/dryvist/ansible-secrets-management/commit/29994ea3ae67fe8b220ff170301067e4def66a4c))

## [0.7.1](https://github.com/dryvist/ansible-secrets-management/compare/v0.7.0...v0.7.1) (2026-10-11)


### Bug Fixes

* **openbao:** count an empty JSON list as absent in the secret-age audit ([#60](https://github.com/dryvist/ansible-secrets-management/issues/60)) ([8c454be](https://github.com/dryvist/ansible-secrets-management/commit/8c454bedee94672ba097826d7cb29d08327bab7c))

## [0.7.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.6.0...v0.7.0) (2026-10-11)


### Features

* **openbao:** add the ci-resolver GitHub identity ([#53](https://github.com/dryvist/ansible-secrets-management/issues/53)) ([7eca696](https://github.com/dryvist/ansible-secrets-management/commit/7eca69625ada89e662c8de7fe170921e69988ac3))

## [0.6.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.5.0...v0.6.0) (2026-10-11)


### Features

* **openbao:** add the ai-admin-guard deny overlay ([4b13726](https://github.com/dryvist/ansible-secrets-management/commit/4b137261d56e20bce67011145c75ffeae34aef06))
* **openbao:** add the github-enterprise-owner mount and the ai-admin-guard overlay ([#48](https://github.com/dryvist/ansible-secrets-management/issues/48)) ([a1b7dc6](https://github.com/dryvist/ansible-secrets-management/commit/a1b7dc66bb398fde7408478b08ebd0be2c0db5e7))
* **openbao:** add the github-enterprise-owner token mount ([e4f413b](https://github.com/dryvist/ansible-secrets-management/commit/e4f413b8c585926c9f8e37a77fb5af7c55ea7832))


### Bug Fixes

* **openbao:** attach ai-admin-guard to ai-admin-session only ([b5a8694](https://github.com/dryvist/ansible-secrets-management/commit/b5a86946a7b5da118eee8bce1272acd29932d837))

## [0.5.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.4.0...v0.5.0) (2026-10-11)


### Features

* **openbao:** add GitHub Enterprise App mounts and inert tiers ([#30](https://github.com/dryvist/ansible-secrets-management/issues/30)) ([278493a](https://github.com/dryvist/ansible-secrets-management/commit/278493a9e3732616fa41d0160465ac37b3830268))
* **openbao:** rotate the agent-workstation secret_id on the domain schedule ([#41](https://github.com/dryvist/ansible-secrets-management/issues/41)) ([fa5bc47](https://github.com/dryvist/ansible-secrets-management/commit/fa5bc4772f05bb1a33d8abed9de81c8bed57371c))


### Bug Fixes

* **openbao:** exclude the plane token's policies from reconcile ([#43](https://github.com/dryvist/ansible-secrets-management/issues/43)) ([164aaff](https://github.com/dryvist/ansible-secrets-management/commit/164aaff0cdddf3fd233ec9d1b71eeabe90ba8468))

## [0.4.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.3.1...v0.4.0) (2026-10-11)


### Features

* **authelia:** add OpenBao elevation device-code clients and elevate policy ([#24](https://github.com/dryvist/ansible-secrets-management/issues/24)) ([7fa9ed2](https://github.com/dryvist/ansible-secrets-management/commit/7fa9ed2df1dbe47c65fe3d70109bca3287a2a1c0))
* **openbao:** add the Authelia JWT elevation roles and a 1h work-identity token ([#25](https://github.com/dryvist/ansible-secrets-management/issues/25)) ([7127d8b](https://github.com/dryvist/ansible-secrets-management/commit/7127d8b0dac6dbe1b7c458fb11569cbcec99c242))
* **openbao:** attach the ai-apply-all policy set to agent-workstation ([#22](https://github.com/dryvist/ansible-secrets-management/issues/22)) ([b0c948c](https://github.com/dryvist/ansible-secrets-management/commit/b0c948c2c31f1e4a0dd547cb90d4cc34055ae6a1))
* **scripts:** add a run wrapper for the controller-side playbooks ([#26](https://github.com/dryvist/ansible-secrets-management/issues/26)) ([f638da2](https://github.com/dryvist/ansible-secrets-management/commit/f638da2690b05571331a1c62e23235c1fb75afcb))

## [0.3.1](https://github.com/dryvist/ansible-secrets-management/compare/v0.3.0...v0.3.1) (2026-10-10)


### Bug Fixes

* **openbao:** accept spent reconcile secret_id on accessor destroy ([#10](https://github.com/dryvist/ansible-secrets-management/issues/10)) ([e5629ab](https://github.com/dryvist/ansible-secrets-management/commit/e5629ab6110ee72858161ac903da49e4f377de41))

## [0.3.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.2.0...v0.3.0) (2026-10-10)


### ⚠ BREAKING CHANGES

* **openbao:** drop the github-write repository allowlist ([#2528](https://github.com/dryvist/ansible-secrets-management/issues/2528))

### Features

* **openbao:** drop the github-write repository allowlist ([#2528](https://github.com/dryvist/ansible-secrets-management/issues/2528)) ([3cecb78](https://github.com/dryvist/ansible-secrets-management/commit/3cecb7860325c3c2a18fe2e62f0f7492537444d6))
* **openbao:** port six ansible-proxmox-apps commits ([5ab3a03](https://github.com/dryvist/ansible-secrets-management/commit/5ab3a03dc1936310b89f94b1e4281f6fc36f5cfe))
* **openbao:** split github-work into read and write identities ([#2523](https://github.com/dryvist/ansible-secrets-management/issues/2523)) ([d7933e5](https://github.com/dryvist/ansible-secrets-management/commit/d7933e50ad2e60e91e3aa365a414841fab3e9302))


### Bug Fixes

* **openbao:** compare /32 AppRole binds without the prefix length ([#2526](https://github.com/dryvist/ansible-secrets-management/issues/2526)) ([dbf96e2](https://github.com/dryvist/ansible-secrets-management/commit/dbf96e2112e7bb2ed3c12efdc19bbf8cb4142cf9))
* **openbao:** refuse to render the voter-health env file without a HEC token ([#2531](https://github.com/dryvist/ansible-secrets-management/issues/2531)) ([34502b9](https://github.com/dryvist/ansible-secrets-management/commit/34502b9aab8c2cf29fbe84348dda472e46fb1ab6))
* **openbao:** unlimited secret_id uses for local-llm, hermes and ai-donna ([#2524](https://github.com/dryvist/ansible-secrets-management/issues/2524)) ([7d89ed6](https://github.com/dryvist/ansible-secrets-management/commit/7d89ed6b4a1b47ecc8ead52c5212c2c0063dedd2))

## [0.2.0](https://github.com/dryvist/ansible-secrets-management/compare/v0.1.0...v0.2.0) (2026-10-10)


### Features

* add GitHub agent flow identities ([7d5b714](https://github.com/dryvist/ansible-secrets-management/commit/7d5b714027b3c2602fed00272f6e3db9f0c338b4))
* **agent_sandbox:** host dispatcher with terminal sessions and a login check ([c7def81](https://github.com/dryvist/ansible-secrets-management/commit/c7def81b3fda3a9814b47e1c80568fb46c55a27e))
* **agent_sandbox:** install the pinned host dispatcher with terminal sessions ([01bc2ee](https://github.com/dryvist/ansible-secrets-management/commit/01bc2ee63917eb4e85db7ea61bf5c5f6e62c313b))
* **agent_sandbox:** provide dispatcher alert settings ([#2382](https://github.com/dryvist/ansible-secrets-management/issues/2382)) ([cc5da81](https://github.com/dryvist/ansible-secrets-management/commit/cc5da8120ecb9e3e64bc7c3a3781c86ec92aaff5))
* **authelia,dashboards:** LiteLLM OIDC client + ingress url_path on board links ([3cc1d67](https://github.com/dryvist/ansible-secrets-management/commit/3cc1d67eb0146b622863b82deaf9871d69fc7e53))
* **authelia,openbao:** seed a UI check service user with TOTP ([bcf07ec](https://github.com/dryvist/ansible-secrets-management/commit/bcf07ec9565c1f85d813f99e770f9484af73b627))
* **authelia,syslog:** narrow Semaphore API bypass, ship iac-platform logs ([#1680](https://github.com/dryvist/ansible-secrets-management/issues/1680)) ([f9a1d09](https://github.com/dryvist/ansible-secrets-management/commit/f9a1d09095a5827ae2a0f91ed2ea80ff52d6851e))
* **authelia:** add run-UI and federated OIDC clients, reconcile operator groups ([#1651](https://github.com/dryvist/ansible-secrets-management/issues/1651)) ([2f43961](https://github.com/dryvist/ansible-secrets-management/commit/2f439614b3e77a4ca20c48edd377fc511165e782))
* **authelia:** declare litellm OIDC client ([d455875](https://github.com/dryvist/ansible-secrets-management/commit/d45587544980d9004d69c8a072a7b0fcd12c5a30))
* **authelia:** exempt the metrics store ingest paths from the forward-auth gate ([#1899](https://github.com/dryvist/ansible-secrets-management/issues/1899)) ([f37e548](https://github.com/dryvist/ansible-secrets-management/commit/f37e548b28f90a90f36573fdbf226f061caa61da))
* **authelia:** register Homarr and Langfuse OIDC clients ([#1554](https://github.com/dryvist/ansible-secrets-management/issues/1554)) ([fad0a41](https://github.com/dryvist/ansible-secrets-management/commit/fad0a419df80c0630142ad90c5ea9da84e32fcd6))
* **authelia:** render litellm confidential client ([a46d68e](https://github.com/dryvist/ansible-secrets-management/commit/a46d68e6fb91a99f3326fe226ca40685a3083b87))
* **ci:** route the runner hosts and Molecule containers through the build caches ([9fe56e9](https://github.com/dryvist/ansible-secrets-management/commit/9fe56e9c13fadf572e58b68ce1a52b03b539c3bb))
* **ci:** route the runner hosts and Molecule containers through the build caches ([1ebc5f5](https://github.com/dryvist/ansible-secrets-management/commit/1ebc5f5182c83681020aa5d5388112caf1927ea7))
* **config:** add exact path entries ([5663df7](https://github.com/dryvist/ansible-secrets-management/commit/5663df74122ea0b08572dba7ad322c1dd0660ff5))
* **config:** add exact path entries ([2eec5d8](https://github.com/dryvist/ansible-secrets-management/commit/2eec5d81551c564b19512cf5beca96d4d70da64f))
* **cribl:** fan OTLP traces out to Arize Phoenix and register its OIDC client ([#1701](https://github.com/dryvist/ansible-secrets-management/issues/1701)) ([12a2c60](https://github.com/dryvist/ansible-secrets-management/commit/12a2c60f1ed13b4b216890d86d47a13417d8a798))
* **deadman:** report to Gatus external endpoints and Healthchecks by slug ([#1856](https://github.com/dryvist/ansible-secrets-management/issues/1856)) ([99b72fc](https://github.com/dryvist/ansible-secrets-management/commit/99b72fc4a2c23d52a4c2a1144edcc43c989b9a29))
* **defaults:** read estate-wide defaults from the secret store ([#1486](https://github.com/dryvist/ansible-secrets-management/issues/1486)) ([be03666](https://github.com/dryvist/ansible-secrets-management/commit/be0366608b2c8b8f388ea6fe97a2520c16601acb))
* **github_runner:** build the Molecule base image once per host and hand it to every scenario ([#1987](https://github.com/dryvist/ansible-secrets-management/issues/1987)) ([04d4b37](https://github.com/dryvist/ansible-secrets-management/commit/04d4b379956a9a59a6dca0bdc7e4d01b4f436188))
* **github_runner:** mint registration tokens from OpenBao, not a static PAT ([#1722](https://github.com/dryvist/ansible-secrets-management/issues/1722)) ([5360cf9](https://github.com/dryvist/ansible-secrets-management/commit/5360cf9057be305aa1b471c3bb5838e7ec57e8cb))
* **github_runner:** run Molecule on the upstream image, drop the custom build ([#2005](https://github.com/dryvist/ansible-secrets-management/issues/2005)) ([d5ad9d7](https://github.com/dryvist/ansible-secrets-management/commit/d5ad9d7a7418ae3ec354d59a24fbe9012fbe5555))
* **github-runner-arc:** add ARC pilot role (k3s + gha-runner-scale-set) ([21846ca](https://github.com/dryvist/ansible-secrets-management/commit/21846caff743a9d2058a73cf8eeb334b4b9bb5db))
* **github-runner-arc:** add ARC pilot role (k3s + gha-runner-scale-set) ([2ef8b6d](https://github.com/dryvist/ansible-secrets-management/commit/2ef8b6d44ca440d0eeb32a51f7e9a53da90823b6))
* **glance:** add Network + Media page and wall kiosk bypass ([#2212](https://github.com/dryvist/ansible-secrets-management/issues/2212)) ([0471738](https://github.com/dryvist/ansible-secrets-management/commit/04717381b250c60c4bcb3224e1c3661455c8dc51))
* **glance:** enable the deployment-profile tile with a generated router key ([#2449](https://github.com/dryvist/ansible-secrets-management/issues/2449)) ([177c3a5](https://github.com/dryvist/ansible-secrets-management/commit/177c3a54e34b583fbb30e0ac78c057e795fe48c0))
* **grafana:** sign in through Authelia SSO ([#1655](https://github.com/dryvist/ansible-secrets-management/issues/1655)) ([a89453e](https://github.com/dryvist/ansible-secrets-management/commit/a89453e1c79e87b823b55b82fb7b2d6c28b633de))
* **healthchecks_docker:** replace the dead email channel with native ntfy ([#1849](https://github.com/dryvist/ansible-secrets-management/issues/1849)) ([e4ae1ac](https://github.com/dryvist/ansible-secrets-management/commit/e4ae1acd88204ab94889575d668d0f3d76017707))
* **homarr:** add the homarr-v2 instance with declarative boards ([#2278](https://github.com/dryvist/ansible-secrets-management/issues/2278)) ([2bc7b39](https://github.com/dryvist/ansible-secrets-management/commit/2bc7b39490c9bda8613ec0d337330c077c5a8519))
* **homarr:** configure integrations from OpenBao over the Homarr API ([#1539](https://github.com/dryvist/ansible-secrets-management/issues/1539)) ([35a60df](https://github.com/dryvist/ansible-secrets-management/commit/35a60df9cfcc71d3bbd6cc5d5f19d8a16c1fb9a0))
* **mcp_gateway:** add MCP gateway role and OpenBao secret wiring ([b72592d](https://github.com/dryvist/ansible-secrets-management/commit/b72592dbf08d20da53c164ad7492364a747f857d))
* **mcp_gateway:** add MCP gateway role and OpenBao secret wiring ([6537d1f](https://github.com/dryvist/ansible-secrets-management/commit/6537d1f9d70e8c29eb8b8ec7517c76f9177f4eff))
* **metrics:** guest-level node_exporter, cAdvisor, PVE API exporter ([#1859](https://github.com/dryvist/ansible-secrets-management/issues/1859)) ([f63da4b](https://github.com/dryvist/ansible-secrets-management/commit/f63da4badd82dc2f1be876c37edf5c720634bd53))
* **ntfy:** alert hub with Slack fan-out and Zammad subscriber ([#1842](https://github.com/dryvist/ansible-secrets-management/issues/1842)) ([a62b13d](https://github.com/dryvist/ansible-secrets-management/commit/a62b13d38bb75e8d0886ee38541ceda66bcd6183))
* **ntfy:** fan every topic out to one all-alerts Slack channel ([#2276](https://github.com/dryvist/ansible-secrets-management/issues/2276)) ([d7128d5](https://github.com/dryvist/ansible-secrets-management/commit/d7128d5ca0373d68d83590a6d0f843e59aaa86f1))
* **ntfy:** provision a publish-only ai-jobs token ([6890f01](https://github.com/dryvist/ansible-secrets-management/commit/6890f0194f14d6d75e060db1fe8b973c0dd68ae4))
* **ntfy:** provision a publish-only ai-jobs token ([45f1508](https://github.com/dryvist/ansible-secrets-management/commit/45f15083a501a21be83aa3895fdba05e595e5d38))
* **object_storage:** mint scoped per-bucket RustFS IAM credentials ([#2200](https://github.com/dryvist/ansible-secrets-management/issues/2200)) ([0b53919](https://github.com/dryvist/ansible-secrets-management/commit/0b5391969f3ec183f01e78add71b30c0c6741f94))
* **openbao_secrets:** accept an operator AppRole pair as the last fallback ([#2101](https://github.com/dryvist/ansible-secrets-management/issues/2101)) ([96e7de7](https://github.com/dryvist/ansible-secrets-management/commit/96e7de70970373ac8347b86f21bbccd73cbf47b5))
* **openbao:** accept a pre-issued rotator token in the rotation play ([#2363](https://github.com/dryvist/ansible-secrets-management/issues/2363)) ([b339e98](https://github.com/dryvist/ansible-secrets-management/commit/b339e9840e6eabba79d687fe67343549d5f3e006))
* **openbao:** accept a pre-issued token as the reconcile identity ([#1783](https://github.com/dryvist/ansible-secrets-management/issues/1783)) ([5d846e3](https://github.com/dryvist/ansible-secrets-management/commit/5d846e36c0ea072b1084cdece79bde92d5112bda))
* **openbao:** add a read-only github-exporter GitHub App tier ([8f80147](https://github.com/dryvist/ansible-secrets-management/commit/8f8014736b8d625f23b20d913309aec659d198ca))
* **openbao:** add a seed-only entry point runnable in either auth mode ([#2118](https://github.com/dryvist/ansible-secrets-management/issues/2118)) ([086c809](https://github.com/dryvist/ansible-secrets-management/commit/086c8091d89dad68eab57c7a41bfee64b2f0846f))
* **openbao:** add a seed-only mode to the AppRole rotation playbook ([#2112](https://github.com/dryvist/ansible-secrets-management/issues/2112)) ([9d3b211](https://github.com/dryvist/ansible-secrets-management/commit/9d3b211b53928a2af7c269a0543d16163e96cddb))
* **openbao:** add a workstation-only converge identity for the OpenBao-node play ([#1862](https://github.com/dryvist/ansible-secrets-management/issues/1862)) ([70e90f1](https://github.com/dryvist/ansible-secrets-management/commit/70e90f10e51bcd2f71ee3b3a19bb08a894c8df70))
* **openbao:** add agent-ssh-sign AppRole for workstation SSH signing ([#2359](https://github.com/dryvist/ansible-secrets-management/issues/2359)) ([78652e1](https://github.com/dryvist/ansible-secrets-management/commit/78652e17fb99090ff72c927d506a70ab330dd148))
* **openbao:** add an agent workstation AppRole ([#2106](https://github.com/dryvist/ansible-secrets-management/issues/2106)) ([bedd914](https://github.com/dryvist/ansible-secrets-management/commit/bedd914e8f1b310ee3ced66559c72ca0b0e4b106))
* **openbao:** add an operator workstation AppRole ([#2097](https://github.com/dryvist/ansible-secrets-management/issues/2097)) ([4ca7225](https://github.com/dryvist/ansible-secrets-management/commit/4ca722505fd2af23100b179fe643c27cde1fac08))
* **openbao:** add approle-audit read-only policy for auth/approle/role ([3a8446f](https://github.com/dryvist/ansible-secrets-management/commit/3a8446f515e070da9bab5a7eee52eea1f4fe2330))
* **openbao:** add bounded admin session role ([a56d9e6](https://github.com/dryvist/ansible-secrets-management/commit/a56d9e67d14d68aac748a106e6dc25aa3df25a89))
* **openbao:** add Cribl Edge generated fields and readers ([#2386](https://github.com/dryvist/ansible-secrets-management/issues/2386)) ([a6ef6ba](https://github.com/dryvist/ansible-secrets-management/commit/a6ef6bafd87f5825f1d9b9095d6f9dbc7713c6a0))
* **openbao:** add daily secret-age auditor timer ([#1821](https://github.com/dryvist/ansible-secrets-management/issues/1821)) ([3db0f9a](https://github.com/dryvist/ansible-secrets-management/commit/3db0f9afc7ec593207f0b9bf4142db7333f1f9c3))
* **openbao:** add github-hermes App mount with visibility-split sets ([#2284](https://github.com/dryvist/ansible-secrets-management/issues/2284)) ([043f741](https://github.com/dryvist/ansible-secrets-management/commit/043f7412588953deb8fd8df8d912ea9344668c5d))
* **openbao:** add github-repo-create tier ([8fdca75](https://github.com/dryvist/ansible-secrets-management/commit/8fdca7558b189f166e0add3185f22b4e42e3a2ac))
* **openbao:** add github-repo-create tier ([1fc7028](https://github.com/dryvist/ansible-secrets-management/commit/1fc7028865506fde66d12539166f0f368bfcd5dd))
* **openbao:** add github-work App mount, policy and AppRole ([0601245](https://github.com/dryvist/ansible-secrets-management/commit/0601245dfb0e40c267eaee884d7cda8d7dec4cf8))
* **openbao:** add github-work App mount, policy and AppRole ([09d9251](https://github.com/dryvist/ansible-secrets-management/commit/09d925190958c83e970ecc6b3fac0d6839312579))
* **openbao:** add Hermes configuration ([#2379](https://github.com/dryvist/ansible-secrets-management/issues/2379)) ([5314292](https://github.com/dryvist/ansible-secrets-management/commit/531429297e6b38c5604ba33f35e35430bb48f99d))
* **openbao:** add inert github-admin-claude repo-create AppRole ([#2055](https://github.com/dryvist/ansible-secrets-management/issues/2055)) ([3636112](https://github.com/dryvist/ansible-secrets-management/commit/36361129a16cfddcdbb492be0c2d6b906f812c86))
* **openbao:** add llm-router-write single-secret writer identity ([#1577](https://github.com/dryvist/ansible-secrets-management/issues/1577)) ([8577d18](https://github.com/dryvist/ansible-secrets-management/commit/8577d18120eb9e1b59b7f6d39d567755ef68ca3b))
* **openbao:** add local-llm-workstation AppRole for workstation reads ([#2352](https://github.com/dryvist/ansible-secrets-management/issues/2352)) ([be55ae3](https://github.com/dryvist/ansible-secrets-management/commit/be55ae32b455ac76295805313a3288eda83b80ca))
* **openbao:** add open-llm's public-repo write permission set ([bc61634](https://github.com/dryvist/ansible-secrets-management/commit/bc61634639b35b10b7c3caebba2ef850e010f0ea))
* **openbao:** add opencode to the ai-api-key provider set ([#1828](https://github.com/dryvist/ansible-secrets-management/issues/1828)) ([3593cfa](https://github.com/dryvist/ansible-secrets-management/commit/3593cfaef85a9205f9401435b21659ba835e0f17))
* **openbao:** add Prometheus telemetry and scrape target ([#2051](https://github.com/dryvist/ansible-secrets-management/issues/2051)) ([84863f8](https://github.com/dryvist/ansible-secrets-management/commit/84863f8b2b769912baaa5b60ec41423e0f7f6c4e))
* **openbao:** add read-only approle-audit policy ([a79e9fd](https://github.com/dryvist/ansible-secrets-management/commit/a79e9fdba4d2cda96583f6748b203da54fa27871))
* **openbao:** add read-only open-llm AppRole ([7242bb9](https://github.com/dryvist/ansible-secrets-management/commit/7242bb976c89520047cf564895c652bf66833721))
* **openbao:** add read-only open-llm AppRole for the successor harness ([9e0b650](https://github.com/dryvist/ansible-secrets-management/commit/9e0b6501b1baf2abc3a4bad66dec0425eddcc381))
* **openbao:** add ssh host-cert signing role ([#2203](https://github.com/dryvist/ansible-secrets-management/issues/2203)) ([3e9cbc4](https://github.com/dryvist/ansible-secrets-management/commit/3e9cbc4f54bf35726518cd206d1db80c41164700))
* **openbao:** add standing operator master-admin AppRole ([12e11d7](https://github.com/dryvist/ansible-secrets-management/commit/12e11d750889da17d223d7ee093b9f86255c7ee7))
* **openbao:** add standing operator master-admin AppRole ([3cfa2d6](https://github.com/dryvist/ansible-secrets-management/commit/3cfa2d6a96eab48df69fc399be26784ed41049a1))
* **openbao:** add the docs router snapshot key, set and OIDC role ([#2505](https://github.com/dryvist/ansible-secrets-management/issues/2505)) ([551e4d9](https://github.com/dryvist/ansible-secrets-management/commit/551e4d922bd93066dc080982300a9996bb6696cf))
* **openbao:** add the iac-platform-semaphore workspace identity ([#1681](https://github.com/dryvist/ansible-secrets-management/issues/1681)) ([4fa7c4a](https://github.com/dryvist/ansible-secrets-management/commit/4fa7c4ac6b0d7dcfa5e438e1d8166bc6c7e00dee))
* **openbao:** add the litellm-local-workstation generated field ([69af118](https://github.com/dryvist/ansible-secrets-management/commit/69af118134aa27b02331c73cb6ad9904febcb615))
* **openbao:** allow a permissions map on github/token write mints ([84ec5f9](https://github.com/dryvist/ansible-secrets-management/commit/84ec5f98ee3b55c9f133974c169247592b70b4dd))
* **openbao:** allow a permissions map on github/token write mints ([4f2a088](https://github.com/dryvist/ansible-secrets-management/commit/4f2a088f082d392c278741aa70c80b23035b7e62))
* **openbao:** attach GitHub and AI read tiers to the workstation identities ([#2111](https://github.com/dryvist/ansible-secrets-management/issues/2111)) ([fabaa99](https://github.com/dryvist/ansible-secrets-management/commit/fabaa99f81182e9c44540e0b8c4f9427c57df748))
* **openbao:** declare a read-only AppRole for the IaC platform deploy ([2abd852](https://github.com/dryvist/ansible-secrets-management/commit/2abd852b0899130afd2f345ffa611483343d8cbc))
* **openbao:** declare a read-only AppRole for the IaC platform deploy ([#1657](https://github.com/dryvist/ansible-secrets-management/issues/1657)) ([d81e3cb](https://github.com/dryvist/ansible-secrets-management/commit/d81e3cbeb01c5c104a32605df96c56f65790f0b8))
* **openbao:** declare disclosure-denylist secret path and read policy ([#2177](https://github.com/dryvist/ansible-secrets-management/issues/2177)) ([7a975b7](https://github.com/dryvist/ansible-secrets-management/commit/7a975b799aa73b71b35697c9ecfdd872528f7600))
* **openbao:** declare the four identities that existed only in the store ([#1788](https://github.com/dryvist/ansible-secrets-management/issues/1788)) ([ace0051](https://github.com/dryvist/ansible-secrets-management/commit/ace005139d56a219886433ec5b23d842e4ba3583))
* **openbao:** define the untrusted dispatcher tier ([63ce58b](https://github.com/dryvist/ansible-secrets-management/commit/63ce58b65474cf1349f38f7cd836579e38b79694))
* **openbao:** docs publisher policy reads one app bucket ([#2073](https://github.com/dryvist/ansible-secrets-management/issues/2073)) ([c43630b](https://github.com/dryvist/ansible-secrets-management/commit/c43630b96fe4a9526f1be36b25a5c5a021a463ae))
* **openbao:** extend Hermes rotation and Context7 configuration ([#2332](https://github.com/dryvist/ansible-secrets-management/issues/2332)) ([2137e49](https://github.com/dryvist/ansible-secrets-management/commit/2137e49f61567308ed86db9d7bc6c3ccb6c006d6))
* **openbao:** fail the converge on an AppRole live but declared nowhere ([#1750](https://github.com/dryvist/ansible-secrets-management/issues/1750)) ([3c4389b](https://github.com/dryvist/ansible-secrets-management/commit/3c4389b7154a49fa83c1af9006ee0dabae229b23))
* **openbao:** fail the converge on an AppRole with no source-address class ([#1747](https://github.com/dryvist/ansible-secrets-management/issues/1747)) ([4843937](https://github.com/dryvist/ansible-secrets-management/commit/48439371250ec1b69edb3db4e1502360bc89dea5))
* **openbao:** fail when the store's provisioning host is absent from a run ([#1766](https://github.com/dryvist/ansible-secrets-management/issues/1766)) ([cd61168](https://github.com/dryvist/ansible-secrets-management/commit/cd61168ceb95350099638a1ea6b7735faf321c5a))
* **openbao:** finite secret_id TTLs, CIDR binding, scoped admin policy, issuer split, human unlock ([#1692](https://github.com/dryvist/ansible-secrets-management/issues/1692)) ([0900005](https://github.com/dryvist/ansible-secrets-management/commit/090000598f0a35f43c3aba86eedad7822c3c8f59))
* **openbao:** generalize slack rotator into an openbao_rotators table, add splunk-mcp ([#1820](https://github.com/dryvist/ansible-secrets-management/issues/1820)) ([8087676](https://github.com/dryvist/ansible-secrets-management/commit/80876765871ca8bb789dea764f599a5563ad701d))
* **openbao:** generate a github-actions router key ([#1825](https://github.com/dryvist/ansible-secrets-management/issues/1825)) ([2f2ac06](https://github.com/dryvist/ansible-secrets-management/commit/2f2ac0664343f24f21d7efd3278acfe4fee53270))
* **openbao:** generate a litellm-local router-key secret ([#2046](https://github.com/dryvist/ansible-secrets-management/issues/2046)) ([170d5a2](https://github.com/dryvist/ansible-secrets-management/commit/170d5a257632e17d3158edb37e4dc31bbfeed3c5))
* **openbao:** generate a litellm-local-workstation router-key secret ([d667131](https://github.com/dryvist/ansible-secrets-management/commit/d667131d6a31586629572c1666ffe35f5ff7003e))
* **openbao:** generate a litellm-local-workstation router-key secret ([#2237](https://github.com/dryvist/ansible-secrets-management/issues/2237)) ([ba42db2](https://github.com/dryvist/ansible-secrets-management/commit/ba42db23b111c0a2b55103e31c4653dd9c750234))
* **openbao:** generate a per-consumer router key for Open WebUI and LangGraph ([#1709](https://github.com/dryvist/ansible-secrets-management/issues/1709)) ([9bb417c](https://github.com/dryvist/ansible-secrets-management/commit/9bb417c70890b309e85e602d2aea7a7552ab96ce))
* **openbao:** generate a scoped router key for langfuse ([#2105](https://github.com/dryvist/ansible-secrets-management/issues/2105)) ([4c3011b](https://github.com/dryvist/ansible-secrets-management/commit/4c3011b28bfa3d952fea957c1b1b3434dd9af635))
* **openbao:** generate a shared Semaphore runner registration token ([#2069](https://github.com/dryvist/ansible-secrets-management/issues/2069)) ([ae5a39a](https://github.com/dryvist/ansible-secrets-management/commit/ae5a39a61fc53fa867adef7ae09301fec2825ee4))
* **openbao:** generate hermes_login_password for the vikunja app secret ([7fc49ac](https://github.com/dryvist/ansible-secrets-management/commit/7fc49acce32bd634d623544fd7e7e650b7bc6011))
* **openbao:** generate hermes_login_password for the vikunja app secret ([3c3f64a](https://github.com/dryvist/ansible-secrets-management/commit/3c3f64a0135846c9e849a2b5f3d84c0afa99edec))
* **openbao:** generate hindsight_api_key in apps/hindsight ([#2354](https://github.com/dryvist/ansible-secrets-management/issues/2354)) ([d5db8f9](https://github.com/dryvist/ansible-secrets-management/commit/d5db8f9b0dacdc6d70d6d50472cce61b6b3a0874))
* **openbao:** generate litellm OIDC client secret ([5d4abb0](https://github.com/dryvist/ansible-secrets-management/commit/5d4abb0bf72a79198d73918ea82b91dff84b9f49))
* **openbao:** generate router keys for eight new apps ([#1867](https://github.com/dryvist/ansible-secrets-management/issues/1867)) ([34646ad](https://github.com/dryvist/ansible-secrets-management/commit/34646ad07a0b5e8139d45f09c6634e34699ebbef))
* **openbao:** generate scoped router keys for agentgateway, dify, llamaindex ([#2104](https://github.com/dryvist/ansible-secrets-management/issues/2104)) ([6e00ac2](https://github.com/dryvist/ansible-secrets-management/commit/6e00ac29847b5cb3cff9af949f2ca63136ecfad3))
* **openbao:** generate the github-actions-oss router key under apps ([d023949](https://github.com/dryvist/ansible-secrets-management/commit/d0239499a1d5c3c6669b5779d95972b52b0ad623))
* **openbao:** generate the github-actions-public router key under apps ([e54d663](https://github.com/dryvist/ansible-secrets-management/commit/e54d663f2991f6238ad411ea1b12f3eb6bbefa46))
* **openbao:** give the unattended execution plane its own identity ([#1724](https://github.com/dryvist/ansible-secrets-management/issues/1724)) ([5b2615a](https://github.com/dryvist/ansible-secrets-management/commit/5b2615a1ddbc985b76c135da59ead7af759a55cb))
* **openbao:** grant LiteLLM provider credential leaves ([d71427a](https://github.com/dryvist/ansible-secrets-management/commit/d71427aa28b0164455958340c6a673ac49b73b8c))
* **openbao:** grant LiteLLM provider credential leaves ([40dadc5](https://github.com/dryvist/ansible-secrets-management/commit/40dadc5400bdb162a6385211c91b614953113c39))
* **openbao:** grant observability read on the OpenRouter usage key ([#2357](https://github.com/dryvist/ansible-secrets-management/issues/2357)) ([ecb22df](https://github.com/dryvist/ansible-secrets-management/commit/ecb22df15903d8afadc5c792ac14651b8fd69d23))
* **openbao:** grant read-only Splunk MCP access ([7e5d255](https://github.com/dryvist/ansible-secrets-management/commit/7e5d2558b46ff30d12c137e8d286988ac417a29c))
* **openbao:** grant read-only Splunk MCP access ([573a5cc](https://github.com/dryvist/ansible-secrets-management/commit/573a5cca9897b9e07baf06e6b9fb9bec6a5022b5))
* **openbao:** grant the agent workstation AppRole the vikunja MCP read policy ([#2108](https://github.com/dryvist/ansible-secrets-management/issues/2108)) ([d0b848d](https://github.com/dryvist/ansible-secrets-management/commit/d0b848d4beb560c969f8a11d9357a27b5586600c))
* **openbao:** grant the converge AppRole a read on the NAS account secret ([#1572](https://github.com/dryvist/ansible-secrets-management/issues/1572)) ([750336a](https://github.com/dryvist/ansible-secrets-management/commit/750336aaca5b6c6d011043cda7e40c7f23135855))
* **openbao:** grant the converge identity its run-environment documents ([#1737](https://github.com/dryvist/ansible-secrets-management/issues/1737)) ([07e1546](https://github.com/dryvist/ansible-secrets-management/commit/07e15464cccb756beeea6255294e1a3ae6540b87))
* **openbao:** grant the pve-exporter token publish path ([#2323](https://github.com/dryvist/ansible-secrets-management/issues/2323)) ([e2d66fb](https://github.com/dryvist/ansible-secrets-management/commit/e2d66fb3413dc353286949a80b0f39d5339722f1))
* **openbao:** grant tofu-proxmox read on ssh-client-ca config ([#2043](https://github.com/dryvist/ansible-secrets-management/issues/2043)) ([9413b48](https://github.com/dryvist/ansible-secrets-management/commit/9413b48fb7fe0930ff2d99945e15f8ad11f39dba))
* **openbao:** let claude-identity rotate its own secret_id ([#2074](https://github.com/dryvist/ansible-secrets-management/issues/2074)) ([26c9cb4](https://github.com/dryvist/ansible-secrets-management/commit/26c9cb497f25f73e93d26c0717561c8039e2ba3b))
* **openbao:** let the agent workstation identity run converges ([#2115](https://github.com/dryvist/ansible-secrets-management/issues/2115)) ([fa87d0f](https://github.com/dryvist/ansible-secrets-management/commit/fa87d0fb69366d2c05628755066fb352da6a704c))
* **openbao:** let the converge identity publish the open-llm bucket ([b751078](https://github.com/dryvist/ansible-secrets-management/commit/b751078e4158b2e43ba941007192ddde84508531))
* **openbao:** let the converge identity publish the open-llm bucket ([d2a956c](https://github.com/dryvist/ansible-secrets-management/commit/d2a956c76c44aebf4c409792409b7b84bf0227ff))
* **openbao:** let the execution plane be the reconcile identity ([#1785](https://github.com/dryvist/ansible-secrets-management/issues/1785)) ([73d1d1c](https://github.com/dryvist/ansible-secrets-management/commit/73d1d1cfcef71a0be20ece74384a57e3e1e6d8c6))
* **openbao:** let the semaphore identity mint read-tier GitHub tokens ([#1742](https://github.com/dryvist/ansible-secrets-management/issues/1742)) ([7700a13](https://github.com/dryvist/ansible-secrets-management/commit/7700a133e69699a0ded699c42c412b0391096e11))
* **openbao:** mint a dedicated router key for Hindsight ([33485b5](https://github.com/dryvist/ansible-secrets-management/commit/33485b5918d7308f0fef0a50f0f56c45cd64a10a))
* **openbao:** mint a dedicated router key for Hindsight ([5a9724d](https://github.com/dryvist/ansible-secrets-management/commit/5a9724dd3712ca37701ff7b3f31a34040527874e))
* **openbao:** mint a repository-scoped docs publisher token from GitHub Actions OIDC ([#1729](https://github.com/dryvist/ansible-secrets-management/issues/1729)) ([1d79191](https://github.com/dryvist/ansible-secrets-management/commit/1d79191498884963073db8a25a4dc01045cd5136))
* **openbao:** mint dedicated router key for n8n ([#2011](https://github.com/dryvist/ansible-secrets-management/issues/2011)) ([6f01c9a](https://github.com/dryvist/ansible-secrets-management/commit/6f01c9a59d871369bf4d8f7cb79fa33463c55350))
* **openbao:** mint the tofu-github token instead of storing it ([#1726](https://github.com/dryvist/ansible-secrets-management/issues/1726)) ([d01c823](https://github.com/dryvist/ansible-secrets-management/commit/d01c823f128017ada6ee42d9cc028a8895617093))
* **openbao:** move policy-sync to an inert openbao-policy-sync AppRole ([#2079](https://github.com/dryvist/ansible-secrets-management/issues/2079)) ([3fb1f4f](https://github.com/dryvist/ansible-secrets-management/commit/3fb1f4f57ef07f0e39b0ea45160693101dcb4d43))
* **openbao:** policy-sync keeps the reconcile policy in step on plane converges ([#2068](https://github.com/dryvist/ansible-secrets-management/issues/2068)) ([8fe4434](https://github.com/dryvist/ansible-secrets-management/commit/8fe4434fda15ad4a1bf6676f0f02cc184181b907))
* **openbao:** promote open-llm's KV bucket, fix policy path ([2bbb6ef](https://github.com/dryvist/ansible-secrets-management/commit/2bbb6efc5909c3d721bb686877a0d26c9072667e))
* **openbao:** promote the task-tracker operator account into its app bucket ([#1794](https://github.com/dryvist/ansible-secrets-management/issues/1794)) ([a70e441](https://github.com/dryvist/ansible-secrets-management/commit/a70e441f59a58d1e326b9a369c8d93cf45a2547a))
* **openbao:** read machine-identity AppRole pairs from the env document in a prefetch play ([#2113](https://github.com/dryvist/ansible-secrets-management/issues/2113)) ([157e80e](https://github.com/dryvist/ansible-secrets-management/commit/157e80edef7c8fb48e3218e4cbcbe98a79eebf2a))
* **openbao:** rotate domain AppRole secret_ids under a dedicated identity ([#2040](https://github.com/dryvist/ansible-secrets-management/issues/2040)) ([335d5cc](https://github.com/dryvist/ansible-secrets-management/commit/335d5cc7a97c47b774c9152f4389983159f5a577))
* **openbao:** rotate the open-llm secret_id on the scheduled cadence ([#2356](https://github.com/dryvist/ansible-secrets-management/issues/2356)) ([b72d162](https://github.com/dryvist/ansible-secrets-management/commit/b72d162c94ada61b2ca0f6289419f95291c931c8))
* **openbao:** say so when provisioning is skipped for want of a token ([#1576](https://github.com/dryvist/ansible-secrets-management/issues/1576)) ([f260451](https://github.com/dryvist/ansible-secrets-management/commit/f260451576eb41d40301dbe9988bf59e1dc31d59))
* **openbao:** seed and grant the hermes-ui app secrets ([#1415](https://github.com/dryvist/ansible-secrets-management/issues/1415)) ([7d6561e](https://github.com/dryvist/ansible-secrets-management/commit/7d6561e88d1e7379502d5ac4dcf3112c0150dc88))
* **openbao:** seed open-llm's vikunja/zammad MCP URLs from OpenBao ([afc29a2](https://github.com/dryvist/ansible-secrets-management/commit/afc29a2ec24b40383e1e55fcac663cec09653239))
* **openbao:** seed open-llm's vikunja/zammad MCP URLs from OpenBao ([88a0803](https://github.com/dryvist/ansible-secrets-management/commit/88a0803ba027c116afb4997e2e0c52f9a6dbcd11))
* **openbao:** self-bootstrapping github-admin-claude with an org-admin set ([#2067](https://github.com/dryvist/ansible-secrets-management/issues/2067)) ([7767306](https://github.com/dryvist/ansible-secrets-management/commit/7767306259d518c7ad37f40f7593e7b6da2588d5))
* **openbao:** set ai-public cidr class and secret_id bounds ([#1886](https://github.com/dryvist/ansible-secrets-management/issues/1886)) ([a5952f7](https://github.com/dryvist/ansible-secrets-management/commit/a5952f762be2bba7326888a6cae3f29878f9ac69))
* **openbao:** set approle-audit CIDR class to machine_or_workstation ([4f169d0](https://github.com/dryvist/ansible-secrets-management/commit/4f169d0c401bdb0635d1807b5b1781d21c2d1432))
* **openbao:** split GitHub engine mounts per App ([#2080](https://github.com/dryvist/ansible-secrets-management/issues/2080)) ([70d3891](https://github.com/dryvist/ansible-secrets-management/commit/70d3891b72ab798e29b8b48378731097cde740de))
* **openbao:** standing secret_id for the vikunja-mcp AppRole ([4e1e2c2](https://github.com/dryvist/ansible-secrets-management/commit/4e1e2c2e001b042ef679f7172554eb1b8e6250a0))
* **openbao:** trust ingress X-Forwarded-For and reconcile bound-CIDR drift ([#1735](https://github.com/dryvist/ansible-secrets-management/issues/1735)) ([eca0975](https://github.com/dryvist/ansible-secrets-management/commit/eca097511dcba1a56f32ceb13caa942770089152))
* **openbao:** update vikunja-mcp AppRole declaration ([019dfb6](https://github.com/dryvist/ansible-secrets-management/commit/019dfb6cd0f5543af2d0c0f73f3aa5aab373977d))
* **openbao:** use installation scope for general write tokens ([becae0a](https://github.com/dryvist/ansible-secrets-management/commit/becae0a305481104e45eb9b0f797e541e79489f8))
* **openbao:** use installation scope for general write tokens ([d94a45d](https://github.com/dryvist/ansible-secrets-management/commit/d94a45d9c8a94c58926648cafe73d9785c737d11))
* **openbao:** use per-call AppRole credentials ([#2437](https://github.com/dryvist/ansible-secrets-management/issues/2437)) ([152dc90](https://github.com/dryvist/ansible-secrets-management/commit/152dc905d46954f207fcb7e50b3947fd4fe68c37))
* **openbao:** validate GitHub App webhook and installation settings ([#2107](https://github.com/dryvist/ansible-secrets-management/issues/2107)) ([f376a49](https://github.com/dryvist/ansible-secrets-management/commit/f376a49e71b25253271989c2a37b3b0c22268988))
* **postgres:** add the litellm database to the ai-VLAN cluster ([#1570](https://github.com/dryvist/ansible-secrets-management/issues/1570)) ([7ed79fe](https://github.com/dryvist/ansible-secrets-management/commit/7ed79fe5575e55ab6b46d748dd8af81e658c2d65))
* **postgres:** optional Patroni/etcd HA mode behind postgres_ha_manager ([#2189](https://github.com/dryvist/ansible-secrets-management/issues/2189)) ([d17d540](https://github.com/dryvist/ansible-secrets-management/commit/d17d5402bcb489cf82630ae746abed2945714103))
* **prometheus_stack:** scrape the LLM router's metrics with a generated per-scraper key ([#1823](https://github.com/dryvist/ansible-secrets-management/issues/1823)) ([934c3d2](https://github.com/dryvist/ansible-secrets-management/commit/934c3d2d5c532f59f9a4d2c73fc2103955ce5893))
* **rotate-key:** add canonical on-demand secret rotation playbook ([#1819](https://github.com/dryvist/ansible-secrets-management/issues/1819)) ([88d7294](https://github.com/dryvist/ansible-secrets-management/commit/88d7294cc8a1c24b4863bb29b226fe2b43292e88))
* **runner:** fall back when the semaphore AppRole login is refused ([#1846](https://github.com/dryvist/ansible-secrets-management/issues/1846)) ([49bd600](https://github.com/dryvist/ansible-secrets-management/commit/49bd600ebc60a0b61340ee6556682c8e361f89eb))
* scaffold the secrets_management collection ([#1](https://github.com/dryvist/ansible-secrets-management/issues/1)) ([99308cf](https://github.com/dryvist/ansible-secrets-management/commit/99308cf2110d665a995a0cdcf1090a8bc4b92d66))
* schedule reconcile rotation ([ec0e531](https://github.com/dryvist/ansible-secrets-management/commit/ec0e53158f21219d2d17c24653f71f43ddf878b4))
* **service_deadman:** add an off-site free-tier deadman + ntfy liveness check ([#1866](https://github.com/dryvist/ansible-secrets-management/issues/1866)) ([c313a63](https://github.com/dryvist/ansible-secrets-management/commit/c313a63c41259d9709787b2a8b0c4cb60f054aa4))
* shared ProxMan cluster ingress, DNS ownership, and workstation connection profile ([#2272](https://github.com/dryvist/ansible-secrets-management/issues/2272)) ([6c67a1e](https://github.com/dryvist/ansible-secrets-management/commit/6c67a1ec52e866aa7bdab9e2e5d053d4a0d64de4))
* **unpoller:** native poller + Cribl scrape + OpenBao credential ([#2174](https://github.com/dryvist/ansible-secrets-management/issues/2174)) ([468ada6](https://github.com/dryvist/ansible-secrets-management/commit/468ada6c932dc4aac6c2b23f9d7ff959f9978585))
* **vikunja:** add data-driven Hermes bridge identity mechanism ([#2062](https://github.com/dryvist/ansible-secrets-management/issues/2062)) ([3ac7d90](https://github.com/dryvist/ansible-secrets-management/commit/3ac7d906d256e0c1dc220447bcb4eeafb0146549))
* **vikunja:** mint a narrow dispatch-queue token and publish it to its own path ([#2109](https://github.com/dryvist/ansible-secrets-management/issues/2109)) ([03b9724](https://github.com/dryvist/ansible-secrets-management/commit/03b9724577d81bb9356b1f379bb87b38831dbd7a))
* **vikunja:** provision the AI Jobs dispatcher token ([cce1b9b](https://github.com/dryvist/ansible-secrets-management/commit/cce1b9b761008cf6976e8a383c5d8b022033eb60))
* **vikunja:** provision the AI Jobs dispatcher token ([2464893](https://github.com/dryvist/ansible-secrets-management/commit/24648938052014cf0fa2d32af95bdc8c810ee09e))
* **vikunja:** publish MCP token to OpenBao with a scoped reader AppRole ([#2054](https://github.com/dryvist/ansible-secrets-management/issues/2054)) ([ae584ee](https://github.com/dryvist/ansible-secrets-management/commit/ae584eec7a280a19912f6f19252b8f2cf5ebb8d2))
* **wall:** serve the server-room wall ([#2139](https://github.com/dryvist/ansible-secrets-management/issues/2139)) ([4415583](https://github.com/dryvist/ansible-secrets-management/commit/4415583de001ab9aec4ea6c15be186143650be8b))
* **zammad,cribl_edge:** Security IDS group, svc-cribl identity, Edge IDS wiring ([#2257](https://github.com/dryvist/ansible-secrets-management/issues/2257)) ([1eea82d](https://github.com/dryvist/ansible-secrets-management/commit/1eea82d01701986b806296f83862b5167c9e1e9d))
* **zammad:** add svc-splunk service account and its own API token ([#1579](https://github.com/dryvist/ansible-secrets-management/issues/1579)) ([a170112](https://github.com/dryvist/ansible-secrets-management/commit/a1701126d5b29df187ffb776d8715f0e9ae9f8b3))


### Bug Fixes

* align the domain catalog ([3b5aa10](https://github.com/dryvist/ansible-secrets-management/commit/3b5aa10965dd41c714bdbf62d4bb37cde0be0a1e))
* assert the single benchmark router key ([#2479](https://github.com/dryvist/ansible-secrets-management/issues/2479)) ([31c5ceb](https://github.com/dryvist/ansible-secrets-management/commit/31c5cebfe3bbb9dcdf11d8b982d7790206fe4d99))
* **authelia:** strip the Digest prefix from service-user hashes ([#2222](https://github.com/dryvist/ansible-secrets-management/issues/2222)) ([81cd257](https://github.com/dryvist/ansible-secrets-management/commit/81cd25793c9299a1178d17ccd86757a2d037c54d))
* **authelia:** strip the Digest prefix so OIDC client secrets are hashes, not plaintext ([#1660](https://github.com/dryvist/ansible-secrets-management/issues/1660)) ([afd21ce](https://github.com/dryvist/ansible-secrets-management/commit/afd21ce61093c24285d84725b3f548757bd70360))
* **authelia:** verify release checksum from signed manifest, drop stale pin ([8f59137](https://github.com/dryvist/ansible-secrets-management/commit/8f5913763fcefabad661619f2e2e2b77b138b1b5))
* **auth:** parameterize role defaults ([#2443](https://github.com/dryvist/ansible-secrets-management/issues/2443)) ([1d1649f](https://github.com/dryvist/ansible-secrets-management/commit/1d1649f846ead60e78e9dcdb4050e89057f4e7e7))
* bound scheduled rotation catalog ([#2399](https://github.com/dryvist/ansible-secrets-management/issues/2399)) ([61fb541](https://github.com/dryvist/ansible-secrets-management/commit/61fb54150d94001ea0e303d57e24b6524422b7f1))
* bound scheduled rotation catalog ([#2399](https://github.com/dryvist/ansible-secrets-management/issues/2399)) ([bdfeaeb](https://github.com/dryvist/ansible-secrets-management/commit/bdfeaeb7f6b8d27fbb793d1756332d01ccf6422d))
* build router key paths from the consumer catalog ([7761562](https://github.com/dryvist/ansible-secrets-management/commit/7761562084a5252475d415541ee562eab506c2fe))
* **ci:** revive the e2e suite with OpenBao-rendered inputs and one matrix job ([#1906](https://github.com/dryvist/ansible-secrets-management/issues/1906)) ([4cd12e6](https://github.com/dryvist/ansible-secrets-management/commit/4cd12e6889383d465f17c298ab92d7db89326c67))
* **cribl_stream:** manage the admin login through the converge ([#1961](https://github.com/dryvist/ansible-secrets-management/issues/1961)) ([ccb2f32](https://github.com/dryvist/ansible-secrets-management/commit/ccb2f326d88fd6dd4626ced229d483becb47ff5e))
* **cribl_stream:** take openbao audit `_time` from the record ([#2516](https://github.com/dryvist/ansible-secrets-management/issues/2516)) ([a748e51](https://github.com/dryvist/ansible-secrets-management/commit/a748e51cd0c0f8dd076e5182f2703a935004f6f1))
* **disclosure:** reword sensitive-category terms in comments and docs ([#2182](https://github.com/dryvist/ansible-secrets-management/issues/2182)) ([0ca9bff](https://github.com/dryvist/ansible-secrets-management/commit/0ca9bffe8c42635aeb4db34b443317643762b170))
* **dns:** front splunk web UI through the shared ingress VIP ([1098d68](https://github.com/dryvist/ansible-secrets-management/commit/1098d68273e949f0d278769414e88c1b5299bdb3))
* **dns:** front splunk web UI through the shared ingress VIP ([8367653](https://github.com/dryvist/ansible-secrets-management/commit/83676539a378ec175f3a63e4eb075adc3c3a3147))
* generate router keys through shared catalog ([#2474](https://github.com/dryvist/ansible-secrets-management/issues/2474)) ([3a109ab](https://github.com/dryvist/ansible-secrets-management/commit/3a109ab4abbdd3124447d0975002fd8249102c4c))
* **homarr:** build the seerr URL from the ingress subdomain; retire the public AppRole ([#1824](https://github.com/dryvist/ansible-secrets-management/issues/1824)) ([7ab7b5b](https://github.com/dryvist/ansible-secrets-management/commit/7ab7b5bd5bfd679594f70c0217ce8edb3df1ad89))
* **inventory:** build fronted service URLs from the ingress zone ([#1666](https://github.com/dryvist/ansible-secrets-management/issues/1666)) ([cb01c45](https://github.com/dryvist/ansible-secrets-management/commit/cb01c453e8ad961bedb66ad19a12c743d30e5a3a))
* **inventory:** preserve tag-selected secret coverage ([90d032c](https://github.com/dryvist/ansible-secrets-management/commit/90d032cca74a2b22b1759b66b810e83d837bb5c8))
* mint flow-lock IDs through approle-issuer ([8efc27d](https://github.com/dryvist/ansible-secrets-management/commit/8efc27d652ee7980e50997a02e3ce996de9fa59b))
* **molecule:** derive expected policy names outside the assert conditional ([#1558](https://github.com/dryvist/ansible-secrets-management/issues/1558)) ([0e81277](https://github.com/dryvist/ansible-secrets-management/commit/0e812779ec32e5315685997ac3bc459f6530ce90))
* **molecule:** give each CI job its own instance names ([#1741](https://github.com/dryvist/ansible-secrets-management/issues/1741)) ([636f5a2](https://github.com/dryvist/ansible-secrets-management/commit/636f5a23dddf1e0f5e429cdafd44a09f8e1acade))
* **ntfy:** single-quote the Zammad topic-group JSON in the subscriber env file ([#2486](https://github.com/dryvist/ansible-secrets-management/issues/2486)) ([55b3418](https://github.com/dryvist/ansible-secrets-management/commit/55b34185f3f9ac9161150a704284ee186a8961ce))
* **openbao_secrets:** decide a failed AppRole login without failing the task ([#2301](https://github.com/dryvist/ansible-secrets-management/issues/2301)) ([ba97921](https://github.com/dryvist/ansible-secrets-management/commit/ba979218bb0713e019c514768c53a6c52554dbcf))
* **openbao_secrets:** declare apps/pve-exporter optional ([#1878](https://github.com/dryvist/ansible-secrets-management/issues/1878)) ([6f31bc3](https://github.com/dryvist/ansible-secrets-management/commit/6f31bc34e2959aef4738c9627baa0254106745fb))
* **openbao_secrets:** declare the local-cloud path optional ([#2293](https://github.com/dryvist/ansible-secrets-management/issues/2293)) ([7bf2124](https://github.com/dryvist/ansible-secrets-management/commit/7bf2124432dda1d1f6e9b47d7d8e647b961a05ae))
* **openbao_secrets:** engine_mount_point AttributeError on ansible-core 2.21 ([#1895](https://github.com/dryvist/ansible-secrets-management/issues/1895)) ([9d3a7a7](https://github.com/dryvist/ansible-secrets-management/commit/9d3a7a74cbdd0308f365143af62373c45299cb15))
* **openbao_secrets:** fail loud on missing or unreadable secrets ([#1691](https://github.com/dryvist/ansible-secrets-management/issues/1691)) ([bffe38b](https://github.com/dryvist/ansible-secrets-management/commit/bffe38b1b323a9cf514ffa886abb91a99562718b))
* **openbao_secrets:** stop the delegated publish escalating on the control node ([#1439](https://github.com/dryvist/ansible-secrets-management/issues/1439)) ([318804a](https://github.com/dryvist/ansible-secrets-management/commit/318804a7708e8bc5811b9a54f155888a9b5b7d0e))
* **openbao_secrets:** take the issuer path only where flow-lock runs ([#2503](https://github.com/dryvist/ansible-secrets-management/issues/2503)) ([75f9f6c](https://github.com/dryvist/ansible-secrets-management/commit/75f9f6c4c98a59dd7969e66a29b4d417607e01a2))
* **openbao:** a denied AppRole existence check is not an absent AppRole ([865b226](https://github.com/dryvist/ansible-secrets-management/commit/865b22641fa451ded785f22a2a9961554de26601))
* **openbao:** admin and write-realm AppRoles accept the workstation ([#1854](https://github.com/dryvist/ansible-secrets-management/issues/1854)) ([8501d94](https://github.com/dryvist/ansible-secrets-management/commit/8501d94bd78e0ea5af2c203d41606ec639b61315))
* **openbao:** ai-admin administers login MFA ([3f59c63](https://github.com/dryvist/ansible-secrets-management/commit/3f59c634f1b6f86f8d13c213270fe0abb1f9b9bf))
* **openbao:** ai-admin administers login MFA ([9016915](https://github.com/dryvist/ansible-secrets-management/commit/9016915c54b9d28163b54926a9238391056f300e))
* **openbao:** alert once per rotator failure streak ([#2515](https://github.com/dryvist/ansible-secrets-management/issues/2515)) ([f7a82d0](https://github.com/dryvist/ansible-secrets-management/commit/f7a82d0cdae13f5585d5b8904483995ef32b67ed))
* **openbao:** bind flow-lock to a machine-or-workstation CIDR class ([#1748](https://github.com/dryvist/ansible-secrets-management/issues/1748)) ([4839da7](https://github.com/dryvist/ansible-secrets-management/commit/4839da72673627d43a0b235e5be587281aa22610))
* **openbao:** bind github-repo-create to the workstation class ([#1869](https://github.com/dryvist/ansible-secrets-management/issues/1869)) ([0dc4133](https://github.com/dryvist/ansible-secrets-management/commit/0dc4133efa6d5c77fd9f7890ea6a907f667456b4))
* **openbao:** bind the ai-sessions-backup AppRole to the workstation class ([81cef7d](https://github.com/dryvist/ansible-secrets-management/commit/81cef7dbd1a28ffef153d40502a0b882f331c797))
* **openbao:** bind the ai-sessions-backup AppRole to the workstation class ([0912923](https://github.com/dryvist/ansible-secrets-management/commit/091292381a6286b1656f2ee913fd5b4cf2eac9c3))
* **openbao:** bind the github-write-x10 realm to the workstation class ([#1858](https://github.com/dryvist/ansible-secrets-management/issues/1858)) ([a8462b0](https://github.com/dryvist/ansible-secrets-management/commit/a8462b058cc2e08d84922e373f2ba3c3ba2ee63f))
* **openbao:** bound the admin AppRole token to the human unlock window ([#1734](https://github.com/dryvist/ansible-secrets-management/issues/1734)) ([6a172b5](https://github.com/dryvist/ansible-secrets-management/commit/6a172b5e7687de2afad55fc1b8e0c08959fa9ab1))
* **openbao:** build the capability probe's paths without a regex backreference ([04f4b9f](https://github.com/dryvist/ansible-secrets-management/commit/04f4b9f5545efcd1e1c464356f2ac8febd3ad33a))
* **openbao:** classify the platform deploy identity as workstation-held ([#1754](https://github.com/dryvist/ansible-secrets-management/issues/1754)) ([0df097c](https://github.com/dryvist/ansible-secrets-management/commit/0df097c2b8fa212908e4d696ac72c18d4e21497f))
* **openbao:** constrain the one policy path inventory renders verbatim ([d730476](https://github.com/dryvist/ansible-secrets-management/commit/d7304767af65642d4ed9d635ffd882de817a56c9))
* **openbao:** constrain the one policy path inventory renders verbatim ([c826aa3](https://github.com/dryvist/ansible-secrets-management/commit/c826aa37f879ee026bc02ce48915964197ffc6e8))
* **openbao:** converge-domain AppRole secret_ids no longer expire ([#1963](https://github.com/dryvist/ansible-secrets-management/issues/1963)) ([59435cb](https://github.com/dryvist/ansible-secrets-management/commit/59435cb17e172b815048214c13c1428a9c462542))
* **openbao:** create the denylist entry metadata with put when absent ([#2273](https://github.com/dryvist/ansible-secrets-management/issues/2273)) ([40e8589](https://github.com/dryvist/ansible-secrets-management/commit/40e85897f2a737dbdf97691fa922df0152271054))
* **openbao:** curl the snapshot API on an on-box IPv4 ([#1706](https://github.com/dryvist/ansible-secrets-management/issues/1706)) ([3e53f8a](https://github.com/dryvist/ansible-secrets-management/commit/3e53f8a1e8cddcfa70ec8ee82e590ab6c078d285))
* **openbao:** declare the reconcile identity's class as plane-and-workstation ([#1772](https://github.com/dryvist/ansible-secrets-management/issues/1772)) ([15831f2](https://github.com/dryvist/ansible-secrets-management/commit/15831f240ab5eeb21cd6fce286ea5f338e03b226))
* **openbao:** define openbao_write_addr in the exempt-tag test fixture ([#1890](https://github.com/dryvist/ansible-secrets-management/issues/1890)) ([d611f6e](https://github.com/dryvist/ansible-secrets-management/commit/d611f6e2ee0ff2e24e7e32f3d5a3e578ea7b2f35))
* **openbao:** delegate generated secret writes through the CLI host ([e677200](https://github.com/dryvist/ansible-secrets-management/commit/e677200747bfadb1b771d93fb0ea388e9b96e43b))
* **openbao:** delegate the GitHub App check include to localhost ([#2270](https://github.com/dryvist/ansible-secrets-management/issues/2270)) ([65c0388](https://github.com/dryvist/ansible-secrets-management/commit/65c0388b426db360e677254d239dada38385b208))
* **openbao:** delegate the reconcile login to the controller ([f0cd0fe](https://github.com/dryvist/ansible-secrets-management/commit/f0cd0fe844f06632616b7c7fcae700fd84d77ea3))
* **openbao:** deploy the snapshot timer, fix voter-health self-detection, harden audit forwarding ([#1693](https://github.com/dryvist/ansible-secrets-management/issues/1693)) ([6745449](https://github.com/dryvist/ansible-secrets-management/commit/6745449a41f1ff315c481c256287967c83d889be))
* **openbao:** do not declare the Hermes policies without an installation ([#2448](https://github.com/dryvist/ansible-secrets-management/issues/2448)) ([79d7ca8](https://github.com/dryvist/ansible-secrets-management/commit/79d7ca8ad817ef53a728bb0e3bf510977bda799a))
* **openbao:** drop the stale scheduled-mode name load in the rotation play ([#2346](https://github.com/dryvist/ansible-secrets-management/issues/2346)) ([4762c6b](https://github.com/dryvist/ansible-secrets-management/commit/4762c6b4cac13730b1df19553cf924b91add6e55))
* **openbao:** emit the voters count the quorum alert needs, and fail closed ([#1761](https://github.com/dryvist/ansible-secrets-management/issues/1761)) ([e3d5e97](https://github.com/dryvist/ansible-secrets-management/commit/e3d5e97a58a206cbe49c40d1eef2b77f16a45309))
* **openbao:** extend reconcile token session TTL ([626d70a](https://github.com/dryvist/ansible-secrets-management/commit/626d70ae12f6c7dfe6628626963bfc720ee67b1d))
* **openbao:** extend reconcile token session TTL ([86310ca](https://github.com/dryvist/ansible-secrets-management/commit/86310cad5b665cbf24c00230c3d6bf4cc1df549d))
* **openbao:** fail the capability gate on a short probe answer, not only an empty one ([8f1a435](https://github.com/dryvist/ansible-secrets-management/commit/8f1a435ef50fc1db28d627a76b6266af4aeed812))
* **openbao:** fail the converge when no ingress address is trusted for X-Forwarded-For ([#1743](https://github.com/dryvist/ansible-secrets-management/issues/1743)) ([d87fa2f](https://github.com/dryvist/ansible-secrets-management/commit/d87fa2f144cc68e9086855567045a574bc6103f7))
* **openbao:** fail the snapshot leader-gate on local API errors ([#1705](https://github.com/dryvist/ansible-secrets-management/issues/1705)) ([0ed0ddf](https://github.com/dryvist/ansible-secrets-management/commit/0ed0ddf855916114b3107317d8e70491ac50a35c))
* **openbao:** fail with the secrets-engine listing's exit code and stderr ([#1795](https://github.com/dryvist/ansible-secrets-management/issues/1795)) ([8a302e2](https://github.com/dryvist/ansible-secrets-management/commit/8a302e2eea426004f80f5d9f5aa35e3e4e0908ae))
* **openbao:** filter ai-orchestrator GitHub grants by tier ([#1834](https://github.com/dryvist/ansible-secrets-management/issues/1834)) ([fbb8193](https://github.com/dryvist/ansible-secrets-management/commit/fbb81938c09f6b412511b967ba63ea04d95c2e45))
* **openbao:** finish a rotation whose previous secret_id already expired ([#2258](https://github.com/dryvist/ansible-secrets-management/issues/2258)) ([617dfa5](https://github.com/dryvist/ansible-secrets-management/commit/617dfa5449f4a2aec377989b67c6833f4ebbe4a5))
* **openbao:** fold host-cert sign grant into existing signer policies ([#2210](https://github.com/dryvist/ansible-secrets-management/issues/2210)) ([437bbf8](https://github.com/dryvist/ansible-secrets-management/commit/437bbf84d55fe2db396da2066f6795a6b0f742cc))
* **openbao:** gate RBAC reconciliation on real, server-reported capability ([#1641](https://github.com/dryvist/ansible-secrets-management/issues/1641)) ([8903e40](https://github.com/dryvist/ansible-secrets-management/commit/8903e40a95e2d5c8504829b23210b1b91aa21310))
* **openbao:** gate SSH-engine and auth-method bootstrap out of reconcile mode ([#1638](https://github.com/dryvist/ansible-secrets-management/issues/1638)) ([cb81fea](https://github.com/dryvist/ansible-secrets-management/commit/cb81feab2fb96fb6b8c9dcd3e1f561d47e1ba11f))
* **openbao:** gate the KV-mounts init step behind reconcile mode ([#1865](https://github.com/dryvist/ansible-secrets-management/issues/1865)) ([78f5997](https://github.com/dryvist/ansible-secrets-management/commit/78f5997f7560ab7ab0ea5690cc63a1ae03444907))
* **openbao:** gate the rotation-exempt metadata patch on capability; grant it to reconcile ([#1835](https://github.com/dryvist/ansible-secrets-management/issues/1835)) ([ba8efb2](https://github.com/dryvist/ansible-secrets-management/commit/ba8efb2ec9693ba8740c826c45a07539e5fbacd2))
* **openbao:** generate router virtual keys in the format the router accepts ([#1857](https://github.com/dryvist/ansible-secrets-management/issues/1857)) ([79b33f1](https://github.com/dryvist/ansible-secrets-management/commit/79b33f1b00cbc1bc21a5553ea61caad0dceb0fc9))
* **openbao:** generate the monitoring GATUS_EXTERNAL_TOKEN ([#2172](https://github.com/dryvist/ansible-secrets-management/issues/2172)) ([546f0aa](https://github.com/dryvist/ansible-secrets-management/commit/546f0aa55f3fcc2fd350cf50e1eb8ed5405c5641))
* **openbao:** give open-llm the rotated-domain secret_id ttl ([#2518](https://github.com/dryvist/ansible-secrets-management/issues/2518)) ([3697109](https://github.com/dryvist/ansible-secrets-management/commit/36971098c32dff31395db6f8ec16af988519bdd3))
* **openbao:** grant the rotate policy's missing role-id/lookup reads ([#2081](https://github.com/dryvist/ansible-secrets-management/issues/2081)) ([9ffee7f](https://github.com/dryvist/ansible-secrets-management/commit/9ffee7f97276470b9c59f6a40ff4733179ebddff))
* **openbao:** grant tofu-unifi read on the object-storage credential ([#1494](https://github.com/dryvist/ansible-secrets-management/issues/1494)) ([390e297](https://github.com/dryvist/ansible-secrets-management/commit/390e29719b89f51fa72b9d8a1bef18adb68d9133))
* **openbao:** guard secret-age rsyslog drop-in against duplicate imfile load ([#1877](https://github.com/dryvist/ansible-secrets-management/issues/1877)) ([d5bf87e](https://github.com/dryvist/ansible-secrets-management/commit/d5bf87ec0c2ce5ff8a83456131abb93a0b4c33ae))
* **openbao:** install curl and jq on the nodes, and name a missing one ([#1730](https://github.com/dryvist/ansible-secrets-management/issues/1730)) ([73ae403](https://github.com/dryvist/ansible-secrets-management/commit/73ae403b5996f2c8795a5025b469bec617e00973))
* **openbao:** keep finite secret_id bounds on the open-llm AppRole ([7e88bb8](https://github.com/dryvist/ansible-secrets-management/commit/7e88bb81e170050b2f5a5c53811baa454286aa03))
* **openbao:** keep finite secret_id bounds on the open-llm AppRole ([2e9b0de](https://github.com/dryvist/ansible-secrets-management/commit/2e9b0def770e7b8493a37819c46bc8905bc0c915))
* **openbao:** keep finite secret_id bounds on the proxman AppRole ([0822829](https://github.com/dryvist/ansible-secrets-management/commit/082282939702dde6c1fa9ae955f067291cae3ef3))
* **openbao:** keep installation write scope opt-in ([#2336](https://github.com/dryvist/ansible-secrets-management/issues/2336)) ([#2342](https://github.com/dryvist/ansible-secrets-management/issues/2342)) ([c068d9f](https://github.com/dryvist/ansible-secrets-management/commit/c068d9f288dceec4df5183d898b7748a232ed274))
* **openbao:** keep the apps reader's grant on the pve-exporter bucket ([#2328](https://github.com/dryvist/ansible-secrets-management/issues/2328)) ([9eda50e](https://github.com/dryvist/ansible-secrets-management/commit/9eda50ed1922db727a82c0dd26e2cff7114bf358))
* **openbao:** keep the existing static-seal key when none is supplied ([#2102](https://github.com/dryvist/ansible-secrets-management/issues/2102)) ([ca9eda2](https://github.com/dryvist/ansible-secrets-management/commit/ca9eda2050d376b276848cb4d54039e295173a99))
* **openbao:** keep the nodes' seal key id when the environment sets none ([#2244](https://github.com/dryvist/ansible-secrets-management/issues/2244)) ([e8d8d81](https://github.com/dryvist/ansible-secrets-management/commit/e8d8d81ed22501c28812387c7b470276dfddd373))
* **openbao:** load the scheduled identity's name from 05g in the rotation play ([b2add5c](https://github.com/dryvist/ansible-secrets-management/commit/b2add5cefb2b467b3a65d9deae0f51fb3854f652))
* **openbao:** load the scheduled identity's name from 05g in the rotation play ([3e7534c](https://github.com/dryvist/ansible-secrets-management/commit/3e7534c47bdd84fc9d8f0135601715d8e40faffa))
* **openbao:** make the bao CLI routing switch a role default, not a fact ([#1907](https://github.com/dryvist/ansible-secrets-management/issues/1907)) ([9697d2c](https://github.com/dryvist/ansible-secrets-management/commit/9697d2ca4cb665933337395e43911e38107f7ba1))
* **openbao:** make the RBAC policy write actually idempotent ([#1665](https://github.com/dryvist/ansible-secrets-management/issues/1665)) ([6a1bc4d](https://github.com/dryvist/ansible-secrets-management/commit/6a1bc4d146ee91057b96eaf10bb58cbf4586c495))
* **openbao:** mask the role_id read in domain rotation ([#2371](https://github.com/dryvist/ansible-secrets-management/issues/2371)) ([d3af608](https://github.com/dryvist/ansible-secrets-management/commit/d3af608a81667febe7dd4e29a1802827ab5c200d))
* **openbao:** non-expiring class-bound secret_ids for standing identities ([#2509](https://github.com/dryvist/ansible-secrets-management/issues/2509)) ([6d4e47a](https://github.com/dryvist/ansible-secrets-management/commit/6d4e47a646c2db98d7bf0073b6c4ea7990587b8f))
* **openbao:** non-expiring secret_ids for the standing ambient AppRoles ([#1885](https://github.com/dryvist/ansible-secrets-management/issues/1885)) ([6553eb7](https://github.com/dryvist/ansible-secrets-management/commit/6553eb70cdf544990755b03cabe04ee5bf10f702))
* **openbao:** parse the live AppRole list as a bare array ([#2351](https://github.com/dryvist/ansible-secrets-management/issues/2351)) ([15f3246](https://github.com/dryvist/ansible-secrets-management/commit/15f3246f20e1f003b8e3d499d866d2d4b2e77e0d))
* **openbao:** pass item explicitly into nested RBAC policy template renders ([be1a67b](https://github.com/dryvist/ansible-secrets-management/commit/be1a67b7aee6ca91ffe052ebd06259152b6a6da7))
* **openbao:** pass item explicitly into nested RBAC policy template renders ([48116f6](https://github.com/dryvist/ansible-secrets-management/commit/48116f6ef4e0a85bc5b28ec6302233866c2878c8))
* **openbao:** persist the audit imfile read offset ([#2521](https://github.com/dryvist/ansible-secrets-management/issues/2521)) ([a2f5115](https://github.com/dryvist/ansible-secrets-management/commit/a2f5115c7e240703ef4f44dfab898cc1e19f17b8))
* **openbao:** preserve finite write realm bounds ([#2339](https://github.com/dryvist/ansible-secrets-management/issues/2339)) ([1e44f41](https://github.com/dryvist/ansible-secrets-management/commit/1e44f41c3da496ed1413992ab1d7ff6a715fa4a4))
* **openbao:** prove workstation-bound rotated pairs by lookup ([#2149](https://github.com/dryvist/ansible-secrets-management/issues/2149)) ([fe78ec8](https://github.com/dryvist/ansible-secrets-management/commit/fe78ec8778fe89ab5d86b022b0e88e19e220f670))
* **openbao:** read capabilities from both response locations, and separate an empty probe from a denial ([#1653](https://github.com/dryvist/ansible-secrets-management/issues/1653)) ([59bad20](https://github.com/dryvist/ansible-secrets-management/commit/59bad20a14536b6768b3ae6abae5b1d97b817b33))
* **openbao:** read the App install allowlist from the env document ([#2268](https://github.com/dryvist/ansible-secrets-management/issues/2268)) ([0127aad](https://github.com/dryvist/ansible-secrets-management/commit/0127aad84cda0c438ad435f3a25f9756c3ab6ade))
* **openbao:** read the rotator's Doppler target from the platform env doc ([#2127](https://github.com/dryvist/ansible-secrets-management/issues/2127)) ([99c77fd](https://github.com/dryvist/ansible-secrets-management/commit/99c77fd87b0cd79ee1dece1c2ae917f3fdf87830))
* **openbao:** reclassify slack approles for workstation CIDR access ([#1864](https://github.com/dryvist/ansible-secrets-management/issues/1864)) ([8bece7d](https://github.com/dryvist/ansible-secrets-management/commit/8bece7d4defc031f24093d73da03cd0ab119f0ab))
* **openbao:** reconcile AppRole TTL bounds on existing machine roles ([#1704](https://github.com/dryvist/ansible-secrets-management/issues/1704)) ([1e69712](https://github.com/dryvist/ansible-secrets-management/commit/1e697126a6e997d5aa4f0d2be946ac4c01fb8c48))
* **openbao:** reconcile declared RBAC without an operator token ([9417daf](https://github.com/dryvist/ansible-secrets-management/commit/9417daf463f9b434a4f5c61b00508a68febd4bc5))
* **openbao:** reconcile RBAC before tagging rotation-exempt paths ([#1844](https://github.com/dryvist/ansible-secrets-management/issues/1844)) ([1723682](https://github.com/dryvist/ansible-secrets-management/commit/1723682e3cd93dfa2e19225887f81f96b1e96816))
* **openbao:** reconcile through per-call issuer ([#2446](https://github.com/dryvist/ansible-secrets-management/issues/2446)) ([588ac6b](https://github.com/dryvist/ansible-secrets-management/commit/588ac6b1c1a8a9101fb96da2587bd7aa7b0c4105))
* **openbao:** refuse to write an empty rendered RBAC policy ([#1831](https://github.com/dryvist/ansible-secrets-management/issues/1831)) ([5fce97c](https://github.com/dryvist/ansible-secrets-management/commit/5fce97cc5e9103dded139602c8e2f57f8fa4ecc1))
* **openbao:** reload plugin backends on a same-version binary rewrite ([#1997](https://github.com/dryvist/ansible-secrets-management/issues/1997)) ([b0af473](https://github.com/dryvist/ansible-secrets-management/commit/b0af473d11183aa9cbf0de2c90fdd3bcc114224d))
* **openbao:** rename open-llm's promoted vikunja field to VIKUNJA_API_TOKEN ([#2021](https://github.com/dryvist/ansible-secrets-management/issues/2021)) ([f3c430a](https://github.com/dryvist/ansible-secrets-management/commit/f3c430a0b0013c80256654d139fcbfc0f044b435))
* **openbao:** republish rotated workstation AppRole pairs into Doppler ([#2120](https://github.com/dryvist/ansible-secrets-management/issues/2120)) ([15cf20d](https://github.com/dryvist/ansible-secrets-management/commit/15cf20dec40a31f3c72b7737d4ed2c43b58da164))
* **openbao:** resolve the existing TOTP method by the field the API returns ([#1913](https://github.com/dryvist/ansible-secrets-management/issues/1913)) ([cf1d0ed](https://github.com/dryvist/ansible-secrets-management/commit/cf1d0ed696d0bdadabfa2acfebf23b11cec9a896))
* **openbao:** restart notified voters one at a time ([#2519](https://github.com/dryvist/ansible-secrets-management/issues/2519)) ([684e155](https://github.com/dryvist/ansible-secrets-management/commit/684e15596a77058ea3cc7933e1537662e626cbe5))
* **openbao:** restore Cribl Mac rotation catalog ([e43cc9d](https://github.com/dryvist/ansible-secrets-management/commit/e43cc9d587408c4e7f39b297158d0f0f7eb249e3))
* **openbao:** rotate the ai-donna AppRole secret_id with the other agent identities ([#2465](https://github.com/dryvist/ansible-secrets-management/issues/2465)) ([b8ef9b2](https://github.com/dryvist/ansible-secrets-management/commit/b8ef9b2fd575c0b87fbb764ab2b8f18dbdcfcef6))
* **openbao:** run init store calls on the CLI host ([a305c3b](https://github.com/dryvist/ansible-secrets-management/commit/a305c3b7f9996d918ac50fe063a4d7af38df509f))
* **openbao:** run init store calls on the CLI host ([505ae3e](https://github.com/dryvist/ansible-secrets-management/commit/505ae3e03f351c4a44ca41b54ebba47b9145eb32))
* **openbao:** run policy-sync before reconcile-grant consumers ([#2219](https://github.com/dryvist/ansible-secrets-management/issues/2219)) ([a5b30d9](https://github.com/dryvist/ansible-secrets-management/commit/a5b30d9c297bf6246a1731792adca7bb33fef521))
* **openbao:** run policy-sync capability check and write from the controller ([#2221](https://github.com/dryvist/ansible-secrets-management/issues/2221)) ([a461dd0](https://github.com/dryvist/ansible-secrets-management/commit/a461dd002fb6a1e1a2f19f48c6a3c310cd3810cb))
* **openbao:** run the undeclared-live AppRole calls on the CLI host ([#2450](https://github.com/dryvist/ansible-secrets-management/issues/2450)) ([fecf6af](https://github.com/dryvist/ansible-secrets-management/commit/fecf6af8a903a4eee2d6ad2b06f4dc09a4262ad9))
* **openbao:** scheduled AppRole rotation renews itself first and survives a failed domain ([#2510](https://github.com/dryvist/ansible-secrets-management/issues/2510)) ([19d268f](https://github.com/dryvist/ansible-secrets-management/commit/19d268f230b8ce164260def3abe726540d2e4e15))
* **openbao:** scrub environment-specific names from init tasks ([#2259](https://github.com/dryvist/ansible-secrets-management/issues/2259)) ([7b6fa02](https://github.com/dryvist/ansible-secrets-management/commit/7b6fa02e6f7e437a3a027e2798186a6ae54780dc))
* **openbao:** seed the claude-code router key under apps ([2fbe517](https://github.com/dryvist/ansible-secrets-management/commit/2fbe51700123e9183c6683e6fe8e53a093133af6))
* **openbao:** send provisioning writes to the Raft leader ([3c09e54](https://github.com/dryvist/ansible-secrets-management/commit/3c09e540509cf61804af77acab1b92b8fa8d0b00))
* **openbao:** send provisioning writes to the Raft leader ([4f4ada6](https://github.com/dryvist/ansible-secrets-management/commit/4f4ada6d200119b35ea2a34240b24cc13ef2b342))
* **openbao:** send the app-secret promote write from the CLI host ([#2452](https://github.com/dryvist/ansible-secrets-management/issues/2452)) ([7709979](https://github.com/dryvist/ansible-secrets-management/commit/770997926a5b48c8cdb0a8692708aa0e19d9783e))
* **openbao:** set ansible_become false on the delegated App check include ([#2271](https://github.com/dryvist/ansible-secrets-management/issues/2271)) ([1bafa69](https://github.com/dryvist/ansible-secrets-management/commit/1bafa69f1fb7fb35e39db939d7723189e4f6d3fb))
* **openbao:** skip plugin-registering engines in reconcile mode ([#1637](https://github.com/dryvist/ansible-secrets-management/issues/1637)) ([ba28afb](https://github.com/dryvist/ansible-secrets-management/commit/ba28afb20796ff3dec9d06f2e9153955cea7cb5a))
* **openbao:** skip the Doppler sync-token read on a seed run ([#2131](https://github.com/dryvist/ansible-secrets-management/issues/2131)) ([e18fa98](https://github.com/dryvist/ansible-secrets-management/commit/e18fa98311d2e36123ad49140dbd489f26426fb2))
* **openbao:** split rbac-policies to clear the per-file token budget ([28e7981](https://github.com/dryvist/ansible-secrets-management/commit/28e7981beebb67a9d165efd488999f2f73394e28))
* **openbao:** stop the audit trail vanishing for hours at a time ([#1690](https://github.com/dryvist/ansible-secrets-management/issues/1690)) ([509386f](https://github.com/dryvist/ansible-secrets-management/commit/509386fb3be423e1abd4652c9e0e9692b5637e93))
* **openbao:** stop treating a CIDR-refused probe as a dead secret_id ([#2023](https://github.com/dryvist/ansible-secrets-management/issues/2023)) ([24e312f](https://github.com/dryvist/ansible-secrets-management/commit/24e312f27b8acff3eac207a34cc15dd9fed05e25))
* **openbao:** tag and order the per-App GitHub mount phase ([#2514](https://github.com/dryvist/ansible-secrets-management/issues/2514)) ([f0687fa](https://github.com/dryvist/ansible-secrets-management/commit/f0687fa9ddb51a993281272a09fa9e26255be2e8))
* **openbao:** tolerate only a genuine-absence answer before a conditional write ([#1678](https://github.com/dryvist/ansible-secrets-management/issues/1678)) ([ea4e6b7](https://github.com/dryvist/ansible-secrets-management/commit/ea4e6b754de796f2b99866111e0ef836d20435a2))
* **openbao:** trim app-secrets comment under the token-limit gate ([3478e1b](https://github.com/dryvist/ansible-secrets-management/commit/3478e1b27bd1a16ab54205ae6c9a09b69baebd3e))
* **openbao:** trim approle comments under the 4000-token file budget ([c8f3850](https://github.com/dryvist/ansible-secrets-management/commit/c8f38500ad91ae412a83c0152d5dbf8c75312df7))
* **openbao:** tune the approle mount login lockout for shared aliases ([#1872](https://github.com/dryvist/ansible-secrets-management/issues/1872)) ([c70d5ed](https://github.com/dryvist/ansible-secrets-management/commit/c70d5edd169e2e97f27b341c1a35861bc6ac8fea))
* **openbao:** unbound redemption count on the workstation GitHub AppRoles ([#1871](https://github.com/dryvist/ansible-secrets-management/issues/1871)) ([d81c7b2](https://github.com/dryvist/ansible-secrets-management/commit/d81c7b255d4f862f1074e5ae846565e0ce01a2af))
* **openbao:** uppercase open-llm's promoted KV field names ([8bdaf5f](https://github.com/dryvist/ansible-secrets-management/commit/8bdaf5f84472b9d2f077699a9523a1e6bb39cc61))
* **openbao:** validate rsyslog once, after every drop-in writer has run ([#1917](https://github.com/dryvist/ansible-secrets-management/issues/1917)) ([6e0e98f](https://github.com/dryvist/ansible-secrets-management/commit/6e0e98f0e7b194dd6f8adf0bf6724dc0e789097c))
* **openbao:** write KV secret values through the API, never argv ([#2370](https://github.com/dryvist/ansible-secrets-management/issues/2370)) ([a07dced](https://github.com/dryvist/ansible-secrets-management/commit/a07dcedcc1e58b4e7e7a945c7e85b27cb9da7b18))
* **openbao:** write reachable RBAC policies before failing on an ungranted name ([#2213](https://github.com/dryvist/ansible-secrets-management/issues/2213)) ([ad4d62d](https://github.com/dryvist/ansible-secrets-management/commit/ad4d62d488ab96d0fa32a7fd65893679a32f8e87))
* **postgres:** replace removed postgresql_set with postgresql_alter_system ([#1889](https://github.com/dryvist/ansible-secrets-management/issues/1889)) ([208eeca](https://github.com/dryvist/ansible-secrets-management/commit/208eeca6d7125b69255b38d64fb25a94d753c7fb))
* **unpoller:** read the UniFi controller address from OpenBao via the prefetch ([#2227](https://github.com/dryvist/ansible-secrets-management/issues/2227)) ([0749376](https://github.com/dryvist/ansible-secrets-management/commit/07493764074a302a4f9e6aa11a953ffd783641ff))
* **vikunja:** give the donna bridge identity its own OpenBao secret path ([#2087](https://github.com/dryvist/ansible-secrets-management/issues/2087)) ([9b06f81](https://github.com/dryvist/ansible-secrets-management/commit/9b06f81231f74e4bb7de70da45a74c7142e304c2))
* **vikunja:** resolve a stable, persisted login password for each Hermes bridge identity ([#2075](https://github.com/dryvist/ansible-secrets-management/issues/2075)) ([916ba43](https://github.com/dryvist/ansible-secrets-management/commit/916ba436c29e08f12da4476831be35c7d9a5dc75))


### Performance

* **ci:** run the checks a change needs ([#1470](https://github.com/dryvist/ansible-secrets-management/issues/1470)) ([733855b](https://github.com/dryvist/ansible-secrets-management/commit/733855b629ee53b7315a0ccecedb3b309b730f75))
* **converge:** cap wall clock at 20 minutes and run openbao reads on the controller ([#1904](https://github.com/dryvist/ansible-secrets-management/issues/1904)) ([10c0ac6](https://github.com/dryvist/ansible-secrets-management/commit/10c0ac68004ca5625d1363bf4529c0271571420b))
* **openbao:** add openbao_kv_seed tag and controller-side policy reads ([#2193](https://github.com/dryvist/ansible-secrets-management/issues/2193)) ([bf7386c](https://github.com/dryvist/ansible-secrets-management/commit/bf7386c5326efdb04bdd832d05a5cdeec4017c51))
* **openbao:** move remaining read loops to the controller ([5fd9b7d](https://github.com/dryvist/ansible-secrets-management/commit/5fd9b7ded4f7fbf56e024b2577bc9b5ac7bfaf97))
* **openbao:** move remaining read loops to the controller ([91fcbae](https://github.com/dryvist/ansible-secrets-management/commit/91fcbaeffa12bf7f7e494a563e7683229a1b56f8))
* **openbao:** render RBAC policies on the controller, not the target ([#1649](https://github.com/dryvist/ansible-secrets-management/issues/1649)) ([8546179](https://github.com/dryvist/ansible-secrets-management/commit/85461795bc8ba1e4a1b30add87dc28d5eac61784))
* **openbao:** run the AppRole, SSH role and policy writes on openbao_cli_host ([c5f9307](https://github.com/dryvist/ansible-secrets-management/commit/c5f9307dd51c64a517f75361c702f0718659b67d))
* **openbao:** run the AppRole, SSH role and policy writes on openbao_cli_host ([34ef30a](https://github.com/dryvist/ansible-secrets-management/commit/34ef30a79f71b0530aec558b66ee324bc4eb6000))
* **secrets:** scope the OpenBao pre-fetch to domains this run's hosts need ([#2183](https://github.com/dryvist/ansible-secrets-management/issues/2183)) ([bad4da3](https://github.com/dryvist/ansible-secrets-management/commit/bad4da3c46444eab5e117322bd435bd3f1423571))

## Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Releases are managed automatically by [release-please](https://github.com/googleapis/release-please).
