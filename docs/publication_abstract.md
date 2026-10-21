# Publication pitch (abstract draft)

**Title:** When Agent Security Tests Never Reach the Security Check:
Lessons from an Egress Gateway

**Abstract** (~215 words):

Tool-use agents can leak private data through outbound calls, yet
reported defense results often measure something other than
protection. We built a pre-dispatch egress gateway — host filtering,
bounded payload decoding, field-level authorization against
permission records, identity-bound task context — and evaluated it
with fictional data, mock receivers, and a local model. Two lessons
carry the article. First, *identify which check actually stopped the
action*: in our live model runs every blocked exfiltration was caught
by host or payload-coverage checks — the authorization layer decided
outcomes only in scripted and replayed calls, a distinction visible
only when each result is attributed to a deciding mechanism. Second,
*verify what reached the recipient*: an independent receiver-side
detector caught deliveries the gateway's own matcher missed,
including real model-generated exfiltration to an invented host and a
sibling-carrier coverage defect we reproduced and corrected.
Supporting examples: a small interface-development comparison (7
tasks) where a text-schema contract produced 4/7 valid calls versus
7/7 for an example-based contract — schema rejection had been
silently credited as protection; and a CaMeL policy-component
comparison agreeing on all 8 saved requests — compatibility, not
system equivalence; its local-model planner never produced a valid
program. Bounded laboratory experience report: the demonstration
illustrates mechanisms; it estimates no real-world prevention rate.
