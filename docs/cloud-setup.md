# Cloud setup

Use the GitHub repository ojassgambira/MMDS in Codex Cloud. The Mac is only a UI
for reviewing changes and managing cloud access; it runs no project workloads.
The inspected cloud runtime has Python 3.12.14 and OpenJDK JRE 21.0.12.1.
Spark 4.0.1 supports Python 3.9+ and requires Java 17+:
https://spark.apache.org/docs/4.0.1/api/python/getting_started/install.html

Run the README commands inside the cloud checkout. Requirements are pinned in
requirements-dev.lock, including the development dependency closure. Use the
virtual environment to avoid altering the runtime's global Python packages.
CI uses Python 3.12, Temurin Java 21, and ubuntu-24.04 on GitHub-hosted runners.
`local[2]` is a two-worker smoke configuration inside the cloud, not execution
on the user's laptop and not evidence of multi-machine scalability.

Check the cloud runtime status and /etc/codex/network-policy.json before fetching
packages. The inspected policy is restricted; it lists package-manager and GitHub
hosts, has no VPN, and no configured secrets or outbound identities. Runtime
status reported policy state unknown, so actual requests must be verified.
Use inherited proxies and CA trust. Do not bypass blocked hosts. Initial sandbox
package requests failed; supported additional network permission was necessary.
No cloud resources should be provisioned for these checks.

Store datasets under /workspace/data and artifacts under /workspace/artifacts.
Do not place Kaggle tokens in configs or shell history. If acquisition needs
credentials or a destination absent from policy, request access through cloud
configuration. The Phase 1 adapter does not download anything.
