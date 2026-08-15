"""Provisioning helpers for the K8s cyber range (kind + Helm).

Kept side-effect free unless explicitly invoked. All cluster mutations shell out
to ``kind``/``kubectl``/``helm`` and are guarded by :func:`tooling_available`,
so importing this module never touches a cluster.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

CHART_DIR = Path(__file__).parent / "chart"
KIND_CONFIG = Path(__file__).parent / "kind-cluster.yaml"


def tooling_available() -> tuple[bool, list[str]]:
    """Return (ok, missing_tools)."""
    missing = [t for t in ("kind", "kubectl", "helm") if shutil.which(t) is None]
    return (not missing, missing)


def _run(cmd: list[str], timeout: float = 300.0) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)


class KindProvisioner:
    def __init__(self, cluster_name: str = "coevsec", namespace: str = "range") -> None:
        self.cluster_name = cluster_name
        self.namespace = namespace

    def cluster_exists(self) -> bool:
        try:
            out = _run(["kind", "get", "clusters"])
        except Exception:
            return False
        return self.cluster_name in out.stdout.split()

    def create_cluster(self) -> None:
        if self.cluster_exists():
            return
        cmd = ["kind", "create", "cluster", "--name", self.cluster_name]
        if KIND_CONFIG.exists():
            cmd += ["--config", str(KIND_CONFIG)]
        _run(cmd)

    def deploy(self, hosts: int) -> None:
        """Deploy the range chart: gateway, `hosts` services, and the data store."""
        _run(["kubectl", "create", "namespace", self.namespace,
              "--dry-run=client", "-o", "yaml"])
        _run(["helm", "upgrade", "--install", "range", str(CHART_DIR),
              "--namespace", self.namespace, "--create-namespace",
              "--set", f"services={hosts}"])

    def isolate_host(self, host: str) -> None:
        """Apply a deny-all NetworkPolicy to a host (dynamic isolation)."""
        k8s_name = host.replace("_", "-")
        policy = _DENY_ALL_TEMPLATE.format(host=k8s_name, namespace=self.namespace)
        subprocess.run(["kubectl", "apply", "-f", "-"], input=policy, text=True,
                       capture_output=True, timeout=60)

    def teardown(self, delete_cluster: bool = False) -> None:
        if delete_cluster and self.cluster_exists():
            subprocess.run(["kind", "delete", "cluster", "--name", self.cluster_name],
                           capture_output=True, text=True, timeout=120)
        else:
            subprocess.run(["helm", "uninstall", "range", "--namespace", self.namespace],
                           capture_output=True, text=True, timeout=120)


_DENY_ALL_TEMPLATE = """\
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-{host}
  namespace: {namespace}
spec:
  podSelector:
    matchLabels:
      app: {host}
  policyTypes: [Ingress, Egress]
"""
