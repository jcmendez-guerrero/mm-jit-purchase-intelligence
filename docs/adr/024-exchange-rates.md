# ADR-024: Exchange rates for suppliers that quote in another currency

- Status: accepted (owner, 2026-11-08)
- Date: 2026-11-09
- Deciders: owner
- Feature: specs/007-supplier-commercial-management (MMI-6)

## Context and problem statement

A supplier can quote in a currency other than EUR, and the ERP can send such costs. Until now nothing converted them: the proposal engine read the cost number as euros. A dollar cost of 1.10 was compared with a euro cost of 1.00 as if it were 1.10 EUR. Wrongly mixed currencies are worse than a missing supplier, and the earlier rule ("costs in that currency are not mixed with EUR without an explicit conversion", feature 004) had no conversion behind it.

The platform needs a reference rate it can trust enough for comparison and allocation, without a manual upkeep burden, new secrets, or an always-on component (shared budget EUR 120/month).

## Decision drivers

- No credentials or secrets, and nothing sent to the outside (public repository, constitution Principle I and II).
- No new always-on service; scale to zero (ADR-006 budget).
- Reproducible proposals: the rate behind a proposal must be known and stored.
- An outage of the rate service must never stop supplier maintenance or proposals.
- An official reference rather than a blend, in case a figure is ever questioned.

## Considered options

1. **Frankfurter, ECB provider, cached locally** (chosen).
2. A manual rate per supplier, kept by the buyer.
3. Refuse non-EUR suppliers.
4. Frankfurter's default blended feed.
5. A self-hosted Frankfurter instance.

## Decision outcome

Option 1. The owner chose Frankfurter <https://frankfurter.dev>.

- **One request, one host.** The procurement worker (already a scale-to-zero cron job) issues `GET https://api.frankfurter.dev/v2/providers/ecb/rates?base=EUR` at most about once a day: only when the newest stored rate was confirmed more than 20 hours ago, and not within an hour of a failure. Host, path, query and method are fixed in code and refused otherwise before a request is built; no redirect is followed; no credentials, cookies or body are sent; the answer is limited to 200 KB and must be JSON. Tests prove the refusals.
- **Official rate.** The ECB provider is pinned (the service itself recommends a single provider for official reference rates). The ECB publishes about 30 currencies; any other currency has no rate.
- **Stored, never fetched during a proposal.** Each rate is stored as exact decimals with its publication date and fetch time. Proposal generation and the screens read the database only.
- **Usable for 7 days.** A rate published more than 7 days before the proposal date is stale. That covers weekends and the TARGET closing days. A missing, unsupported or stale rate leaves the supplier out of automatic allocation and creates one review item per supplier, problem and currency; nothing is converted silently or dropped silently.
- **Visible.** The proposal line states the original cost, the rate and its day; the product list shows the euro equivalent and why there is none.
- **As is.** The service provides the data without warranty and says blended rates are not official. Converted amounts serve comparison and allocation, not accounting or tax.
- **Housekeeping.** The same pass purges rates older than 400 days.
- **Switch.** `MMI_FX_DISABLED=1` makes the worker skip the call, for runs that must stay offline.

Verified on 2026-11-09 with one public, read-only request (nothing sent): the answer is a JSON list of `{date, base, quote, rate}` with 30 quotes; the newest date on a Monday morning was the previous Friday, so no weekend rates exist. Behaviour on holidays is not yet observed.

### Consequences

- Good: no manual upkeep, no secrets, no new resource, one tiny request a day (about 2 KB), proposals stay reproducible, and an outage only ages the stored rate.
- Bad / residual risk: a new outbound dependency on a third-party host; no network-level egress rule exists (an FQDN rule needs Azure Firewall, outside the budget, as already noted for the cost writer), so the application allowlist is the control. The service states no numeric rate limit.
- Rejected: manual rates (error-prone upkeep); refusing non-EUR suppliers (blocks real suppliers); the blended feed (not an official rate); self-hosting (an always-on component, against the cost rule).

## Follow-up

- Observe a TARGET holiday and record whether the newest date simply stays on the last working day.
- If the service ever publishes quotas, or changes the v2 answer shape, the refusal tests fail closed and this record is revisited.
- Agent 00 confirms the daily call as an acceptable shared change (task T003).
