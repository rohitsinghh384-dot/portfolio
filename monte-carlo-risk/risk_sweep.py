"""
Risk sizing sweep: how does risk per trade change the odds of passing an
evaluation with a fixed profit target and trailing drawdown?

    python risk_sweep.py --win-rate 0.45 --rr 1.5 --target 3000 --trailing-dd 2000 \
        --risks 100 150 200 250 300 400 500 --plot examples/risk_sweep.png
"""

import argparse

import numpy as np

from mc_risk import Config, simulate


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--win-rate", type=float, required=True)
    p.add_argument("--rr", type=float, required=True)
    p.add_argument("--target", type=float, required=True)
    p.add_argument("--trailing-dd", type=float, required=True)
    p.add_argument("--risks", type=float, nargs="+", required=True)
    p.add_argument("--start", type=float, default=50_000)
    p.add_argument("--trades", type=int, default=300)
    p.add_argument("--sims", type=int, default=20_000)
    p.add_argument("--cost", type=float, default=0.0)
    p.add_argument("--plot")
    a = p.parse_args()

    rows = []
    print(f"{'Risk/trade':>11} {'Pass':>7} {'Fail':>7} {'Open':>7} {'Median trades':>14}")
    for r in a.risks:
        res = simulate(Config(win_rate=a.win_rate, rr=a.rr, risk=r, start=a.start,
                              trades=a.trades, sims=a.sims, cost=a.cost,
                              target=a.target, trailing_dd=a.trailing_dd))
        med = np.nanmedian(res["trades_to_pass"]) if res["pass_rate"] > 0 else float("nan")
        rows.append((r, res["pass_rate"], res["fail_rate"], res["unresolved_rate"], med))
        print(f"${r:>10,.0f} {res['pass_rate']:>7.1%} {res['fail_rate']:>7.1%} "
              f"{res['unresolved_rate']:>7.1%} {med:>14.0f}")

    if a.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["text.parse_math"] = False

        risks = [r[0] for r in rows]
        fig, ax1 = plt.subplots(figsize=(8, 4.5))
        ax1.plot(risks, [r[1] * 100 for r in rows], "o-", color="#1f4e79", lw=2, label="Pass rate")
        ax1.set(xlabel="Risk per trade ($)", ylabel="Pass rate (%)")
        ax1.grid(alpha=0.25)
        ax2 = ax1.twinx()
        ax2.plot(risks, [r[4] for r in rows], "s--", color="#c77700", lw=1.5, label="Median trades to pass")
        ax2.set_ylabel("Median trades to pass")
        lines = ax1.get_lines() + ax2.get_lines()
        ax1.legend(lines, [l.get_label() for l in lines], loc="upper right", fontsize=8)
        ax1.set_title(f"Pass rate vs risk size | win rate {a.win_rate:.0%}, R:R {a.rr:g}, "
                      f"target ${a.target:,.0f}, trailing DD ${a.trailing_dd:,.0f}", fontsize=10)
        fig.tight_layout()
        fig.savefig(a.plot, dpi=140)
        print(f"\nChart saved to {a.plot}")


if __name__ == "__main__":
    main()
