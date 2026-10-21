# Can the released CaMeL policy interface express M3's intent?

Assessment of `SecurityPolicy`/`SecurityPolicyEngine` at upstream
commit `f083b6b`. Conclusion: **the interface can express it as a
custom policy; the released policy SET cannot.** Two arms, clearly
separated.

## The interface

`SecurityPolicy = (tool_name, kwargs: Mapping[str, CaMeLValue])
-> Allowed | Denied`. Policies are arbitrary Python; the engine
glob-matches tool names and consults `dependencies` for the
default-deny/private-dependency checks. Readers metadata on each
CaMeLValue is the authorization substrate.

## Expressing M3's recipient/field authorization

M3 intent: field `f` may reach destination `d` under purpose `p`
iff a covering allow record exists and no covering deny record
does. Mapping to released concepts:

| M3 concept | CaMeL mapping |
|---|---|
| permitted destination per field | `readers` set on the field's CaMeLValue = {destination_principals authorized by records} |
| purpose scoping | our adapter computes readers FOR the bound purpose (per-task closure); CaMeL readers have no purpose axis — purpose is handled by *how readers were assigned*, out-of-band |
| deny-wins | deny record removes d from readers — removal is computed by us, not by their engine |
| field-level granularity | per-arg readers on each extracted value |

A custom `SecurityPolicy` — call it `camel-m3-intent` — for
`url_fetch`: parse the URL's `d=` carrier, extract field values,
and require `destination ∈ readers(value)` for every matched
protected field. **This uses the released interface and released
reader mechanics; the reader ASSIGNMENT comes from our permission
records, not CaMeL's provenance propagation.**

## The released policy set (descriptive-only arm)

`base_security_policy` denies any non-public data reaching a
state-changing tool — under it, authorized sharing is impossible.
It is ONE released policy, not CaMeL's only supported policy; the
suite policies (`send_email_policy` etc.) express readers⊆recipients
but are hardwired to AgentDojo tool schemas. Treating the
base-policy arm as "CaMeL" would mischaracterize it — it is the
released base-policy component, descriptive only.

## Frozen policy configuration (specified, not yet run)

```
policy name:        camel-m3-intent (custom SecurityPolicy,
                    released interface)
tool pattern:       url_fetch
rule:               for each matched protected field value v in
                    decoded carrier: require dest_principal ∈
                    readers(v); else Denied
readers(v):         {dest : ∃ allow(owner(f) covers f, dest, p_task)}
                    minus {dest : ∃ deny covers (f, dest, p_task)}
p_task:             application-bound task purpose (adapter input)
capability source:  OUR adapter — recorded as supplied metadata
unmatched payload:  Denied (conservative, mirrors F5)
```

Status: **executed** — vendored component in
`src/third_party/camel_policy/`; arms in
`src/tool_routing/argverify/camel_policy_arm.py` (camel-arms-1.0);
comparison run once on saved eval-v4 requests
(`results/camel_component_eval/`).

## Trusted-record → capability mapping (as implemented)

| our concept | mapping to capabilities |
|---|---|
| `data_owner` + `permitted_fields` | allow record applies to field `f` iff `field_metadata[f].owner == data_owner` |
| `destination_principal` | candidate member of `readers_set` on the field's CaMeLValue |
| `purpose` | readers computed for the bound task purpose only; mismatched purpose → record skipped → empty readers |
| `constraints.not_after` | expired records excluded from readers |
| `effect: allow` | adds destination to `readers_set` |
| `effect: deny` | removes destination (deny-wins, before policy evaluation) |
| missing/ambiguous metadata | field absent from records → `readers_set = ∅` → any destination check fails |
| unlabeled/unaccounted carrier content | policy-level Denied (mirrors F5) |
| non-protected values | `readers.Public()` |

Sources: `SourceEnum.User` marks values whose content came from
retrieved data the user owns; the `_unaccounted_carrier` marker
uses `SourceEnum.CaMeL`. Computed from trusted records only —
never from M3 decisions, expected labels, or evaluator truth.
No case required marking non-comparable.
