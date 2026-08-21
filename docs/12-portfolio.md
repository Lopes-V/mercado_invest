# Portfolio

Portfolio accounting is deterministic and provider-independent. Transactions use `Decimal`; BUY adds price and fees to cost basis, while SELL consumes the existing average cost and rejects oversell. A valuation accepts only a `VALID` market price. Cross-currency valuation requires an explicit `VALID` FX rate; it never assumes a 1:1 conversion. No tax, broker, or real-money operation exists here.
