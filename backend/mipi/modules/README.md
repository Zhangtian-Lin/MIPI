# Backend modules

V0 starts with `sources`, `documents`, `entities`, `events`, `projects`, `policies`, `evidence`, and `verification`. Each module will grow into `domain`, `application`, `infrastructure`, `api`, and `tests` only when real behavior is implemented.

Cross-module writes are forbidden. Use application services and domain events described in `docs/agents/Agent编排与交接协议.md`.

