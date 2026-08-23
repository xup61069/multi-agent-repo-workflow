# Security policy

Please report vulnerabilities privately through GitHub's security advisory interface instead of a public issue.

The toolkit processes repository paths, Git output, local task files, and optional GitHub issue bodies. Reports should identify the affected script, the untrusted input, the resulting filesystem or command behavior, and a minimal reproduction.

The scripts must not execute commands sourced from configuration or issue bodies. A handoff's validation list is data for the assigned agent; `handoff_check.py` validates it but never executes it.
