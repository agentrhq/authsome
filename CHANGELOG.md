# Changelog

## [0.7.2](https://github.com/agentrhq/authsome/compare/authsome-v0.7.1...authsome-v0.7.2) (2026-06-17)


### Features

* add agent detail view ([256753f](https://github.com/agentrhq/authsome/commit/256753f3200701f2382319db78c9d5f4e4cbd162))
* Improve agents page ([02658d1](https://github.com/agentrhq/authsome/commit/02658d1aee7211a446eb21b785c8ce0482c31d7c))
* merge agent detail view with enhanced agents list and review fixes ([749e703](https://github.com/agentrhq/authsome/commit/749e7032746d54eadc0ba408979de3682fcedcb9))


### Bug Fixes

* simplify agent detail metadata layout ([43f9b4e](https://github.com/agentrhq/authsome/commit/43f9b4ebde17717f243ebe972e567c1c4db96595))


### Documentation

* fix self-hosting quick start and first-run flow ([48f7c6f](https://github.com/agentrhq/authsome/commit/48f7c6fbb7d592a18c5bd101433b00bce03f20f3))
* updated self hosting docs ([57c8409](https://github.com/agentrhq/authsome/commit/57c8409e6eea9190e672531bad7b83b959e2bab8))

## [0.7.1](https://github.com/agentrhq/authsome/compare/authsome-v0.7.0...authsome-v0.7.1) (2026-06-17)


### Features

* improve connections and providers page design ([ab122f6](https://github.com/agentrhq/authsome/commit/ab122f60d767b0b3642b85dbd3cef58fc2736a1d))
* Improve settings page ([3e04eff](https://github.com/agentrhq/authsome/commit/3e04eff5a4e6c57db8499957561bf935eb088446))
* improve UI design system, layouts, and remaining pages ([969c068](https://github.com/agentrhq/authsome/commit/969c068e23d4a37b50dfd307415524df4faa2b3a))


### Bug Fixes

* **ui:** remove sidebar gaps in main and settings layouts ([e0e6498](https://github.com/agentrhq/authsome/commit/e0e6498b35e93cec444c8c998d321de985ccaaed))

## [0.7.0](https://github.com/agentrhq/authsome/compare/authsome-v0.6.4...authsome-v0.7.0) (2026-06-16)


### ⚠ BREAKING CHANGES

* replace init and scan with authsome onboard

### Features

* add auth session store contract ([604d18e](https://github.com/agentrhq/authsome/commit/604d18e24a4682aa8330ba0a5c2dd925344c2af5))
* add global connection fallback registry ([9c50afc](https://github.com/agentrhq/authsome/commit/9c50afc585158127eb98154221b45ea270faf68e))
* add paged audit event queries ([3a1a564](https://github.com/agentrhq/authsome/commit/3a1a564673e054be14880c44782c42fcc9741ce6))
* add production backend config ([f4a6cf5](https://github.com/agentrhq/authsome/commit/f4a6cf5a16f9eb711f943b97226db442149b3107))
* add ProviderType classification and JSONC support for providers ([dfabe6c](https://github.com/agentrhq/authsome/commit/dfabe6cfcc7e1c5e2c21f5c30000ead706fa9e01))
* add ProviderType classification and JSONC support for providers ([ea42284](https://github.com/agentrhq/authsome/commit/ea42284ff80efcb52384ddb43ab18a8c479d67f7)), closes [#362](https://github.com/agentrhq/authsome/issues/362)
* add root health check ([3b8cfd0](https://github.com/agentrhq/authsome/commit/3b8cfd01bb7ddd2c1e5cd2e2781138463a186b22))
* add store migrations and postgres pooling ([8a817d9](https://github.com/agentrhq/authsome/commit/8a817d99c218f95e3af6b8a80eeae0c0c645dc78))
* added support for agents ([4c79bb0](https://github.com/agentrhq/authsome/commit/4c79bb0a5906343be3ad464fb709a3a116568f1d))
* derive agent identity from a single private-key env var ([0890c0b](https://github.com/agentrhq/authsome/commit/0890c0bc61946e07015c7fc83fdb6bf8f8899181))
* derive agent identity from a single private-key env var ([d9d2c60](https://github.com/agentrhq/authsome/commit/d9d2c60563dde88cc4b585f16b0372f65346c589))
* enforce role-aware audit event queries ([08446d1](https://github.com/agentrhq/authsome/commit/08446d1e2837c2553fd6c7b537161dc2c83367bf))
* expose global connection CLI controls ([0975ab8](https://github.com/agentrhq/authsome/commit/0975ab82e04f9fe117cf2e73d976488d436da004))
* global connection pointers ([16af935](https://github.com/agentrhq/authsome/commit/16af935137c9874b3d87ba272e4aba4a73968a65))
* implement custom provider management with CRUD support, registration schema updates, and a dedicated UI form. ([8dbf579](https://github.com/agentrhq/authsome/commit/8dbf579e21d89b737c5fc15910572df1296c10f9))
* implement custom provider management with CRUD support, registration schema updates, and a dedicated UI form. ([8f4029e](https://github.com/agentrhq/authsome/commit/8f4029ec7e96e9d107d1e4029ff00d8fb4911504))
* implement tooltip help text and collapsible advanced sections in custom provider form ([54ba7b2](https://github.com/agentrhq/authsome/commit/54ba7b23e2949cf4b162ab2a31769929239110c6))
* replace init and scan with authsome onboard ([d9936d5](https://github.com/agentrhq/authsome/commit/d9936d569956cb852c07516e0d1043fda8dcb2b5)), closes [#434](https://github.com/agentrhq/authsome/issues/434)
* select redis runtime state ([d828d2b](https://github.com/agentrhq/authsome/commit/d828d2b775c526ef7c8ac700a0396afe0ff88d77))
* show global connections in dashboard ([b21f5b1](https://github.com/agentrhq/authsome/commit/b21f5b11b21daa70fc7cd2146bbe6a98d6ce19b6))
* show scoped audit log in dashboard ([0b8d752](https://github.com/agentrhq/authsome/commit/0b8d752392eb8d87277a423501df012b127b8fb8))
* stateless production deployments ([c55448d](https://github.com/agentrhq/authsome/commit/c55448dca085c63417d3a51735edab37e0e657b7))
* **ui:** add authenticated layout with sidebar and breadcrumbs ([d27267f](https://github.com/agentrhq/authsome/commit/d27267fc029b4bf166613bc05437fa24a5df6aa4))
* **ui:** redesign provider/connection detail pages and fix accent token ([384dd20](https://github.com/agentrhq/authsome/commit/384dd2094e68fd7d2554dfd3b04cb86ea8883b5b))
* **ui:** redesign provider/connection detail pages and fix accent token ([ae806a3](https://github.com/agentrhq/authsome/commit/ae806a311683531cd74c9a8df959f3365485d03a))
* user scoped audit log ([151e0af](https://github.com/agentrhq/authsome/commit/151e0afa186c5b11f1072637ba5728721bd611ef))


### Bug Fixes

* 'broker' to 'gateway' in README ([976d4a5](https://github.com/agentrhq/authsome/commit/976d4a59f4419d39ac0ab33fd7ab30bd0167e210))
* add env field to config and disable PostHog in non-prod environments ([c1a9f66](https://github.com/agentrhq/authsome/commit/c1a9f6639387a5537b7c75128e469281064a3bd4))
* address production readiness review ([b374fb4](https://github.com/agentrhq/authsome/commit/b374fb49a01a8706842f76c905f48451ed71e5e8))
* atomically consume redis pending claims ([b754b80](https://github.com/agentrhq/authsome/commit/b754b80227906925670dbe4adb7844ac0be012b9))
* avoid audit shutdown deadlock ([d54c415](https://github.com/agentrhq/authsome/commit/d54c4159bac2145e62b1ad1e89b8570284cdf932))
* avoid hardcoded compose secrets ([5a15e41](https://github.com/agentrhq/authsome/commit/5a15e4179b5c14c8c2dab986fcdf461a39b82b0c))
* bind store transactions to pooled connection ([9c141f3](https://github.com/agentrhq/authsome/commit/9c141f3c81c1412ee51a1f3cd1a7e967dbc68af7))
* clarify clickable surface hover states ([e5ee9b9](https://github.com/agentrhq/authsome/commit/e5ee9b9d3e265f61b350d1b6c9ef26f5f38ce56d))
* clarify compose master key secret ([ee25d5c](https://github.com/agentrhq/authsome/commit/ee25d5ce4922c0c74efa2d314e6c402fe2e2ee54))
* clean redis auth session indexes ([60e21e1](https://github.com/agentrhq/authsome/commit/60e21e1ceb1ab7611fa02edd576cb0e5f4b11a18))
* clean up failed runtime startup ([448c8b2](https://github.com/agentrhq/authsome/commit/448c8b24174ea4224faf0a713cd358c098c1b32b))
* close redis client on ping failure ([ea0fd94](https://github.com/agentrhq/authsome/commit/ea0fd94e5bff9f652899334a3a485293cde07218))
* env field in config, PostHog no-op in dev/test ([dd6f8d2](https://github.com/agentrhq/authsome/commit/dd6f8d21b57c6e0f972dc9673680167a18481dba))
* exclude local build artifacts from package ([69b263b](https://github.com/agentrhq/authsome/commit/69b263b071432bd0f139154d30c2680d5b55a429))
* harden container startup path ([ff3d542](https://github.com/agentrhq/authsome/commit/ff3d5426a51ae0ab9a74e4cb67f95f92cd1f62b5))
* hide optional asyncpg import from ty ([eb37f84](https://github.com/agentrhq/authsome/commit/eb37f84c9fbbc1b940eacaa8baa2afbb09ad59c7))
* keep connections page unfiltered after detail navigation ([13cbd0d](https://github.com/agentrhq/authsome/commit/13cbd0d54db4250c2a7ab6a16dcfde1a15ba9bdb))
* lazy load postgres driver ([a87328f](https://github.com/agentrhq/authsome/commit/a87328f578c734e9f58de93a41e65e6bdf73b6cb))
* pass global connection props to connections page ([e6e51fd](https://github.com/agentrhq/authsome/commit/e6e51fddf3134c39d385afcb4c53b24616d4fcac))
* polish connection action feedback ([8d93438](https://github.com/agentrhq/authsome/commit/8d934387fc10b5ac1ce694a895139d1c3d3684b3))
* polish dashboard connection flows ([913ec09](https://github.com/agentrhq/authsome/commit/913ec0984c533356d7f06904516109c0788e182d))
* polish dashboard connection flows ([8f35bf1](https://github.com/agentrhq/authsome/commit/8f35bf1216813afa21fe893f9411f3dda70cf388))
* preserve pop replay auth errors ([c68de27](https://github.com/agentrhq/authsome/commit/c68de27a155cacde3a21bef6e446857921a4d7f4))
* prevent daemon error card clipping ([29d2813](https://github.com/agentrhq/authsome/commit/29d28137ad9c6c930dfeba3b340c30b6dfe254a5))
* recover from 409 when concurrent agents register the same DID ([3a9f17e](https://github.com/agentrhq/authsome/commit/3a9f17e9bce010d197b639f6af57e36b2932008a))
* refine provider and connection dashboard states ([da7a401](https://github.com/agentrhq/authsome/commit/da7a4017b14ac3d162bbba05ab8beb23cba65281))
* remove blocking future result call in audit event persistence to prevent thread deadlock ([e33fc3c](https://github.com/agentrhq/authsome/commit/e33fc3c18e6c24eb5a5739e14f7cfbe5f47933f6))
* remove duplicate health route ([5457d10](https://github.com/agentrhq/authsome/commit/5457d10940613636adec71b322d02a6963f921d0))
* require production backend URLs ([be5c646](https://github.com/agentrhq/authsome/commit/be5c646b5ba3762f1627067f8f5e5d0af2ab453e))
* restore logo dev token ([de814ee](https://github.com/agentrhq/authsome/commit/de814ee15ed6d06520093e55d4197e0a5d2ee72f))
* restore sqlite store branch ([7a39de6](https://github.com/agentrhq/authsome/commit/7a39de61d0cbf993dee307a556249ab147b57e31))
* ruff check ([8d94e4d](https://github.com/agentrhq/authsome/commit/8d94e4d37f9081109d49b159354a3c86143635e6))
* **ui:** replace Button render-as-link with Link+buttonVariants; img→Image, a→Link ([67fbe48](https://github.com/agentrhq/authsome/commit/67fbe483ddb64cb615c50f70f6df141441f0e476))


### Documentation

* add production self-hosting path ([ea4eaa7](https://github.com/agentrhq/authsome/commit/ea4eaa791bd3a47214304d6d7b3e2406eae930e9))
* describe scoped audit log access ([80cb249](https://github.com/agentrhq/authsome/commit/80cb2499844ac9373420dff1a895e0ac0641f892))
* design stateless production deployments ([80e5ad9](https://github.com/agentrhq/authsome/commit/80e5ad9218f6e57c3795451c6a63ee76928c4ff6))
* design user-scoped audit log ([224be18](https://github.com/agentrhq/authsome/commit/224be18855ce222ef99acbaa84e35cf3be949924))
* plan user-scoped audit log ([32a7275](https://github.com/agentrhq/authsome/commit/32a7275b0c122bb80344b9f1a989340af4947df8))
* refine credential broker comparison ([44b37bf](https://github.com/agentrhq/authsome/commit/44b37bf6f0bd95ba2001220b6ca2733d7f6c439b))
* refresh Mintlify site for v0.7 and remove stale profile/library references ([6151535](https://github.com/agentrhq/authsome/commit/61515356a2c2828f4e3d810b10148cf71a5c44da))
* refresh Mintlify site for v0.7 and remove stale references ([6204a47](https://github.com/agentrhq/authsome/commit/6204a474d7270d1c0d082bf75e41df934551fdca))
* unified messaging ([841c0d6](https://github.com/agentrhq/authsome/commit/841c0d698b545e90d5d32583448dee656aa0af2a))
* updated broker credentials comparison ([9253aa8](https://github.com/agentrhq/authsome/commit/9253aa8d97cf0255e94fa74662f7de0ba6682a6d))

## [0.6.4](https://github.com/agentrhq/authsome/compare/authsome-v0.6.3...authsome-v0.6.4) (2026-06-09)


### Bug Fixes

* keep dashboard sidebar fixed in providers page ([168c51f](https://github.com/agentrhq/authsome/commit/168c51f5604960bd82fd0e73c7b359f8b23f6023))

## [0.6.3](https://github.com/agentrhq/authsome/compare/authsome-v0.6.2...authsome-v0.6.3) (2026-06-09)


### Chores

* manually bump yanked version

## [0.6.2](https://github.com/agentrhq/authsome/compare/authsome-v0.6.1...authsome-v0.6.2) (2026-06-09)


### Features

* add bundled providers for 14 Google Workspace and API services ([a389bf7](https://github.com/agentrhq/authsome/commit/a389bf7078cbe44e61bfe1c3c5f6b7b5436b6429))
* add bundled providers for 14 Google Workspace and API services ([0a88fef](https://github.com/agentrhq/authsome/commit/0a88fef824de7a0de94b5fbeeef0092dbebd0711))
* add bundled providers for Jira, Confluence, YouTube, Vertex AI, Todoist, Cloudflare, Outlook, Word, Calendar, and Zoom ([2e7d2f6](https://github.com/agentrhq/authsome/commit/2e7d2f6dae0b2a98516dd44d0c447950639fb061))
* add client_secret_handling support for basic auth and update OAuth flows accordingly ([b3bceae](https://github.com/agentrhq/authsome/commit/b3bceaeae93cd9a6d0dafd39ef4fd8ae237992ff))
* add Reddit OAuth2 bundled provider ([2d66ac9](https://github.com/agentrhq/authsome/commit/2d66ac96ab220a374e1bcbddc823b341f842b907))
* add required field support to InputField and update UI components to respect optionality ([19a40fe](https://github.com/agentrhq/authsome/commit/19a40fe91cb228d21ffc25cd598bf11fe032007c))
* add required field support to InputField and update UI components to respect optionality ([3b7b175](https://github.com/agentrhq/authsome/commit/3b7b175b70a40958808264621d6777835bd56c16))
* enable admin browser sessions for provider revocation and add error handling to UI button ([73c5843](https://github.com/agentrhq/authsome/commit/73c58437b61d5ece377d07fbed2e7f4621cc970b))
* Fix failing tests ([6fe1107](https://github.com/agentrhq/authsome/commit/6fe11073c829a86d7e114b04d1bfa4d367d67c24))
* hide configuration UI for API key providers ([39caabe](https://github.com/agentrhq/authsome/commit/39caabec157a66bac09d28c73dd7e852cdc2c99b))
* implement provider and connection detail endpoints with UI support for configuration management and status monitoring ([11d2166](https://github.com/agentrhq/authsome/commit/11d21661096d7680b9d756c7332714945a34319c))
* Improve UI ([9f622ec](https://github.com/agentrhq/authsome/commit/9f622ec1ab7ec50643c517a81246ace01ec8e476))
* Improve UI ([3a7a7b8](https://github.com/agentrhq/authsome/commit/3a7a7b8aea8bde69707f6f0e63e356408518a19e))


### Bug Fixes

* bundle static UI assets into wheel ([74be6b9](https://github.com/agentrhq/authsome/commit/74be6b97243bdf1c690f19881084b66d60d702ae))
* bundle static UI assets into wheel ([745f1a2](https://github.com/agentrhq/authsome/commit/745f1a28d41e016dcb7650e8622dbbb0cb93987b))
* use artifacts instead of force-include for wheel UI assets ([f345a18](https://github.com/agentrhq/authsome/commit/f345a189bf5db5252487fa4101487dc7a3935a1e))

## [0.6.1](https://github.com/agentrhq/authsome/compare/authsome-v0.6.0...authsome-v0.6.1) (2026-06-06)


### Bug Fixes

* build action ([5b5a55d](https://github.com/agentrhq/authsome/commit/5b5a55d2bff76979ff5186092050aa31cca85cbf))

## [0.6.0](https://github.com/agentrhq/authsome/compare/authsome-v0.5.0...authsome-v0.6.0) (2026-06-06)


### ⚠ BREAKING CHANGES

* Cleaner architechture, multi server compatible identities and cleaner ui

### feature

* Cleaner architechture, multi server compatible identities and cleaner ui ([f661d8d](https://github.com/agentrhq/authsome/commit/f661d8d360233557d460dd9502525b101720073d))


### Features

* add Dockerfile, docker-compose, and self-hosting guide ([c7455c0](https://github.com/agentrhq/authsome/commit/c7455c00edd5fc325c3708998cbd978317f882af))
* add Dockerfile, docker-compose, and self-hosting guide ([6231674](https://github.com/agentrhq/authsome/commit/62316746108a60077814e4b5954d59d6c5a0314b)), closes [#366](https://github.com/agentrhq/authsome/issues/366)
* Add logos and description for all bundled providers ([33e13f9](https://github.com/agentrhq/authsome/commit/33e13f96259bfcc196c7d0f0ad3cdc09da3fe905))
* add provider dashboard metadata ([635285a](https://github.com/agentrhq/authsome/commit/635285a56550e390cfb19fc01321b6fca34cf283))
* add static Next.js dashboard ([7c46cd8](https://github.com/agentrhq/authsome/commit/7c46cd895d860f2eecfb5a726cace09afe4dfc49))
* add static Next.js dashboard ([e0a2cd9](https://github.com/agentrhq/authsome/commit/e0a2cd915843901256f9a0d6b90a0016e483611a))
* Build dependencies ([2705e8e](https://github.com/agentrhq/authsome/commit/2705e8e6e55a2906d5115502d65f97413f888d84))
* improve scan to cover all typical env file locations ([364f3e5](https://github.com/agentrhq/authsome/commit/364f3e531b8cc7707bf3a6df6dd94f03ee00ba50))
* improve scan to cover all typical env file locations ([96fd514](https://github.com/agentrhq/authsome/commit/96fd514adbda5cc3eb1bc38007d35f71de14bc5a))
* replace Python dashboard fallback with built Next.js static UI ([98a3351](https://github.com/agentrhq/authsome/commit/98a3351c56cea43b417c989b4f197d224d015c7a))
* Simplify identity portability ([ad23d60](https://github.com/agentrhq/authsome/commit/ad23d6075474c008c58c4447138ed0212a783f64))
* **ui:** redirect to connections view after successful provider login ([19bdf05](https://github.com/agentrhq/authsome/commit/19bdf0546e6e8fcb26d86553d8f0c80fe826a597))
* **ui:** redirect to connections view after successful provider login ([60931a0](https://github.com/agentrhq/authsome/commit/60931a027b505b3937ab7161f8c7c43d8b3798a4)), closes [#355](https://github.com/agentrhq/authsome/issues/355)
* Update docs ([07dbb87](https://github.com/agentrhq/authsome/commit/07dbb8705fc51ec4e920ec47b0517181bb60ca79))


### Bug Fixes

* allow explicit authsome config home ([7faf61f](https://github.com/agentrhq/authsome/commit/7faf61f9d896e9a18214c8cc9cf774b96895a2a3))
* cache identity registration per daemon ([668f91a](https://github.com/agentrhq/authsome/commit/668f91a54aebead5f62e58e35f3e5fe3b8032347))
* Cleaner design ([301d353](https://github.com/agentrhq/authsome/commit/301d353c5e9e4f42259adc5223676be507de8425))
* **docs:** remove all broken links to missing pages ([cac5f9f](https://github.com/agentrhq/authsome/commit/cac5f9f2c48e29291d61275470734c4440814c60))
* inherit ServerConfig from AuthsomeConfig for consistent home resolution ([cf95c6c](https://github.com/agentrhq/authsome/commit/cf95c6c5da525030e8e5f7e8006eb2211f0ef535))
* install pnpm before setup-node to fix CI cache resolution ([0dd5291](https://github.com/agentrhq/authsome/commit/0dd5291ffbe673e8a9c6c39a7128bed41f474303))
* move dashboard auth flow to Next routes ([52fe7dc](https://github.com/agentrhq/authsome/commit/52fe7dc5c3320a46fdddd8e21e3e876d5485179d))
* remove populate_by_name and redundant validation_alias from settings ([9ee46a6](https://github.com/agentrhq/authsome/commit/9ee46a651ee16a4f78824dd86056ddfc39a4b152))
* Remove type checking hacks ([10f6e8a](https://github.com/agentrhq/authsome/commit/10f6e8ae41dc019c233b341555afffc072eb68e3))
* resolve pre-commit failures ([b96d593](https://github.com/agentrhq/authsome/commit/b96d5938832b861880214fa7eb9b5dd5006abc42))
* **ui:** replace setState-in-effect with lazy useState initializers ([ff592fd](https://github.com/agentrhq/authsome/commit/ff592fde5924329f1f8c1060509e22746c1c296b))


### Documentation

* remove stale authsome skill commands ([fc51d29](https://github.com/agentrhq/authsome/commit/fc51d2919a9be42bab146439b6ceb4fd5c3829df))
* Update context on design philosophy behind authsome ([5933be4](https://github.com/agentrhq/authsome/commit/5933be47de734839d2e65f03b2a783c70acb75fa))
* Update documentation ([d76304a](https://github.com/agentrhq/authsome/commit/d76304a911ab2a9f7049079cfe1e0b648a11e79f))
* Update documentation ([30ec8d4](https://github.com/agentrhq/authsome/commit/30ec8d4ff6ddf1c16061156067207ac9b68e3bfb))
* Update documentation to correctly reference current authsome state ([54d7c3a](https://github.com/agentrhq/authsome/commit/54d7c3a200c1eaa0765bfcfb4497b9f238721e90))

## [0.5.0](https://github.com/agentrhq/authsome/compare/authsome-v0.4.2...authsome-v0.5.0) (2026-05-29)


### ⚠ BREAKING CHANGES

* existing local installs have an unclaimed identity under local@authsome.internal and are rejected until the user registers a principal (email+password) and claims the identity.
* existing Fernet-encrypted vaults cannot be read back; migration requires re-importing credentials.
* mount dashboard at / instead of /ui

### Features

* add admin audit dashboard ([1bc5044](https://github.com/agentrhq/authsome/commit/1bc504472ace6629e88a9ad06531c927ff31da26))
* add Anthropic and Gemini bundled providers ([1e47c48](https://github.com/agentrhq/authsome/commit/1e47c48b07ee76d5a9dfdd58c238150316dca2a0))
* add Anthropic and Gemini bundled providers ([e788328](https://github.com/agentrhq/authsome/commit/e78832884f69492978a097587374d0e3853371db))
* add browser SSO via Chrome cookie reading (browser-cookie3) ([aeb4263](https://github.com/agentrhq/authsome/commit/aeb426357f43abe6a13b3684de135c3e6e110166))
* Add docs for design of principal roles and audit ([de33f8a](https://github.com/agentrhq/authsome/commit/de33f8a5148ff9f6d30e5b392b76e57af751b5ed))
* add principal_role parameter to AuthService and dependency injection routes ([7d43b56](https://github.com/agentrhq/authsome/commit/7d43b567c8c3e0eec8e4ef33b7fd0eb53cb431b4))
* browser SSO via Chrome cookie reading (browser-cookie3) ([7607600](https://github.com/agentrhq/authsome/commit/7607600eba2e62125aac801cd09ad28f3948cf3c))
* implement audit events and principal roles ([9503710](https://github.com/agentrhq/authsome/commit/950371088ba46e5f38086dd0c7fccabd0333f83d))
* implement audit events and principal roles ([0ed077b](https://github.com/agentrhq/authsome/commit/0ed077b9df60808f840d37460de3a75c5dd8303c))
* move daemon management commands from admin module to main CLI ([397a8e8](https://github.com/agentrhq/authsome/commit/397a8e8e0aa1142a432ba1af73a3f4235ecccfd9))
* move daemon management commands from admin module to main CLI ([af356d5](https://github.com/agentrhq/authsome/commit/af356d5f4ff435488484c736516cdad1f61780f4))
* replace flat master-key vault encryption with Argon2id KEK/DEK model ([b76903d](https://github.com/agentrhq/authsome/commit/b76903d74b61ff469a4221d41e95713a04bdaeb2))
* respect AUTHSOME_DAEMON_URL in all daemon control paths ([fa23037](https://github.com/agentrhq/authsome/commit/fa23037d73c6c1cc2892654eca6a5d6931f79243))
* respect AUTHSOME_DAEMON_URL in all daemon control paths ([1ba904b](https://github.com/agentrhq/authsome/commit/1ba904bf0db74fb20e43a370fecf559e97e1f95c))
* server store refactor ([acb2013](https://github.com/agentrhq/authsome/commit/acb20132f04ef05c81f9d16ce6c2685607ee4171))


### Bug Fixes

* added support for cookie expiry date ([5ea8aa9](https://github.com/agentrhq/authsome/commit/5ea8aa977e8d044420d4f469c047319ed1c3765c))
* Fix incorrect posthog key and remove unnecessary tests ([77c7bb7](https://github.com/agentrhq/authsome/commit/77c7bb7b24e9bd4f8135685127ff53617e9a73b1))
* Fix incorrect posthog key and remove unnecessary tests ([8f8d9b9](https://github.com/agentrhq/authsome/commit/8f8d9b9e59f6896dca3f3b6b14d33f363d4738b3))
* refresh DCR provider client on replace ([9af604d](https://github.com/agentrhq/authsome/commit/9af604d80d023ef0762f5f1c6ae41857302de0de))
* refresh DCR provider client on replace ([595de28](https://github.com/agentrhq/authsome/commit/595de28f25f5526f63cf6e9136291d86c6972754))
* remove extraneous admin command argument from daemon subprocess invocation ([2c43de6](https://github.com/agentrhq/authsome/commit/2c43de6449ad38f95bd80c6e6d1901b8526e952c))
* ruff check ([6dbef78](https://github.com/agentrhq/authsome/commit/6dbef782679cdb82a0735dfd879234316d34efad))


### Reverts

* display input fields for dcr providers ([6c108cb](https://github.com/agentrhq/authsome/commit/6c108cb44f5c63ee0c069f941ff2302e9f7a9ff3))


### Documentation

* correct manual testing guide against the current CLI surface ([0a7c379](https://github.com/agentrhq/authsome/commit/0a7c379c007afe1b01d48341b2df14f199411841))
* update manual testing guide for the unified claim flow ([70e5539](https://github.com/agentrhq/authsome/commit/70e5539a5924a96b7864862444957dc4e385f49e))


### Code Refactoring

* mount dashboard at / instead of /ui ([f8cf936](https://github.com/agentrhq/authsome/commit/f8cf93663f7a4bc757082155c6f4d6bde51da366))
* unify local and hosted into a single deployment flow ([63bd4c9](https://github.com/agentrhq/authsome/commit/63bd4c90aa10e31d4b11ad9b190f00f1e1e1a316))

## [0.4.2](https://github.com/agentrhq/authsome/compare/authsome-v0.4.1...authsome-v0.4.2) (2026-05-25)


### Features

* add device flow verification fields to auth schemas and CLI JSON output ([c24779c](https://github.com/agentrhq/authsome/commit/c24779c6df5939602f06bc3b18c5e270963cbdfc))
* auto-create env handle identities ([72e1b35](https://github.com/agentrhq/authsome/commit/72e1b350cd13cd9923eb8e2f408c599cfaf98497))
* env backed identity design ([e1662b5](https://github.com/agentrhq/authsome/commit/e1662b51963a6dac66d6d6f30f654ad04fc96736))
* improve copy-to-clipboard functionality with browser fallback and UI feedback ([02daa81](https://github.com/agentrhq/authsome/commit/02daa8182ed9d22abe75670db09286979844223d))
* restructure CLI commands under provider and admin namespaces ([7b4b31a](https://github.com/agentrhq/authsome/commit/7b4b31ad4fbc5bb8ffc2c1f60e0d69268844558e))
* restructure CLI commands under provider and admin namespaces ([a326e3f](https://github.com/agentrhq/authsome/commit/a326e3f1c43d2037124f0ba49751c8a5af0daa81))
* simplify Client ID label and implement robust cross-browser copy-to-clipboard logic ([d763f7f](https://github.com/agentrhq/authsome/commit/d763f7f7dc8bb33b7049c27be78d0cdd08195ede))


### Bug Fixes

* expose actionable session details in login --json ([87ae0b7](https://github.com/agentrhq/authsome/commit/87ae0b7aeee76b69abae13d488e9e0829031d0c8))
* normalize cli error handling for json output ([fb2754b](https://github.com/agentrhq/authsome/commit/fb2754bded00bcdea76a7433736f59ae60f01cff))
* update daemon process command to include admin subcommand ([7855c77](https://github.com/agentrhq/authsome/commit/7855c77ceec670887c1cd4947e4202aaeff3a9b2))

## [0.4.1](https://github.com/agentrhq/authsome/compare/authsome-v0.4.0...authsome-v0.4.1) (2026-05-25)


### Features

* enable provider configuration management for hosted admins with required credential inputs and scope persistence ([e26d584](https://github.com/agentrhq/authsome/commit/e26d5841f34467af77e67903eaf6ee8b97d59313))
* enable provider configuration management for hosted admins with… ([30b2f8a](https://github.com/agentrhq/authsome/commit/30b2f8a3814a04b710fd37206889e3e1a71fd43f))


### Bug Fixes

* rename AUTHSOME_ADMIN_PRINCIPLES environment variable to fix typo ([10f17f4](https://github.com/agentrhq/authsome/commit/10f17f48e35f118e76d7cb5c797a498408c51db7))

## [0.4.0](https://github.com/agentrhq/authsome/compare/authsome-v0.3.2...authsome-v0.4.0) (2026-05-25)


### ⚠ BREAKING CHANGES

* Create version 0.4 which adds support for principal, identity, vault key loading precedence and many more fixes

### Features

* ClaimStatus lifecycle, vault_id gating, ADR 0003 alignment ([d8553ba](https://github.com/agentrhq/authsome/commit/d8553baabbfba595580fd0d6d0c0a90ba282e911))
* Cleanup server routes ([225d7fd](https://github.com/agentrhq/authsome/commit/225d7fdcfba184c60bffdb70ba28e9576109b25c))
* disable analytics automatically when running under pytest and add verification tests ([d1abc48](https://github.com/agentrhq/authsome/commit/d1abc48f11255419f5d58cc13d5280fa221a3b21))
* implement HostedAccountService for email/password authentication and JWT session management ([c161ab9](https://github.com/agentrhq/authsome/commit/c161ab96d0d78ad02ce98b5ad4c0269ba3fd0530))
* implement master key rotation via rekey command and API endpoint ([f78f872](https://github.com/agentrhq/authsome/commit/f78f872624b1da899d76dd0c1a04ee81fafca772))
* implement opt-out telemetry support via environment variables and add associated documentation and tests ([9d7c88f](https://github.com/agentrhq/authsome/commit/9d7c88fb0a1a777b535f5e06b11a60a00eda263c))
* implement opt-out telemetry support via environment variables and add associated tests ([1c1554c](https://github.com/agentrhq/authsome/commit/1c1554c9cf3fbf093d107d7c6a3fd15103572096))
* implement vault rekey functionality with encryption source validation and add corresponding API and unit tests. ([e7f4187](https://github.com/agentrhq/authsome/commit/e7f418707aacde9b7705a5f79c8a84b28878715d))
* login flow ([e0ea86d](https://github.com/agentrhq/authsome/commit/e0ea86dc99de0d1d616b3c609e48c2ba6a61d516))
* scope connections to vault, add claim flow and principal concept ([d3f2006](https://github.com/agentrhq/authsome/commit/d3f2006d67c572fef7dd05b539c7e2c83de8ddaa))


### Bug Fixes

* correct import path and test fixture for ready endpoint ([3951af8](https://github.com/agentrhq/authsome/commit/3951af82390994ad6d5acbdc06e59d91c8ccd962))
* deduplicate error class name in daemon responses and stop orphaned daemon ([76e2320](https://github.com/agentrhq/authsome/commit/76e2320c96e1e06eaa9d6822e98f33f8e027db1c))
* improve whoami robustness by handling connection failures gracefully and isolating keyring tests ([83709f4](https://github.com/agentrhq/authsome/commit/83709f4e373a3057b49af0e3b9e40b2166883d43))


### Documentation

* add dedicated Hermes Agent integration page, drop stale Hermes refs ([b7297dd](https://github.com/agentrhq/authsome/commit/b7297dd5e658bf20baf0251a21460f6c6b5b7048))
* add dedicated Hermes Agent integration page, drop stale Hermes refs ([e12082f](https://github.com/agentrhq/authsome/commit/e12082f0786504e5049550375ea97831657125e7))
* add hosted UI auth and identity claim design spec ([e552805](https://github.com/agentrhq/authsome/commit/e5528053c146e6a8652cd8fe44409d286d8a2d6a))
* fix CONTEXT.md dependency graph and direction ([17fff13](https://github.com/agentrhq/authsome/commit/17fff13aa893d049b65e16e1922f80130f388da2))
* make auth/ a leaf module, move AuthService to server/ ([d92611c](https://github.com/agentrhq/authsome/commit/d92611ccd4fc987595034b1e6b1ee49e1049af16))
* resolve merge conflicts in UBIQUITOUS_LANGUAGE.md ([48229eb](https://github.com/agentrhq/authsome/commit/48229eb8b456cbdaeeb7a7a1a2e0bf02800fb21e))
* rewrite CONTEXT.md with module boundaries, create TODOS.md ([c7a1629](https://github.com/agentrhq/authsome/commit/c7a1629166324729a9e14868ebaa9ad082165053))
* rewrite login and proxy sections in manual-testing guide ([3719d13](https://github.com/agentrhq/authsome/commit/3719d13a960430d2839df85b458d55ec83071006))
* update architecture language, retire Profile, add Principal/Vault/Claim terms ([8dc663e](https://github.com/agentrhq/authsome/commit/8dc663e21e505a5327a7168ea47a245ed94b8db7))


### Code Refactoring

* Create version 0.4 which adds support for principal, identity, vault key loading precedence and many more fixes ([bb5a2a6](https://github.com/agentrhq/authsome/commit/bb5a2a615291a89bfd5c1a581692b2d86a82dca4))

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
