"""
Monte Carlo risk simulator for a trading strategy.

Given a win rate, a reward:risk ratio and a risk budget per trade, it simulates
thousands of possible trade sequences and answers the questions that matter
before risking money:

  * What is the expectancy per trade?
  * How deep do drawdowns realistically get?
  * How long can a losing streak run?
  * Under evaluation-style rules (profit target, trailing drawdown, daily loss
    limit), what share of attempts pass, fail, or run out of trades?

Usage
-----
    python mc_risk.py --win-rate 0.45 --rr 1.5 --risk 250 \
        --start 50000 --target 3000 --trailing-dd 2000 --daily-loss 1000 \
        --trades 200 --trades-per-day 2 --sims 20000 --plot results.png

Run `python mc_risk.py --help` for every option.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np


@dataclass
class Config:
    win_rate: float          # probability a trade wins, 0 to 1
    rr: float                # reward:risk, e.g. 1.5 means win = 1.5x the risk
    risk: float              # risk per trade: dollars, or a fraction if fractional=True
    start: float = 50_000.0  # starting balance
    trades: int = 200        # max trades per simulated attempt
    sims: int = 10_000       # number of simulated attempts
    fractional: bool = False # risk a fixed fraction of equity instead of fixed dollars
    cost: float = 0.0        # round-trip cost per trade in dollars
    target: float | None = None       # profit target in dollars (pass condition)
    trailing_dd: float | None = None  # trailing drawdown limit from equity peak
    lock_at_start: bool = True        # trailing floor stops rising at the starting balance
    daily_loss: float | None = None   # max loss within one day
    trades_per_day: int = 1
    seed: int | None = 42


def expectancy_r(win_rate: float, rr: float) -> float:
    """Average result per trade in units of risk (R)."""
    return win_rate * rr - (1 - win_rate)


def breakeven_win_rate(rr: float) -> float:
    """Win rate at which the strategy neither makes nor loses money."""
    return 1 / (1 + rr)


def kelly_fraction(win_rate: float, rr: float) -> float:
    """Full Kelly fraction of equity to risk per trade (most traders use a fraction of it)."""
    return win_rate - (1 - win_rate) / rr


def simulate(cfg: Config) -> dict:
    rng = np.random.default_rng(cfg.seed)
    wins = rng.random((cfg.sims, cfg.trades)) < cfg.win_rate

    if cfg.fractional:
        # Equity compounds: each trade multiplies equity by (1 + r) or (1 - f)
        growth = np.where(wins, 1 + cfg.risk * cfg.rr, 1 - cfg.risk)
        equity_pre_cost = cfg.start * np.cumprod(growth, axis=1)
        equity = equity_pre_cost - cfg.cost * np.arange(1, cfg.trades + 1)
        pnl = np.diff(np.concatenate([np.full((cfg.sims, 1), cfg.start), equity], axis=1), axis=1)
    else:
        pnl = np.where(wins, cfg.risk * cfg.rr, -cfg.risk) - cfg.cost
        equity = cfg.start + np.cumsum(pnl, axis=1)

    # Peak includes the starting balance
    peak = np.maximum.accumulate(np.maximum(equity, cfg.start), axis=1)
    drawdown = peak - equity
    max_dd = drawdown.max(axis=1)

    never = cfg.trades  # sentinel index meaning "never happened"
    idx = np.arange(cfg.trades)

    def first_true(mask: np.ndarray) -> np.ndarray:
        return np.where(mask.any(axis=1), mask.argmax(axis=1), never)

    fail_at = np.full(cfg.sims, never)

    if cfg.trailing_dd is not None:
        floor = peak - cfg.trailing_dd
        if cfg.lock_at_start:
            floor = np.minimum(floor, cfg.start)
        fail_at = np.minimum(fail_at, first_true(equity <= floor))

    if cfg.daily_loss is not None:
        day = idx // cfg.trades_per_day
        # cumulative P&L within each day
        intraday = np.zeros_like(pnl)
        for d in np.unique(day):
            cols = day == d
            intraday[:, cols] = np.cumsum(pnl[:, cols], axis=1)
        fail_at = np.minimum(fail_at, first_true(intraday <= -cfg.daily_loss))

    pass_at = (
        first_true(equity - cfg.start >= cfg.target) if cfg.target is not None
        else np.full(cfg.sims, never)
    )

    passed = pass_at < fail_at
    failed = fail_at < pass_at
    unresolved = ~(passed | failed)

    # Longest losing streak per simulation
    losses = ~wins
    streak = np.zeros(cfg.sims, dtype=int)
    run = np.zeros(cfg.sims, dtype=int)
    for t in range(cfg.trades):
        run = np.where(losses[:, t], run + 1, 0)
        streak = np.maximum(streak, run)

    return {
        "cfg": cfg,
        "equity": equity,
        "max_dd": max_dd,
        "final": equity[:, -1],
        "streak": streak,
        "pass_rate": passed.mean(),
        "fail_rate": failed.mean(),
        "unresolved_rate": unresolved.mean(),
        "trades_to_pass": np.where(passed, pass_at + 1, np.nan),
        "has_rules": cfg.target is not None or cfg.trailing_dd is not None or cfg.daily_loss is not None,
    }


def summarize(res: dict) -> str:
    c: Config = res["cfg"]
    pct = lambda a, q: np.nanpercentile(a, q)
    lines = [
        "Strategy",
        f"  Win rate {c.win_rate:.0%}, reward:risk {c.rr:g}, "
        + (f"risk {c.risk:.2%} of equity" if c.fractional else f"risk ${c.risk:,.0f} per trade"),
        f"  Expectancy:          {expectancy_r(c.win_rate, c.rr):+.3f} R per trade (before costs)",
        f"  Break-even win rate: {breakeven_win_rate(c.rr):.1%}",
        f"  Full Kelly fraction: {kelly_fraction(c.win_rate, c.rr):.1%} of equity",
        "",
        f"Over {c.trades} trades, {c.sims:,} simulations",
        f"  Final P&L      median ${pct(res['final'] - c.start, 50):>10,.0f}   "
        f"5th pct ${pct(res['final'] - c.start, 5):>10,.0f}   95th pct ${pct(res['final'] - c.start, 95):>10,.0f}",
        f"  Max drawdown   median ${pct(res['max_dd'], 50):>10,.0f}   "
        f"95th pct ${pct(res['max_dd'], 95):>10,.0f}   99th pct ${pct(res['max_dd'], 99):>10,.0f}",
        f"  Losing streak  median {pct(res['streak'], 50):>4.0f}   95th pct {pct(res['streak'], 95):>4.0f}   "
        f"worst {res['streak'].max():>4.0f}",
    ]
    if res["has_rules"]:
        rules = []
        if c.target is not None:
            rules.append(f"target +${c.target:,.0f}")
        if c.trailing_dd is not None:
            rules.append(f"trailing DD ${c.trailing_dd:,.0f}")
        if c.daily_loss is not None:
            rules.append(f"daily loss ${c.daily_loss:,.0f} ({c.trades_per_day} trades/day)")
        lines += [
            "",
            "Evaluation rules: " + ", ".join(rules),
            f"  Pass {res['pass_rate']:.1%}   Fail {res['fail_rate']:.1%}   "
            f"Unresolved after {c.trades} trades {res['unresolved_rate']:.1%}",
        ]
        if res["pass_rate"] > 0:
            lines.append(f"  Median trades to pass: {np.nanmedian(res['trades_to_pass']):.0f}")
    return "\n".join(lines)


def plot(res: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["text.parse_math"] = False

    c: Config = res["cfg"]
    eq = res["equity"] - c.start
    x = np.arange(1, c.trades + 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5), gridspec_kw={"width_ratios": [1.6, 1]})

    for path_i in eq[:150]:
        ax1.plot(x, path_i, color="#9aa5b1", alpha=0.15, lw=0.7)
    for q, style in [(5, "--"), (50, "-"), (95, "--")]:
        ax1.plot(x, np.percentile(eq, q, axis=0), color="#1f4e79", ls=style, lw=1.8,
                 label=f"{q}th percentile")
    if c.target is not None:
        ax1.axhline(c.target, color="#2e7d32", lw=1, label="Profit target")
    if c.trailing_dd is not None:
        ax1.axhline(-c.trailing_dd, color="#c62828", lw=1, label="Initial drawdown floor")
    ax1.set(title="Simulated equity paths (no stop rules applied)", xlabel="Trade number", ylabel="P&L ($)")
    ax1.legend(fontsize=8, loc="upper left")
    ax1.grid(alpha=0.25)

    ax2.hist(res["max_dd"], bins=50, color="#1f4e79", alpha=0.85)
    p95 = np.percentile(res["max_dd"], 95)
    ax2.axvline(p95, color="#c62828", ls="--", lw=1.2, label=f"95th pct ${p95:,.0f}")
    ax2.set(title="Maximum drawdown distribution", xlabel="Max drawdown ($)", ylabel="Simulations")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)

    fig.suptitle(f"Win rate {c.win_rate:.0%} | R:R {c.rr:g} | "
                 + (f"risk {c.risk:.2%}" if c.fractional else f"risk ${c.risk:,.0f}")
                 + f" | {c.sims:,} sims", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description="Monte Carlo risk simulator for trading strategies.")
    p.add_argument("--win-rate", type=float, required=True, help="e.g. 0.45")
    p.add_argument("--rr", type=float, required=True, help="reward:risk, e.g. 1.5")
    p.add_argument("--risk", type=float, required=True,
                   help="dollars per trade, or fraction of equity with --fractional (e.g. 0.01)")
    p.add_argument("--fractional", action="store_true")
    p.add_argument("--start", type=float, default=50_000)
    p.add_argument("--trades", type=int, default=200)
    p.add_argument("--sims", type=int, default=10_000)
    p.add_argument("--cost", type=float, default=0.0, help="round-trip cost per trade ($)")
    p.add_argument("--target", type=float)
    p.add_argument("--trailing-dd", type=float)
    p.add_argument("--no-lock", action="store_true", help="let the trailing floor rise above start")
    p.add_argument("--daily-loss", type=float)
    p.add_argument("--trades-per-day", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--plot", help="save a chart to this PNG path")
    a = p.parse_args()

    cfg = Config(
        win_rate=a.win_rate, rr=a.rr, risk=a.risk, start=a.start, trades=a.trades,
        sims=a.sims, fractional=a.fractional, cost=a.cost, target=a.target,
        trailing_dd=a.trailing_dd, lock_at_start=not a.no_lock, daily_loss=a.daily_loss,
        trades_per_day=a.trades_per_day, seed=a.seed,
    )
    res = simulate(cfg)
    print(summarize(res))
    if a.plot:
        plot(res, a.plot)
        print(f"\nChart saved to {a.plot}")


if __name__ == "__main__":
    main()
