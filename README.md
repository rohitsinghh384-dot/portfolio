# Trishnoorpreet Singh

Business student at Ritsumeikan Asia Pacific University (Japan) with a computer science background. I build data tools around markets and real estate, mostly to find where something is mispriced against a baseline I can defend.

## Projects

| Project | What it is | Stack |
|---|---|---|
| [REI Platform](rei-platform/) | Finds mispriced land near credible infrastructure projects in Indian cities. Public showcase with a synthetic-data scoring demo | Python, pandas, PostGIS, Playwright |
| [Monte Carlo Risk Simulator](monte-carlo-risk/) | Stress-tests trading strategies: drawdown and losing-streak distributions, and pass rates under prop-firm rules across position sizes | Python, NumPy, Matplotlib |

### Also built (code private)

- **Automated trading strategies (MQL5).** 7+ Expert Advisors for MetaTrader 5 covering mean reversion, trend following and market-profile breakouts, each with hard-coded risk limits. One was demo-tested by 15 traders and bought by 2, so the source stays private.
- **Market alert bots (Python).** Telegram bots that track indices, FX and gold across timeframes, with retry and fallback logic for unreliable data feeds.
- **NGO patient and donor database.** Took an NGO in Punjab from paper records and WhatsApp threads to a structured database, now holding 2,000+ patient and 500+ donor records.

## Run the projects

```bash
pip install -r requirements.txt

# Monte Carlo simulator
cd monte-carlo-risk
python mc_risk.py --win-rate 0.45 --rr 1.5 --risk 250 --target 3000 --trailing-dd 2000

# REI demo notebook
cd ../rei-platform
jupyter notebook scoring_demo.ipynb
```

## Contact

trishnoor22@gmail.com | Beppu, Japan
