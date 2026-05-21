# Changelog

## [0.3.2](https://github.com/agentrhq/authsome/compare/authsome-v0.3.1...authsome-v0.3.2) (2026-05-20)


### Features

* Add posthog telemetry events ([575a464](https://github.com/agentrhq/authsome/commit/575a4648fbfa8c4de7b46c50311c2b426587977c))
* Add posthog telemetry events ([8797a94](https://github.com/agentrhq/authsome/commit/8797a94b406fe109b0a2216d693b74dd17446892))
* **evals:** /run-evals command + profile/run-dir flags ([bdeae58](https://github.com/agentrhq/authsome/commit/bdeae583a2d5bd9b4a28e1b717c74240469c890a))
* **evals:** add expected_interrupt and next_turn_instruction eval fields ([c4b2a93](https://github.com/agentrhq/authsome/commit/c4b2a9304ab53773c4b76cd4245b5663e744e4fc))
* **evals:** capture real claude transcripts via stream-json subprocess ([1b28f5a](https://github.com/agentrhq/authsome/commit/1b28f5ab4f9cd702e2ccf8b2bf805b0a58418158))
* **evals:** move new evals schema to evals/evals.json, restore skills copy ([5bb73ba](https://github.com/agentrhq/authsome/commit/5bb73ba509dc3a1b5d55c1356210f724d7c4b130))
* **evals:** profile isolation + authsome state check per eval ([73d3e70](https://github.com/agentrhq/authsome/commit/73d3e70b18387ec5510714e3ef4254f8fb33c49e))
* **proxy:** configurable intercept scope and unmatched policy ([987e312](https://github.com/agentrhq/authsome/commit/987e312aeeb680a4910697a18abb6eadb62d2b95))
* update health check to validate connections based on active identity and add test coverage ([9290169](https://github.com/agentrhq/authsome/commit/929016909595a68c4452c2291564241277df5ec6))
* update health check to validate connections based on active identity and add test coverage ([3fa9f97](https://github.com/agentrhq/authsome/commit/3fa9f97c8b3236b57649ae8b8a8e5ec538da8ca2))


### Bug Fixes

* copy full skill folder in evals and fix login flow links in authsome skill ([e8918a9](https://github.com/agentrhq/authsome/commit/e8918a97369f483f12b66e34d2eac5156ebc51f2))
* **evals:** use claude --system-prompt for judge, grade on rate limit ([b790c63](https://github.com/agentrhq/authsome/commit/b790c6329890cc0ccc824b51ca8b428ad6bca1c6))
* **evals:** use hermes as LLM judge instead of claude -p ([1157837](https://github.com/agentrhq/authsome/commit/1157837e4bda094d3f8f804886ecc4820fa62a5c))
* **marketplace:** point plugin homepage to authsome.ai ([11ffd80](https://github.com/agentrhq/authsome/commit/11ffd80da7e0c05c998236bfa3a7a9c59fb17de1))
* **marketplace:** point plugin homepage to authsome.ai ([a767cbc](https://github.com/agentrhq/authsome/commit/a767cbcea2464ed8fc7469219d33df3c5df9d794))
* **proxy:** address PR review feedback on mode validation and route defaults ([83ab469](https://github.com/agentrhq/authsome/commit/83ab4691e63ff62c8db9168af4e2cbbfdba55401))


### Documentation

* add GitHub OAuth app setup walkthrough to quickstart ([f45d9c9](https://github.com/agentrhq/authsome/commit/f45d9c9ece6bb7ba017b6ad6c1041b3bac53a4f7))
* add Roadmap, Contributing, and Links sections to README ([07534a4](https://github.com/agentrhq/authsome/commit/07534a4cdcec7f05f552b49f5d8d5a032232a630))
* add Roadmap, Contributing, and Links sections; rewrite roadmap.mdx ([03990b2](https://github.com/agentrhq/authsome/commit/03990b28db0460ea18c5c16eea7848ab262d235d))
* correct roadmap against changelog as source of truth ([eec08e3](https://github.com/agentrhq/authsome/commit/eec08e3b1605ac542153481b6faf49ab0a904676))
* **evals:** add hermes smoke test to pre-session setup ([bc4ef39](https://github.com/agentrhq/authsome/commit/bc4ef3917d74747fbeddec3c0f540f28b9f895d7))
* **evals:** add skip handling and per-eval max_turns config ([68ae0ed](https://github.com/agentrhq/authsome/commit/68ae0ed68b49df4d45083a911d8482dece1ae7a3))
* **evals:** merge setup.md into run-evals command, delete setup.md ([072836f](https://github.com/agentrhq/authsome/commit/072836f2d8a95822023f6f6f428d00bc21430875))
* **evals:** remove profile creation from run-evals command ([33ab525](https://github.com/agentrhq/authsome/commit/33ab5258b8b7144c02d12c5d3b71fa0aba4fa707))
* **evals:** update design spec and plan to reflect as-built state ([2558f5c](https://github.com/agentrhq/authsome/commit/2558f5c0de134bc26fee4d59a2c1120b736563c9))
* mark policy layer and firewall rules as shipped, add multi-user to coming next ([b1487e8](https://github.com/agentrhq/authsome/commit/b1487e87bcf5c99912181331296441190c4c2f05))
* **quickstart:** add provider tabs and a runnable agent example ([7c577ab](https://github.com/agentrhq/authsome/commit/7c577abe64fb9b4db34fa8b0bbc43f72289dd8da))
* **quickstart:** GitHub OAuth setup walkthrough and provider tabs ([63ffdec](https://github.com/agentrhq/authsome/commit/63ffdec8abe91c90966bfb61b8b547903b945bcf))
* reframe roadmap as end-user capabilities, not implementation work ([0740764](https://github.com/agentrhq/authsome/commit/07407646f6c88c8c1b72d8a43f947f80e24492dd))
* rewrite profile storage model to match current architecture ([457d1b2](https://github.com/agentrhq/authsome/commit/457d1b2ee7d54ce03ea697beb4913a5ce01ce0c7))
* rewrite profile storage model to match current architecture ([773323a](https://github.com/agentrhq/authsome/commit/773323ab73bd8a05e251f5ef121b2b072dc3259a))
* rewrite roadmap.mdx, remove ROADMAP.md, link README to docs ([a165d37](https://github.com/agentrhq/authsome/commit/a165d372fc5b44d7ee34066e40d6ade24b9ed575))
* simplify hosted daemon mode description in roadmap ([5458bf6](https://github.com/agentrhq/authsome/commit/5458bf62a5ededf7cfa2030d104bcf94b41178e6))
* **site:** adopt skill-driven CLI conventions across the docs ([8ba6967](https://github.com/agentrhq/authsome/commit/8ba6967f490502ab55bd401de25e8328bf476067))
* **site:** adopt skill-driven CLI conventions across the docs ([71b89fd](https://github.com/agentrhq/authsome/commit/71b89fd036dac67c7cfc761295b39889bf3ec9f2))

## [0.3.1](https://github.com/agentrhq/authsome/compare/authsome-v0.3.0...authsome-v0.3.1) (2026-05-17)


### Bug Fixes

* **cli:** resolve three CLI bugs and improve audit log command ([3b990e3](https://github.com/agentrhq/authsome/commit/3b990e3cae998d9ccaccb421b5cb577c2bb89de3))
* **cli:** resolve three CLI bugs, improve audit log, and sync docs ([dd9cad3](https://github.com/agentrhq/authsome/commit/dd9cad326cb2817826eb8e5b8bb42f5f3df8e2a2))


### Documentation

* **cli:** sync reference and manual-testing guide with 0.3.0 implementation ([bdf659f](https://github.com/agentrhq/authsome/commit/bdf659ffffc0a0c2100cc21508daec042161656e))

## [0.3.0](https://github.com/agentrhq/authsome/compare/authsome-v0.2.4...authsome-v0.3.0) (2026-05-15)


### ⚠ BREAKING CHANGES

* unify Identity and Profile; remove profile management layer
* Existing implicit default-profile installs must run authsome init again; profile:default credentials are not migrated.

### Features

* add --reload flag to daemon serve command and replace custom file watcher ([8fea50e](https://github.com/agentrhq/authsome/commit/8fea50e09a9b54a130133301876627bc67d57827))
* add --reload flag to daemon serve command and replace custom file watcher with uvicorn native reload ([2faa3c9](https://github.com/agentrhq/authsome/commit/2faa3c957bb377b82c804d8ed5ebbd26c94d0c71))
* add audit logging for proxy request injection and resolution misses ([6766c0e](https://github.com/agentrhq/authsome/commit/6766c0e7f5b43cd9d2d8d8645dc813cc46c447a2))
* add audit logging for proxy request injection and resolution misses, and include pytest-asyncio dependency. ([0afaf87](https://github.com/agentrhq/authsome/commit/0afaf8780ca701505145e4c2018434ec1365bd74))
* add copy-to-clipboard functionality to OAuth Redirect URI and update UI layout and styling ([0e1aa31](https://github.com/agentrhq/authsome/commit/0e1aa310bfdb2f0f89b153b252c6ed47cba02689))
* add did pop daemon authorization ([7ad14f6](https://github.com/agentrhq/authsome/commit/7ad14f60a39fefaebf274df5abcccc7270f841f4))
* add DID PoP daemon authorization ([dca2246](https://github.com/agentrhq/authsome/commit/dca2246235cb9637fa26254e8f29eb549ed7ada8))
* add RFC 7009 token revocation support to BaseFlow and integrate into Auth service ([74b96a3](https://github.com/agentrhq/authsome/commit/74b96a319c163461109beb370c49e0b88227f966))
* add RFC 7009 token revocation support to BaseFlow and integrate into Auth service ([7af96fc](https://github.com/agentrhq/authsome/commit/7af96fc5633871ab56c391db25018f2e9e07378b))
* **cli:** add import-env for headless API key ingestion ([bc318ff](https://github.com/agentrhq/authsome/commit/bc318fff28781f90a0b8259beef2114b730c8d72))
* **cli:** add import-env for headless API key ingestion ([e080286](https://github.com/agentrhq/authsome/commit/e0802865bc2052c583b2e7fa0ffed303481d651c))
* **cli:** add scan command for env provider detection ([9f9b8d4](https://github.com/agentrhq/authsome/commit/9f9b8d4de75bd6a53795454156bbc0514cb2908e))
* **cli:** add scan command for env provider detection and optional import ([9dee261](https://github.com/agentrhq/authsome/commit/9dee261c0164ed3e202977dfd4ad199804aae6ef))
* display OAuth redirect URI in auth UI and improve CLI command documentation and validation ([878461b](https://github.com/agentrhq/authsome/commit/878461ba6f2cd3999a9181957a877b69fb57531b))
* display OAuth redirect URI in auth UI and improve CLI command documentation and validation ([a0d72aa](https://github.com/agentrhq/authsome/commit/a0d72aa767f3c7f60c17d22e3cdd04a34e70a13b))
* enhance system health checks with permission, integrity, and key rotation monitoring ([dede72a](https://github.com/agentrhq/authsome/commit/dede72a1a6defd8167600ab7859f7c640550a5fa))
* expand doctor checks ([97afd37](https://github.com/agentrhq/authsome/commit/97afd37cfc04120c6cf635cdc69b7ba20cde17ce))
* expand doctor checks ([03ad70f](https://github.com/agentrhq/authsome/commit/03ad70fa3655a05daf82fcc7ba8513beb3ada6a6))
* expand health checks with integrity, permission, and rotation w… ([0956ef1](https://github.com/agentrhq/authsome/commit/0956ef1688e4cce4cf8454d2665ecea06457fe37))
* expand health checks with integrity, permission, and rotation warnings and update CLI UI to support warn status ([c885067](https://github.com/agentrhq/authsome/commit/c885067f046fa4b65fe6c3f99e1c4e694db2064b))
* global client credentials ([aa6aa56](https://github.com/agentrhq/authsome/commit/aa6aa56cfcaf4a82cdd2cdd808d4383f9506da47))
* global client credentials ([747b48f](https://github.com/agentrhq/authsome/commit/747b48f276eef0aeccfb8087423f4a24b163a4a9))
* implement auto-restart for daemon when source files are modified during development ([6fd7a6b](https://github.com/agentrhq/authsome/commit/6fd7a6b34b480d20b14b3926f64f9dd57095c47d))
* implement centralized audit logging and refactor duration formatting utility ([f9b5b89](https://github.com/agentrhq/authsome/commit/f9b5b8995a5fc5408d3e1b2c28affdd0f14cff65))
* implement hosted UI session management and multitenant provider visibility policy ([9ed0714](https://github.com/agentrhq/authsome/commit/9ed0714455d19a62ef51a3f035418f9785d34ed0))
* implement hosted UI session management and multitenant provider… ([c482817](https://github.com/agentrhq/authsome/commit/c48281734307035784b64d9ea99a9ed002a31411))
* implement local client profile management and update error handling for session authentication ([46a981a](https://github.com/agentrhq/authsome/commit/46a981a448c916a5e6cd5e22eb5e98687a473313))
* introduce parse_store_key utility and integrate into service for robust key parsing ([87b65e7](https://github.com/agentrhq/authsome/commit/87b65e7530e946fdff4a8b8bd8195d971f81117d))
* introduce parse_store_key utility and integrate into service for robust key parsing ([78ac38c](https://github.com/agentrhq/authsome/commit/78ac38ceaa3000de052a52fd94b519e4c49257b2))
* make provider client credentials a global property of hosted deployment ([be78393](https://github.com/agentrhq/authsome/commit/be78393d23358f370c38db4aa1d8c8768d04d3c6))
* move OAuth2 refresh token logic to BaseFlow and update service to use flow-specific handlers ([9b0366d](https://github.com/agentrhq/authsome/commit/9b0366dd014e3542a3f8156909ead8fd91a61561))
* move OAuth2 refresh token logic to BaseFlow and update service to use flow-specific handlers ([77b07d0](https://github.com/agentrhq/authsome/commit/77b07d0b41fc3e39bbee79c2409a68c85fadf64c))
* require server-registered identities ([019bdd1](https://github.com/agentrhq/authsome/commit/019bdd11e8fdc343ca0f571c2c7ef15f1347ba23))
* server store cleanup ([ec06181](https://github.com/agentrhq/authsome/commit/ec061812d284b7c9cef8f93a1d215b6df111cb8e))
* stabilize and document specific CLI exit codes for error states ([9f40cc6](https://github.com/agentrhq/authsome/commit/9f40cc6e02c5a95f9304c5948ca7cb5e222fa8cd))
* standardize CLI exit codes and add comprehensive documentation for error states ([8024433](https://github.com/agentrhq/authsome/commit/80244339c9990b741f48093123a9fbaf54f7c3c6))
* standardize CLI JSON output format with versioning ([c1c4fec](https://github.com/agentrhq/authsome/commit/c1c4fec7a0ea5a1715d8d818ecee191f64dde719))
* standardize CLI JSON output format with versioning and stable schema fields ([933d106](https://github.com/agentrhq/authsome/commit/933d106f1f14f370ca829b9e03843d43fa4d32ce))


### Bug Fixes

* client secret field made default ([3929b86](https://github.com/agentrhq/authsome/commit/3929b86ea934023cec0e4b58e14c7761bdf79b93))
* client secret field made default ([e3a4939](https://github.com/agentrhq/authsome/commit/e3a4939136d4c694e6c18743e15832dcd9191d83))
* correct daemon health check logic to properly validate client status and readiness ([e92bdad](https://github.com/agentrhq/authsome/commit/e92bdad5bbe208f3942618a06ae193f72eefd520))
* **docs:** repoint canonical to authsome.ai and drop dead links ([459259e](https://github.com/agentrhq/authsome/commit/459259ea8ef9e4b277706644fb88875188859cca))
* **docs:** repoint canonical to authsome.ai and drop dead links ([c97c1af](https://github.com/agentrhq/authsome/commit/c97c1afb5f9f79ddf5727ba965a2c2bdc0c13ce8))
* **docs:** unwrap call-graph diagram from Frame component ([bd28b9c](https://github.com/agentrhq/authsome/commit/bd28b9c647bfd233d702f393c2cf39055318d82c))
* **docs:** unwrap call-graph diagram from Frame component ([4d8e548](https://github.com/agentrhq/authsome/commit/4d8e54807728340e630eeb649c24e557b0e8259b))
* modify return type of _request function in cli client ([d7ddb2e](https://github.com/agentrhq/authsome/commit/d7ddb2ee33afbb406bc89913b7bc551a0e382697))
* prevent accidental termination of unrelated processes by validat ([f6b2f30](https://github.com/agentrhq/authsome/commit/f6b2f30c77a85ba56e0409fd5028417ea0b09c8f))
* prevent accidental termination of unrelated processes by validating daemon PID against local lock record during shutdown ([c25fe9c](https://github.com/agentrhq/authsome/commit/c25fe9c2cab05eabcb4707df53082f551ab8aad0))
* **proxy:** add mitmproxy CA to macOS keychain for Go tool TLS compatibility ([145734a](https://github.com/agentrhq/authsome/commit/145734accec2b5f1a3ad1f3c8478f82a461dc218))
* **proxy:** add mitmproxy CA to macOS keychain for Go tool TLS compatibility ([c9a9842](https://github.com/agentrhq/authsome/commit/c9a98425e59934906302f0fc46818771c7300a3b)), closes [#234](https://github.com/agentrhq/authsome/issues/234)
* refactoring ([cbf3a40](https://github.com/agentrhq/authsome/commit/cbf3a40b41f51c548cf9b377ad50e71e53e35af3))
* remove redundant flexbox properties from summary element styling ([8fc0b32](https://github.com/agentrhq/authsome/commit/8fc0b32e3801408a373f22dcf864609a562f02b7))
* save library version in client config ([5f52807](https://github.com/agentrhq/authsome/commit/5f52807b68012e3b46e9b62fb7ad63b0c0c383a5))
* update vault storage to use collection-scoped path in _save_provider_state ([c9eba5b](https://github.com/agentrhq/authsome/commit/c9eba5bb78ff54215a6660f70836e00716fcaae7))
* warn when token refresh fails ([627d579](https://github.com/agentrhq/authsome/commit/627d579d6ef65dda58b764a43ee3705ad72344d5))


### Reverts

* expand health checks with integrity, permission, and rotation w… ([6090d69](https://github.com/agentrhq/authsome/commit/6090d699c610b786fc2674ca20aebcdf409918b4))


### Documentation

* add API call constraints and troubleshooting guide to SKILL.md ([8313a27](https://github.com/agentrhq/authsome/commit/8313a270e2db8fb490e920bca09c925738e9ac7b))
* **readme:** add codecov badge and star history chart ([373a4a8](https://github.com/agentrhq/authsome/commit/373a4a80e9de7e1e4dd587e270fe960774d0d6aa))
* **readme:** overhaul with logo, community, security, and integrations ([3009e95](https://github.com/agentrhq/authsome/commit/3009e9505bf22dd51ae6efe9902261fce291d8c8))
* **readme:** overhaul with logo, community, security, and integrations ([2135499](https://github.com/agentrhq/authsome/commit/2135499d1aed84e8127f8607ffecdac698faef4b))
* remove restrictive constraints on CLI tool usage from SKILL.md ([98ee7ef](https://github.com/agentrhq/authsome/commit/98ee7efb36fe1bb5de800ce156146c7a5a9823f1))
* **site:** add CodeGroup, Expandable; remove now-unused proxy-injection snippet ([02d97f0](https://github.com/agentrhq/authsome/commit/02d97f025befb8f25bec882a56b05a1c38a54049))
* **site:** add logo wordmark, Discord link, and navbar icons ([38b3704](https://github.com/agentrhq/authsome/commit/38b3704a3e1911a0294cf9aa3bbdc7bc12ef2767))
* **site:** add logo wordmark, Discord link, and navbar icons ([bccf288](https://github.com/agentrhq/authsome/commit/bccf288447602df23c333fe79d662877bc7c4399))
* **site:** audit fixes across all four tiers ([89700e5](https://github.com/agentrhq/authsome/commit/89700e5b11657936adb54968b7d335bd6e96aef8))
* **site:** drop dead ProxyInjection import from provider pages ([eb5f0a6](https://github.com/agentrhq/authsome/commit/eb5f0a6afb841497400432774ca8fcad3046cc9a))
* **site:** four-tab nav + CLI/proxy-first framing ([f8fcab4](https://github.com/agentrhq/authsome/commit/f8fcab42ea0af9026829f85a18d2a67ab0c8d590))
* **site:** full audit pass — fix factual errors, dedupe, expand CLI/API surface ([ee33a49](https://github.com/agentrhq/authsome/commit/ee33a4932ae711fab0cefc30df482638876e4e41))
* **site:** lead with CLI + proxy; demote library to embedding case ([3f3cdd8](https://github.com/agentrhq/authsome/commit/3f3cdd8fccd623978c7fcbbabb9b4eef8bcde20b))
* **site:** rebuild docs into tabbed structure with shared snippets and component upgrades ([ced2422](https://github.com/agentrhq/authsome/commit/ced242215e70fe633ef27934fb9bef57df685ec3))
* **site:** split Guides and Reference into top-level tabs ([fac06d6](https://github.com/agentrhq/authsome/commit/fac06d6275044737265570a24c861c7d44edffe8))
* **skill:** add proxy mental model to Usage section ([7ca72a5](https://github.com/agentrhq/authsome/commit/7ca72a53ae89394db5a31a725eeacf9ef255f820))
* **skill:** bump to 0.1.5, soften CRITICAL RULE, clean up examples ([70c95ff](https://github.com/agentrhq/authsome/commit/70c95ffd82be6a7816f991136be2e5e6d47d31ed))
* **skill:** fix repo refs, sharpen description, move CRITICAL RULE to body ([d52244c](https://github.com/agentrhq/authsome/commit/d52244cbb93840aa54a4b645f67fd06fa9f404fc))
* **skill:** lead with usage, move install/login to reference sections ([51fcf74](https://github.com/agentrhq/authsome/commit/51fcf740c16d25937ccac81cc71d8777c3424f26))
* **skill:** radically simplify — usage first, minimal prose ([6e9ab01](https://github.com/agentrhq/authsome/commit/6e9ab01400ef49e7f6f13eb7f21a089bdc096c00))
* **skill:** recommend uv tool install over uvx alias ([a4b3355](https://github.com/agentrhq/authsome/commit/a4b335533afdaab5399fbc8db82d7b820560d962)), closes [#251](https://github.com/agentrhq/authsome/issues/251)
* **skill:** recommend uv tool install, simplify usage, v0.1.5 ([f264696](https://github.com/agentrhq/authsome/commit/f2646960a840fde4b513dcd3af6e926a36ef1e61))
* **skill:** remove registering a new provider section ([3342b5b](https://github.com/agentrhq/authsome/commit/3342b5b59adf41bb9e77995cbca3bae0c14cea77))
* **skill:** simplify Step 3 with concrete examples and always-run pattern ([727dccc](https://github.com/agentrhq/authsome/commit/727dcccc4173fe41c287593041771697b262e291))
* Update README how-it-works diagram ([26dcd74](https://github.com/agentrhq/authsome/commit/26dcd74a8687c2e295bf6b4ab7df3a58b14a72e2))


### Code Refactoring

* unify Identity and Profile; remove profile management layer ([d6958c8](https://github.com/agentrhq/authsome/commit/d6958c8434f4aa20a8d82c8fb4ecc143a3fa3d69))

## [0.2.4](https://github.com/manojbajaj95/authsome/compare/authsome-v0.2.3...authsome-v0.2.4) (2026-05-08)


### Features

* add dashboard UI ([9296d68](https://github.com/manojbajaj95/authsome/commit/9296d68691777652b27ad982f513d520fa597c94))
* add python-multipart dependency, update CLI table styling, and refine provider error messaging ([5d6f393](https://github.com/manojbajaj95/authsome/commit/5d6f39317e41f0d2f12cf02ba795f1c6be065c12))
* add python-multipart dependency, update CLI table styling, and refine provider error messaging. ([e2a9d3d](https://github.com/manojbajaj95/authsome/commit/e2a9d3d7e4392196c80eb72ad1762edc25d22971))
* add support for custom server base URLs ([2fde0fd](https://github.com/manojbajaj95/authsome/commit/2fde0fd0cc93f91c3494f2fd11ee9cc6041cf078))
* add support for customizable home directory and exit after printing JSON output ([cc2d830](https://github.com/manojbajaj95/authsome/commit/cc2d830f2021bdc36ebb96abcc82f720abf61456))
* add support for customizable home directory and exit after printing JSON output ([705a358](https://github.com/manojbajaj95/authsome/commit/705a3584f6a62e677eb6960aab2bf159fcf4ed4c))
* add support for hosted daemon deployments via AUTHSOME_SERVER_BASE_URL and AUTHSOME_DAEMON_URL configuration. ([0af4b01](https://github.com/manojbajaj95/authsome/commit/0af4b01c7b8cca2d07cb0e659493bccc33cac14e))
* added an interractive dashboard ([3867a96](https://github.com/manojbajaj95/authsome/commit/3867a96bb01b9cd2b3e0d9728d2004ecc2f12e6c))
* added support for notion dcr ([cd960f3](https://github.com/manojbajaj95/authsome/commit/cd960f37b57ea6738a65a3c5f7e504edef08f4c9))
* added support for notion dcr ([11ea590](https://github.com/manojbajaj95/authsome/commit/11ea590faf79d72eb5b8c6ade2bfc2265daa563d))
* allow header_prefix to be null in API key provider ([bbfc8f8](https://github.com/manojbajaj95/authsome/commit/bbfc8f8c1dc395867681cc06b4b08af72e289ef0))
* allow header_prefix to be null in API key provider ([74771c4](https://github.com/manojbajaj95/authsome/commit/74771c44ffd19221b7049eccd5f4213ee09f036f))
* client server architecture (WIP - do not merge) ([bf548e1](https://github.com/manojbajaj95/authsome/commit/bf548e146524409c921a0f54c3fdb51b11745a3e))
* green themed UI ([a826498](https://github.com/manojbajaj95/authsome/commit/a826498a1bb933afd206894bd99ffd5eb3860e87))
* implement custom error handling and propagation between daemon server and CLI client ([f536edb](https://github.com/manojbajaj95/authsome/commit/f536edbdcd48ab5a2400f1750819557a508485f1))
* introduce working implementation of client server architecture with session management. Refactor profile/provider store to reside behind app store interface and implement local version of store. ([a285172](https://github.com/manojbajaj95/authsome/commit/a285172e0404fd382726bc704a66e87b940d5cef))
* restructure client-server daemon architecture ([4bd09e0](https://github.com/manojbajaj95/authsome/commit/4bd09e018552d2b9235419373c57a317e9530337))
* **ui:** add interactive dashboard actions ([097f62a](https://github.com/manojbajaj95/authsome/commit/097f62a1946228455853844ef1993b783f2c67dc))


### Bug Fixes

* add non-interactive register confirmation flag ([57745be](https://github.com/manojbajaj95/authsome/commit/57745be9fb223cf77f9e05b1b7f46aaa6d3bbd57))
* add non-interactive register confirmation flag ([45c3a4b](https://github.com/manojbajaj95/authsome/commit/45c3a4bf910ec3d14c893dae99d93822282c9dee))
* added support for linear oauth ([680c0d9](https://github.com/manojbajaj95/authsome/commit/680c0d9950abb72cc3fde68138ebd0db7b671dea))
* added support for linear oauth ([10213c8](https://github.com/manojbajaj95/authsome/commit/10213c841a99ea1adf9983a771795f2171b7b44a))
* clear existing log handlers and log verbose status in setup_logging ([b84747e](https://github.com/manojbajaj95/authsome/commit/b84747eb7e4de92ee4e47b0aed96a43b0f264e0f))
* clear existing log handlers and log verbose status in setup_logging ([75e7c0d](https://github.com/manojbajaj95/authsome/commit/75e7c0da6ff0752eaf4045491934b37c7cfc98ac))
* **cli:** distinct exit code for cancelled credential entry ([f21047d](https://github.com/manojbajaj95/authsome/commit/f21047da250354888ec5c7b196a909b1dcb4b6cf))
* **cli:** distinct exit code for cancelled credential entry ([09fd6bc](https://github.com/manojbajaj95/authsome/commit/09fd6bc687b7aa72c702e37b60e1146c68520a8f))
* merged with develop ([a5711a7](https://github.com/manojbajaj95/authsome/commit/a5711a79a4421c05993e02c3802987dc27e32d5e))
* resolve circular import in server dependencies ([006ce3f](https://github.com/manojbajaj95/authsome/commit/006ce3f19a0b8a3eefd409aaed5049b404380441))
* ruff check fixed ([65e6b6a](https://github.com/manojbajaj95/authsome/commit/65e6b6aaaa97c63f98cbd9fdc58afd033bf8efc4))
* tests fix ([f7bec29](https://github.com/manojbajaj95/authsome/commit/f7bec299eb2360d179d684bc33e7e1d5708655e0))
* update import path for DARK_THEME_CSS to reflect module reorganization ([d97d7bf](https://github.com/manojbajaj95/authsome/commit/d97d7bf5c0415df5a23b33d1f17b4531a25778ef))
* updated overview tab ([36c2741](https://github.com/manojbajaj95/authsome/commit/36c27410ce7c265587358ce65eeb0cc414b9bce3))
* validate provider existence before retrieving connection metadata ([17580d4](https://github.com/manojbajaj95/authsome/commit/17580d431dad56d584121092291b12b38f690ee4))
* validate provider existence before retrieving connection metadata ([285f379](https://github.com/manojbajaj95/authsome/commit/285f37970d80cbf97983babce7fcb0e8ae553af5))


### Documentation

* Add design decisions for hosted version ([1551eff](https://github.com/manojbajaj95/authsome/commit/1551eff9de8d0795f67866b1350df4894002606d))
* add engineering principles and AI agent guidelines ([efaeced](https://github.com/manojbajaj95/authsome/commit/efaeced04f7ad767e7eb1fb2210863f52ad4fc66))
* expand manual testing guide to cover full CLI surface ([bbe42f2](https://github.com/manojbajaj95/authsome/commit/bbe42f246977159e79893ca8d2f2912e90fba92f))
* update CLI commands in documentation to use uvx for execution ([ab8268f](https://github.com/manojbajaj95/authsome/commit/ab8268f6420311beab7764f2518b8d9a6a9487dc))
* update CLI commands in documentation to use uvx for execution ([cc1030f](https://github.com/manojbajaj95/authsome/commit/cc1030ffda23add58009ddd8ffb690ffb644a164))
* update issue reporting guidelines to require automated GitHub CLI submission ([e388891](https://github.com/manojbajaj95/authsome/commit/e38889141d63687e73fec82b8cbcf8660abdd248))
* update issue reporting guidelines to require automated GitHub CLI submission ([1f3374d](https://github.com/manojbajaj95/authsome/commit/1f3374db102dd131eb9a5d2d9a78ea5780ec2e3d))
* use GitHub user-attachments URL for demo video ([a74f16f](https://github.com/manojbajaj95/authsome/commit/a74f16f1ef4c6e9b2abb62e68aa1cd4bcb0b08d7))

## [0.2.3](https://github.com/manojbajaj95/authsome/compare/authsome-v0.2.2...authsome-v0.2.3) (2026-05-01)


### Documentation

* add demo video to README ([36a9e18](https://github.com/manojbajaj95/authsome/commit/36a9e18a9a482baad9693f4b906226197866f70f))
* add demo video to README ([83ed25a](https://github.com/manojbajaj95/authsome/commit/83ed25a750f57e255268cee87e776c7d1d1f7961))

## [0.2.2](https://github.com/manojbajaj95/authsome/compare/authsome-v0.2.1...authsome-v0.2.2) (2026-04-29)


### Features

* add audit logging ([e130f30](https://github.com/manojbajaj95/authsome/commit/e130f309adfa8474671e9a4d2d00464e0ae1b225))
* add JSON output support to audit log command ([5ca2cd7](https://github.com/manojbajaj95/authsome/commit/5ca2cd78eee1c01b4510a42b33e56d1c11ccc942))
* expand whoami context ([2dead00](https://github.com/manojbajaj95/authsome/commit/2dead00b959f0f7b14958eede370d673792236ec))
* implement structured audit logging for CLI actions and proxy events ([e33b2d5](https://github.com/manojbajaj95/authsome/commit/e33b2d5834543fea75557efcfdf49ee6ce8297af))
* migrate --no-audit option from root command to common CLI options decorator ([93f4913](https://github.com/manojbajaj95/authsome/commit/93f4913c85c1815a649dedf8b991488ccfdac63b))
* render list output as table ([9ac6750](https://github.com/manojbajaj95/authsome/commit/9ac6750809133598b7e625a626f43f145201046d))
* show connections in inspect ([3c25b10](https://github.com/manojbajaj95/authsome/commit/3c25b10e2195835b2e9e664898b05dc4f8084063))
* show expiry in list output ([55aa376](https://github.com/manojbajaj95/authsome/commit/55aa3764f5aa0e334d278d09c697e29ade47bfe4))
* support regex proxy host urls ([a57a7de](https://github.com/manojbajaj95/authsome/commit/a57a7de0093c28fafa3805ef444f548e82e34d4c))


### Bug Fixes

* added support for regex check for API keys ([1da9d36](https://github.com/manojbajaj95/authsome/commit/1da9d36cd20cf3e85b6ec9098c9aea8b51b5e7bd))
* added support for regex check for API keys ([2d8022e](https://github.com/manojbajaj95/authsome/commit/2d8022eb112226e15d31ff50079d1975b25afe79))
* count active providers once ([8faf814](https://github.com/manojbajaj95/authsome/commit/8faf814800793ddc23911058fea5e52df4afd4b9))
* export all connections when provider omitted ([2b5ec34](https://github.com/manojbajaj95/authsome/commit/2b5ec34bf57c0b2990145bef43fce53a16d5ac08))
* export all connections when provider omitted ([622992f](https://github.com/manojbajaj95/authsome/commit/622992ffa7d1e53f877cf1b380fa9dfaa31333a8))
* harden auth proxy routing ([3c3a7ad](https://github.com/manojbajaj95/authsome/commit/3c3a7adcc9e578aaa37dde7c0fa683b5a0483022))
* harden auth proxy routing ([0fd02c6](https://github.com/manojbajaj95/authsome/commit/0fd02c6530c2d83cd35d65d41e1e2155fa60214c))
* keep proxy routing on default connections ([946576a](https://github.com/manojbajaj95/authsome/commit/946576a65229dd1252a8d1ed099349973ab65178))
* make login idempotent ([cb327fa](https://github.com/manojbajaj95/authsome/commit/cb327fa389853e71c06792db8896c2f31c96de94))
* prefer specific proxy route prefixes ([679fa77](https://github.com/manojbajaj95/authsome/commit/679fa77762d6a1293fd0d87f1d84bced59cfe471))
* preserve connected state on refresh fallback ([7c8ff9f](https://github.com/manojbajaj95/authsome/commit/7c8ff9fb5ba9f93ccca1d0454a91808dd4f5d4ce))
* respect requested login context ([2902059](https://github.com/manojbajaj95/authsome/commit/29020591e7f4fc851178371b0ea5243f8d2b2678))
* update audit log event type and add comprehensive unit tests for AuditLogger ([96b6999](https://github.com/manojbajaj95/authsome/commit/96b6999e2f162d88c7a10a006896bd7377564ebe))
* update openai export test fixture ([05bd00d](https://github.com/manojbajaj95/authsome/commit/05bd00dd7fcd864a6cd9c3b8b6c33ae27c8e6704))
* warn when refresh falls back to cached token ([7b1af48](https://github.com/manojbajaj95/authsome/commit/7b1af483583f4bf3c35b8a7010b2c2c63853bc82))

## [0.2.1](https://github.com/manojbajaj95/authsome/compare/authsome-v0.2.0...authsome-v0.2.1) (2026-04-28)


### Bug Fixes

* set connection host_url directly from resolved definition ([149b347](https://github.com/manojbajaj95/authsome/commit/149b34705a8d107d99352faac15671c4ed975112))

## [0.2.0](https://github.com/manojbajaj95/authsome/compare/authsome-v0.1.12...authsome-v0.2.0) (2026-04-28)


### ⚠ BREAKING CHANGES

* Complete internal restructuring. All public Python API has moved; CLI commands and flags are unchanged.

### Features

* add --verbose and --log-file options to CLI with loguru sinks ([0058f09](https://github.com/manojbajaj95/authsome/commit/0058f09cd643eeecde7e902c66db35b7c8b17695))
* add base URL templating support for providers ([ee172db](https://github.com/manojbajaj95/authsome/commit/ee172dbbeed1cc1761a9eb52901d22e39060cad8))
* add host_url support to auth connections and update proxy server to match based on resolved connection hosts ([73c5f72](https://github.com/manojbajaj95/authsome/commit/73c5f7259840b3e4d2caeb83e8b71c34590de602))
* add support for dynamic URL templating using {base_url} in provider definitions and CLI ([156ecf0](https://github.com/manojbajaj95/authsome/commit/156ecf0cbfb8f1fa282e73cd0df695e017353a9c))
* added support for docs in providers ([#85](https://github.com/manojbajaj95/authsome/issues/85)) ([f112275](https://github.com/manojbajaj95/authsome/commit/f11227528ae02b75eb70d5b07f5f50abc733d482))
* inject combined system and mitmproxy CA bundle into subprocess … ([#90](https://github.com/manojbajaj95/authsome/issues/90)) ([b5d042b](https://github.com/manojbajaj95/authsome/commit/b5d042b5c975ff51a06909279441c28016757837))
* silence authsome library logger by default (loguru best practice) ([2fe4c88](https://github.com/manojbajaj95/authsome/commit/2fe4c88d900eb7303e80907ea432849b25db332c))
* v0.2.0 — Vault + AuthLayer architecture, InputProvider, FlowResult ([bfd75ee](https://github.com/manojbajaj95/authsome/commit/bfd75eeae0e82f41e8e7bc5647aa55503aea08b5))


### Bug Fixes

* added support for posthiz device flow ([#81](https://github.com/manojbajaj95/authsome/issues/81)) ([9b9a485](https://github.com/manojbajaj95/authsome/commit/9b9a485460b6214e6434772ad2b2a44fae01057a))
* allow SQLite connection across threads for proxy auth injection ([536d78b](https://github.com/manojbajaj95/authsome/commit/536d78b81fb4500cd862f1e34c50b392f80d70e5)), closes [#76](https://github.com/manojbajaj95/authsome/issues/76)
* device flow ([#89](https://github.com/manojbajaj95/authsome/issues/89)) ([b596ee1](https://github.com/manojbajaj95/authsome/commit/b596ee1fafab57f846f722293ac3b6ee84062962))
* resolve ty type check errors in dcr_pkce and vault ([dc471d2](https://github.com/manojbajaj95/authsome/commit/dc471d2aac54191e1d3af7d6b7c3322560ba0813))


### Documentation

* Add documentation for current design and future direction ([7cc0e2c](https://github.com/manojbajaj95/authsome/commit/7cc0e2cc37cfa5fdae4d03e01efd31a2db3d6391))
* clarify authsome architecture direction ([e4eef7a](https://github.com/manojbajaj95/authsome/commit/e4eef7a7e22738211e7e6c81e84936d2b0f52f2b))
* Remove superpower ([f53f86c](https://github.com/manojbajaj95/authsome/commit/f53f86c1fec9b289864e2cb9e946e3238b01d5e1))

## [0.1.12](https://github.com/manojbajaj95/authsome/compare/authsome-v0.1.11...authsome-v0.1.12) (2026-04-24)


### Features

* merge develop to main ([#74](https://github.com/manojbajaj95/authsome/issues/74)) ([b88d476](https://github.com/manojbajaj95/authsome/commit/b88d476a77d71e872783874ae34c5af286720c70))


### Bug Fixes

* add host_url to bundled providers and update docs for current API ([4c756a0](https://github.com/manojbajaj95/authsome/commit/4c756a07b40b5cc20ce338dcf655948027414177))

## [0.1.11](https://github.com/manojbajaj95/authsome/compare/authsome-v0.1.10...authsome-v0.1.11) (2026-04-24)


### Features

* add configuration files for a few more OAuth2 providers ([#47](https://github.com/manojbajaj95/authsome/issues/47)) ([d587881](https://github.com/manojbajaj95/authsome/commit/d58788167b36c9f4df59d36cd912b140424f88e6))
* add proxy runner, RC publishing, and OAuth scope support ([#53](https://github.com/manojbajaj95/authsome/issues/53)) ([456d9bd](https://github.com/manojbajaj95/authsome/commit/456d9bd81128819c3281b8e88603f8d39d14cf64))


### Documentation

* overhaul authsome skill and consolidate reference docs ([#46](https://github.com/manojbajaj95/authsome/issues/46)) ([4b7dad4](https://github.com/manojbajaj95/authsome/commit/4b7dad4fef2c9eed5b951192c1080bdb8511e632))
* update authsome skill description with detailed capabilities, usage guidelines, and security policies ([#39](https://github.com/manojbajaj95/authsome/issues/39)) ([6c0bf89](https://github.com/manojbajaj95/authsome/commit/6c0bf890c9ff61ce7faabb2d57da36403e849751))

## [0.1.10](https://github.com/manojbajaj95/authsome/compare/authsome-v0.1.9...authsome-v0.1.10) (2026-04-22)


### Features

* added redirect url  in popup broswer Ui ([#36](https://github.com/manojbajaj95/authsome/issues/36)) ([b292017](https://github.com/manojbajaj95/authsome/commit/b29201776b06779e8486bbca53e3158d649bd915))
* added support for ashby ([#42](https://github.com/manojbajaj95/authsome/issues/42)) ([b37724e](https://github.com/manojbajaj95/authsome/commit/b37724e52cc88c729971a0b5d30a80abc03df5aa))
* replace reset flow with force flag and reorganize provider lifecycle commands into logout, revoke, and remove ([#32](https://github.com/manojbajaj95/authsome/issues/32)) ([66b0583](https://github.com/manojbajaj95/authsome/commit/66b0583c5be921f83aaf1ade633ea240e572ab4a))


### Documentation

* refresh readme ([#30](https://github.com/manojbajaj95/authsome/issues/30)) ([12cbfae](https://github.com/manojbajaj95/authsome/commit/12cbfae72f57be82431a3c5bf8d81b1377e3f442))

## [0.1.9](https://github.com/manojbajaj95/authsome/compare/authsome-v0.1.8...authsome-v0.1.9) (2026-04-21)


### Features

* add --version / -v flag to CLI ([#22](https://github.com/manojbajaj95/authsome/issues/22)) ([688aefb](https://github.com/manojbajaj95/authsome/commit/688aefba7238909e2ee0fbf111b66e66e7996f8a))
* Add github templates and CONTRIBUTING.md ([#20](https://github.com/manojbajaj95/authsome/issues/20)) ([98e0136](https://github.com/manojbajaj95/authsome/commit/98e01369459d1652c86df5d090cea15ed17fcef7))
* introduce secure browser-based bridge for sensitive input collection and remove CLI credential flags ([#28](https://github.com/manojbajaj95/authsome/issues/28)) ([8302b10](https://github.com/manojbajaj95/authsome/commit/8302b105bf9ef0ef00a1da396cb91f0c134d54ce))
* provider for klaviyo added ([#25](https://github.com/manojbajaj95/authsome/issues/25)) ([32038af](https://github.com/manojbajaj95/authsome/commit/32038afaa0cb5b209a26a1cdccf2aa0572f17f59))


### Bug Fixes

* redirect url explicitly mentioned in register provider ([#27](https://github.com/manojbajaj95/authsome/issues/27)) ([78b6eeb](https://github.com/manojbajaj95/authsome/commit/78b6eeb9e2cf5ecbbc727dbb54a16af5144584d0))
* use model_dump(mode="json") to serialize datetime fields in CLI ([#23](https://github.com/manojbajaj95/authsome/issues/23)) ([551239a](https://github.com/manojbajaj95/authsome/commit/551239a7b0e37b7c2ce4b89c946e9ec05339ae49))


### Documentation

* add portable authsome spec v1 ([#26](https://github.com/manojbajaj95/authsome/issues/26)) ([307aa2c](https://github.com/manojbajaj95/authsome/commit/307aa2c53721009b5d8a4fdc7ff1dfcf24cb89bf))

## [0.1.8](https://github.com/manojbajaj95/authsome/compare/authsome-v0.1.7...authsome-v0.1.8) (2026-04-21)


### Features

* add client record type to function docstring ([1be12a9](https://github.com/manojbajaj95/authsome/commit/1be12a93638f8f33ef907802878620f339956b2a))


### Bug Fixes

* Fix the store key bug ([72433e7](https://github.com/manojbajaj95/authsome/commit/72433e73c5f1c5593b7da6b5109c0409d87164b5))

## [0.1.7](https://github.com/manojbajaj95/authsome/compare/authsome-v0.1.6...authsome-v0.1.7) (2026-04-21)


### Features

* implement common_options decorator to support global CLI flags across all commands ([72d08ed](https://github.com/manojbajaj95/authsome/commit/72d08ed9345f760bc79a9cafaa05da2dea99992b))

## [0.1.6](https://github.com/manojbajaj95/authsome/compare/authsome-v0.1.5...authsome-v0.1.6) (2026-04-21)


### Bug Fixes

* update incorrect imports and fix README ([5ca9da0](https://github.com/manojbajaj95/authsome/commit/5ca9da0e8de2e71b438cfbe86080453910668e2d))

## [0.1.5](https://github.com/manojbajaj95/authsome/compare/authsome-v0.1.4...authsome-v0.1.5) (2026-04-21)


### Features

* add 29 new API provider configurations to bundled_providers ([#9](https://github.com/manojbajaj95/authsome/issues/9)) ([f9d8af4](https://github.com/manojbajaj95/authsome/commit/f9d8af4685b0b6339373f3bc204a9e826b83a5a5))
* enable CLI support for providing client credentials and API keys during login; and persist aforementioned credentials in profile store ([#10](https://github.com/manojbajaj95/authsome/issues/10)) ([7c960db](https://github.com/manojbajaj95/authsome/commit/7c960db5956fa5b30bfbd7d091671ef0a21a1084))


### Documentation

* rewrite README with agent-first positioning and badges ([94e090b](https://github.com/manojbajaj95/authsome/commit/94e090beaf2b40ab3b318bef2fd85ea668d09342))

## [0.1.4](https://github.com/agentr-labs/authsome/compare/authsome-v0.1.3...authsome-v0.1.4) (2026-04-20)


### Bug Fixes

* update command execution to use double-quoted strings and process in shell ([157edad](https://github.com/agentr-labs/authsome/commit/157edad42f253f98d6767ce524972f52c47cdb39))

## [0.1.3](https://github.com/agentr-labs/authsome/compare/authsome-v0.1.2...authsome-v0.1.3) (2026-04-20)


### Documentation

* add CLI reference and provider registration guides and update main skill documentation ([#5](https://github.com/agentr-labs/authsome/issues/5)) ([3d9d3b3](https://github.com/agentr-labs/authsome/commit/3d9d3b345e6db1f20245dc87a480266c089c580a))

## [0.1.2](https://github.com/universal-mcp/authsome/compare/authsome-v0.1.1...authsome-v0.1.2) (2026-04-17)


### Features

* Improve cli and test public pkce oauth flow ([27c8d50](https://github.com/universal-mcp/authsome/commit/27c8d50fac896d9d84e51042fc0b37cb07131eb3))
* Show separate custom and bundled providers; highlight connections spearately; tested pkce public oauth flow ([0924521](https://github.com/universal-mcp/authsome/commit/092452168fd0404eca4fc1afc96fdab7397974ab))

## [0.1.1](https://github.com/universal-mcp/authsome/compare/authsome-v0.1.0...authsome-v0.1.1) (2026-04-17)


### Features

* add Google and Okta providers and reformat GitHub provider scopes ([cc02780](https://github.com/universal-mcp/authsome/commit/cc0278017bf3c03c5315132eeb9657bbe2583f9e))
* add Linear provider and standardize PKCE callback port to 7999 while updating GitHub flow to standard PKCE ([15b1069](https://github.com/universal-mcp/authsome/commit/15b1069b8cdf2c3b9a7e2c6496aa88355d2bd053))
* implement CLI with full command set ([5724f3c](https://github.com/universal-mcp/authsome/commit/5724f3cd0768cb69c6c8cb55d94af7e69232d35d))
* implement initial version of core auth framework ([3c980b4](https://github.com/universal-mcp/authsome/commit/3c980b4b60b24cba4e53802a291f05f62a6e2929))
