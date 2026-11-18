# Quickstart: validating Data Quality and Forecast Intelligence

Synthetic fixtures only; never point this at a real Siweb host. Contracts: [contracts/quality-intelligence.md](contracts/quality-intelligence.md). Entities: [data-model.md](data-model.md).

## Prerequisites

- Local stack as in `specs/001-mmi-purchase-intelligence/quickstart.md` (PostgreSQL, inventory-service, forecast-service, api-bff, web).
- Synthetic catalogue from `packages/testing` containing: a smooth product, an intermittent product, a product with a stockout period, a product with an outlier day, a product with rejected movements, a product with seed data (feature 008) and one with too little history.
- Signed in as buyer; a second session as viewer.

## Validation scenarios

1. **Quality summary (US1)**: open the outlier product in the quality screen. Expect coverage with gap days, the anomaly flagged with its rule, the stockout days marked, rejected movements counted with Spanish reasons and a review link.
2. **Anomaly decision**: as buyer mark the anomaly `excluded`. Expect an audit event, a new series version and, after the next run, a new forecast; the original value is still shown. As viewer the same call returns 403.
3. **Explanation (US2)**: open the explanation of each fixture product. Expect model, dataset and configuration versions, class, method with reason, and eligibility; the too-little-history product is not eligible with a Spanish reason and has no forecast figure; its proposal line shows the conservative min/max quantity labelled "not a forecast".
4. **Reproducibility**: recompute the run with unchanged inputs. Expect identical results and explanations and no new run.
5. **Uncertainty and provenance (US3)**: expect low/expected/high and a confidence label on every eligible product; the seed product shows `estimated` values; no value outside ERP movements is labelled `observed` (automated check, SC-002).
6. **Backtest (US4)**: start a backtest for the catalogue. Expect a background job with status; per-product WAPE, bias and baseline comparison; a product where the baseline wins is flagged. Stored forecasts and proposals are unchanged (hash compare before and after).
7. **Portfolio (US5)**: open the portfolio. Expect counts by class and eligibility summing to the active product count; filter by category and supplier; each count opens its product list.
8. **Spanish UI**: all strings es-ES with Spanish number and date formats; Playwright run captures screenshots for the PR.

## Commands (indicative; exact test paths are fixed in tasks.md)

```bash
pytest services/inventory-service/tests services/forecast-service/tests services/api-bff/tests
(cd apps/web && npx playwright test --project=es-ES quality)
python -m gates run   # run from scripts/ before the PR
```

## Expected outcomes

Matches the Success Criteria in [spec.md](spec.md): SC-001 to SC-009, with automated tests passing on synthetic data and no change to stored forecasts, proposals, stock or ERP data from backtests.
