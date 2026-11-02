"""Shai-Hulud supply-chain worm detector (job-security-scan).

Modules: iocs (indicator data), inventory (packages on disk), findings (model, redaction,
output), heuristics (install-hook behaviour), scanner (repo mode), host (laptop mode).
Stdlib only; Python 3.8+. Nothing here executes the code it inspects or touches the network.
"""

MAX_SCAN_BYTES = 25 * 1024 * 1024
