# Usability check script (SC-002)

**Status: prepared, not run.** SC-002 asks for one buyer who does not know the app to finish two journeys in under 5 minutes each, without help. It is a reported result, not a build gate. Use synthetic data only (the mock API or the local environment with fixtures).

## Setup

- Role: buyer. Window 1280 px wide. Keyboard and mouse allowed.
- Observer notes time, wrong turns, questions asked and any word the person did not understand.

## Journey 1: product

1. Open the dashboard and find a product at risk of running out.
2. Open its detail and say what its code (SKU), stock and supplier are.
3. Open the related supplier or proposal and come back to the same product.

## Journey 2: supplier

1. Find a supplier from the suppliers screen.
2. Change its lead time to an invalid value (for example, letters), read the message, correct it and save.
3. Leave the screen with an unsaved change and say what the prompt asks.
4. Import a terms file that has one bad row and say which row was rejected and why.

## Record

| Journey | Time | Finished without help | Problems | Words not understood |
|---|---|---|---|---|
| Product | | | | |
| Supplier | | | | |
