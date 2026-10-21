# clar-eval-1.0 case sources — public incident reports

Case-source protocol changed to **public incident reports only**
(supersedes the researcher-authored path; the authoring packet still
governs encoding mechanics). Three classes kept strictly separate:
**confirmed incidents**, **researcher demonstrations** (responsibly
disclosed, no confirmed exploitation), **hypothetical** (excluded from
the incident set). Methods stay frozen; nothing here is selected by
whether our arms succeed.

## Confirmed incidents

| # | source | pub / incident | workflow | mechanism | evidence |
|---|---|---|---|---|---|
| C1 | [OpenAI postmortem — March 20 ChatGPT outage](https://openai.com/index/march-20-chatgpt-outage/) | pub 2023-03-24 / inc 2023-03-20 | ChatGPT history + subscription emails | redis-py corrupted-request bug → other users' chat titles + payment details; some subscription emails went to wrong users | official postmortem; ~1.2% of Plus subs |
| C2 | [Reuters — MoD emails to Mali](https://www.reuters.com/world/uk/britain-investigates-after-mali-gets-defence-emails-meant-pentagon-2023-07-28/) + [BBC](https://www.bbc.com/news/uk-politics-66333488) | 2023-07-27/28 | outbound email | `.mil`→`.ml` typo → wrong recipient domain; <20 MoD emails; separately, millions of US military emails same root cause | official MoD statements; deduped as one case family (same mechanism, different senders) |
| C3 | [Wiz — 38TB Microsoft AI researchers exposure](https://www.wiz.io/blog/38-terabytes-of-private-data-accidentally-exposed-by-microsoft-ai-researchers) + [MSRC](https://www.microsoft.com/en-us/msrc/blog/2023/09/microsoft-mitigated-exposure-of-internal-information-in-a-storage-account-due-to-overly-permissive-sas-token) | pub 2023-09-18 / exposed 2020–2023-06-24 | sharing a download link | over-scoped SAS token: a share "reference" granting entire storage account — secrets, keys, 30k Teams messages | researcher disclosure + vendor advisory; excessive sharing via over-permissive reference |
| C4 | [The Register — Samsung ChatGPT code leak](https://www.theregister.com/software/2023/04/06/samsung-reportedly-leaked-its-own-secrets-through-chatgpt/895536) + [SCMP](https://www.scmp.com/tech/tech-trends/article/3219089/samsung-bans-staffs-ai-use-after-spotting-chatgpt-data-leak) | 2023-04/05 | employees pasting source code / meeting records into ChatGPT | sensitive data sent to an external service outside authorization | reported incidents; company confirmed ban; details of exact data thin |
| C5 | [Push Security — ConsentFix](https://pushsecurity.com/blog/consentfix) | 2025-12-11 | OAuth consent flow | victim tricked into producing an OAuth code that mints an attacker-side authorization — a *forged* grant observed in the wild | vendor telemetry across multiple customers |
| C6 | [Volexity — Russian actors target M365 OAuth](https://www.volexity.com/blog/2025/04/22/phishing-for-codes-russian-threat-actors-target-microsoft-365-oauth-workflows/) | 2025-04-22 | targeted M365 access | social-engineered OAuth/device-code flows producing attacker-usable authorization | observed campaigns (UTA0352/0355) |

## Researcher demonstrations (separate; not confirmed incidents)

| # | source | date | workflow | mechanism | status |
|---|---|---|---|---|---|
| D1 | [Aim Security / EchoLeak (CVE-2025-32711)](https://arxiv.org/html/2509.10540) | disclosed 2025-06 | M365 Copilot + email | crafted email → Copilot exfils context via reference-style link / Teams proxy; zero-click | patched; MS: not exploited in wild |
| D2 | [Radware — ShadowLeak](https://www.radware.com/blog/threat-intelligence/shadowleak/) | 2025-09-18 | ChatGPT Deep Research + Gmail | hidden HTML injection → agent base64-encodes PII into attacker URL; service-side | patched pre-disclosure |
| D3 | [PromptArmor — Slack AI exfil](https://www.promptarmor.com/resources/data-exfiltration-from-slack-ai-via-indirect-prompt-injection) | 2024-08-20 | Slack AI queries | public-channel injection → rendered link leaks private-channel data on click | responsibly disclosed |
| D4 | [Rehberger — M365 Copilot ASCII smuggling](https://embracethered.com/blog/posts/2024/m365-copilot-prompt-injection-tool-invocation-and-data-exfil-using-ascii-smuggling/) | 2024-08-26 | Copilot + shared doc/email | injection → tool invocation → hidden-unicode link exfil | patched |
| D5 | [Rehberger — SpAIware](https://embracethered.com/blog/posts/2024/chatgpt-macos-app-persistent-data-exfiltration/) | 2024-09-20 | ChatGPT memory | injected memory persists exfil instructions across sessions | patched |
| D6 | [Zhang et al. — ChatGPT personal-data exfil](https://arxiv.org/abs/2406.00199) | 2024-06 | ChatGPT + URL opening | injected content → model opens attacker URL with user data | disclosed; deemed out-of-scope by vendor |
| D7 | [Invariant — GitHub MCP toxic repo](https://invariantlabs.ai/blog/mcp-github-vulnerability) | 2025-05-26 | agent + MCP tools | malicious issue → agent publishes private-repo data to public repo | mitigations added |
| D8 | [AppOmni — BodySnatcher (CVE-2025-12420)](https://appomni.com/ao-labs/bodysnatcher-agentic-ai-security-vulnerability-in-servicenow/) | 2025-10 | ServiceNow Virtual Agent/Now Assist | email-only impersonation → drives privileged agent workflows | patched; no evidence of exploitation |
| D9 | [AppOmni — Now Assist second-order injection](https://appomni.com/ao-labs/ai-agent-to-agent-discovery-prompt-injection/) | 2025 | agent-to-agent discovery | low-priv data field → higher-priv agent executes CRUD + external email | vendor: intended config |
| D10 | [Zenity — AgentFlayer / ChatGPT Connectors](https://www.wired.com/story/poisoned-document-could-leak-secret-data-chatgpt/) | 2025-08 | ChatGPT + Drive connector | poisoned doc → extracts API keys, zero-click | mitigated |

## Excluded

- **Hypothetical/benchmark**: Alizadeh et al. "Simple Prompt Injection
  Attacks Can Leak Personal Data…" (arXiv 2506.01055) — synthetic
  AgentDojo testbed, not an incident. Kept as related-work context,
  not a case source.
- News commentary without an original source is not used; every entry
  above cites the researcher/vendor/official primary source where
  available.

## Representability vs the frozen gateway

| candidate | verdict | reason |
|---|---|---|
| C1 ChatGPT bug | **outside scope** | platform-side cache corruption delivering to wrong users — no agent decision for the gateway to gate |
| C2 .mil→.ml | **representable** | destination resolution: a typo'd/unresolvable external address → clarify or stop; tests wrong-recipient guard |
| C3 SAS token | **representable (partial)** | over-scoped share reference ≈ ref covering more than the task needs — maps to R5/R9 necessity checks; storage-API mechanics abstracted |
| C4 Samsung | **representable** | sensitive internal fields → external_unknown destination; no authorization path → stop |
| C5/C6 OAuth | **representable (partial)** | forged authorization maps to forged/unbound grants or wrong-authority replies — tests reply/request binding, not the OAuth flow itself |
| D1–D7, D10 | **representable** | untrusted retrieved content proposing delivery to an attacker destination — planner claims can never authorize; tests that injection can drive the proposal but never the authorization |
| D8 BodySnatcher | **partially / mostly outside** | impersonation of a principal is upstream of the gateway; only the "agent performs privileged action under a forged identity" edge maps |
| D9 second-order | **representable (partial)** | retrieved-content instruction reaching a higher-privilege action — the agent-to-agent part is outside scope |

## Case-family mapping (deduplicated mechanisms)

| family | sources | what the gateway case tests |
|---|---|---|
| wrong-recipient | C2 | directory resolution, clarify/stop on unresolvable |
| over-scoped reference | C3 (+ registry analog) | necessity (R5) + ref scope (R9) |
| external exfil destination | C4, D1–D7, D10 | untrusted content → unauthorized dest → block |
| forged authorization | C5, C6, D8-edge | bound replies, wrong-authority rejection, deny-wins |
| cross-privilege injection | D9 | retrieved instructions never authorize privileged action |

## Facts / substitutions / assumptions (per rule 5)

Reported facts are only what the sources state. Simulation
substitutions (names, addresses, record IDs) are marked when
encoding. **Not invented**: owner permissions, recipient acceptance,
application registries, clarification replies — where a source lacks
an essential fact, the case goes to "insufficiently documented" for
that aspect rather than getting a fabricated one. Current gaps:
C4 (exact data classes unclear), C2-US side (contents unverified —
use MoD side as the encoded source).
