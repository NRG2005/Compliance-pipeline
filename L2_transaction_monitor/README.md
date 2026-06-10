# L2: Transaction Monitor

This layer uses six Azure Functions running in parallel to perform deterministic checks on the transaction data.

## Category 1: Velocity & Structuring (T1)
- **T1**: Detects sub-threshold splitting over time windows. Uses windowed-aggregation engine parameterised by rail and threshold for structuring detection.

## Category 2: Sanctions & Watchlist (T2)
- **T2**: Standalone deterministic ID cross-reference against FIU-IND watchlists using fuzzy matching (rapidfuzz).

## Category 3: Graph Network Flow (T5)
- **T5**: Directed-graph traversals over Cosmos transaction edges. Depth-1 fan-in/fan-out analysis with shared graph-building primitive for depth-≤3 round-trip traversals.

## Category 4: Account Risk & Dormancy (T3)
- **T3**: Account-level scoring based on age, KYC level, and activity history. Owns dormancy detection signal.

## Category 5: Cross-Border / FEMA-LRS (T6)
- **T6**: Standalone check for PAN-level YTD outward-remittance aggregation against FEMA-LRS ceiling enforcement.

## Category 6: Geo-Anomaly (T4)
- **T4**: Transaction location vs the account's historical geographic pattern. Uses moving average of account geographic state.

A weighted scoring formula combines the outputs of these checks into a single suspicion score.
