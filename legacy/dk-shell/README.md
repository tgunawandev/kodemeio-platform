# Legacy `dk` shell toolkit

The original Bash-based `kodemeio-dokploy` repository was renamed and archived
on 2026-08-25:

- Repository: https://github.com/tgunawandev/kodemeio-dokploy-legacy
- Final tag: `legacy-final-20260825`
- Final commit: `626bffc1a4b9926d1909b9ad401ca1668d9204ce`

The shell implementation is not copied into this repository. Its supported
operations are available through `kctl-dokploy` in
[kodemeio-skills](https://github.com/tgunawandev/kodemeio-skills).

Do not add new logic here. If a short transition is required, create a wrapper
that delegates directly to `kctl-dokploy` with an explicit profile.
