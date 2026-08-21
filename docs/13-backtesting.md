# Backtesting

The backtest core is walk-forward. A signal at timestamp T receives only candles ending at T. The forward reference price is read only after the signal has been created. The output is an observation summary, not a claim of trading profit. Paper execution, separately, uses the next available candle open and never the signal candle.
