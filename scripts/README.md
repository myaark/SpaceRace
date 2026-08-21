# scripts/

Plain shell scripts for common repo-wide tasks. No task-runner dependency
(`make`, etc.) is assumed. Each script has a `.sh` (bash / Git Bash) version;
add a `.ps1` twin only if you actually run it from native PowerShell.

- `dev.sh` — bring up infra + app services via docker-compose for local dev
- `down.sh` — tear down the docker-compose stack

Service-specific scripts (frontend build, backend tests, etc.) belong in
each service's own folder once those conventions are defined, not here.
