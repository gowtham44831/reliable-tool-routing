"""Minimal reproduction: released CaMeL base_security_policy denies
even fully-public kwargs.

Upstream commit f083b6b, vendored verbatim at
src/third_party/camel_policy/ (Apache-2.0, unmodified semantics).

Observation only — separate from comparative conclusions. Reported
because `base_security_policy` compares the (readers, visited)
tuple returned by get_all_readers against Public() rather than the
readers component, so the released function returns Denied for any
kwarg. Unpatched; no upstream change made or requested.

Run: .venv/bin/python scripts/repro_base_policy_denies_public.py
"""

from third_party.camel_policy import security_policy
from third_party.camel_policy.capabilities import (
    Capabilities, readers, sources)
from third_party.camel_policy.interpreter.value import CaMeLStr

pub = CaMeLStr.from_raw(
    "hello", Capabilities(frozenset({sources.SourceEnum.User}),
                          readers.Public()), ())
priv = CaMeLStr.from_raw(
    "secret", Capabilities(frozenset({sources.SourceEnum.User}),
                           frozenset({"owner.svc"})), ())

for name, v in [("public", pub), ("private", priv)]:
    r = security_policy.base_security_policy(
        "url_fetch", {"arg": v}, set())
    print(f"{name}: {type(r).__name__} "
          f"{getattr(r, 'reason', '')}")
