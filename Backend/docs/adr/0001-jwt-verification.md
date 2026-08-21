# 0001: Stateless JWT verification via a shared internal package

- Status: accepted
- Date: 2026-08-21

## Context

`AuthService` issues JWTs on login (`python-jose`, `HS256`, secret in
`JWT_SECRET`). Other services — `PlayerService`, `MatchmakingService`,
`GameSessionService`, `LeaderboardService` — need to authenticate
incoming requests carrying one of these tokens. Two options were
considered:

1. Each service calls `AuthService` (e.g. `POST /auth/verify`) on every
   authenticated request to check the token.
2. Each service verifies the JWT signature itself, using the same secret
   `AuthService` signs with — no network call.

## Decision

Verify locally (option 2). The verification dependency (decode the JWT,
validate signature/expiry, raise 401 on failure) lives in **one shared
internal package** that every service which needs authentication depends
on, rather than being copy-pasted per service or centralized behind a
runtime call to `AuthService`.

## Why

JWTs are self-contained and signed specifically so that verification
doesn't require a call back to the issuer. Routing verification through
`AuthService` at request time would:

- make `AuthService` a synchronous dependency for *every* request in
  *every* service, not just auth flows — an outage or slowdown in
  `AuthService` would cascade to the whole backend.
- add a network hop's worth of latency to every authenticated request,
  for no correctness benefit over checking the signature directly.

Copy-pasting the verification dependency into 4 services instead of
calling `AuthService` avoids the SPOF/latency problem, but risks drift
(e.g. one service missing an expiry check, or falling behind on a
`python-jose` security patch) since there's no single place to fix a bug.

## Consequences

- A shared internal package must exist (e.g.
  `Backend/shared/spacerace_auth/`) containing the `verify_token`
  dependency and JWT settings (algorithm, expected claims). Each service
  that authenticates callers installs it (e.g. via a path/local
  requirement) rather than reimplementing decoding.
- `AuthService` remains the only service that signs tokens or knows how
  to *mint* one; it has no special runtime role in *verifying* them for
  other services.
- Revocation (if ever needed — e.g. banning a user mid-session) can't be
  done by simply deleting server-side state, since verification never
  touches `AuthService`; it would need a separate mechanism (short token
  TTLs, or a deny-list each service checks). Not needed yet — flagged
  here so it isn't forgotten if that requirement shows up later.
