# -*- coding: utf-8 -*-
"""
Interactive Example: Stochastic Network Optimization with PyPSA

Three model implementations:
    1. Deterministic optimization over gas-price scenarios
    2. Stochastic optimization via PyPSA API
    3. Manual stochastic model construction with linopy

This example works with this PyPSA branch: https://github.com/PyPSA/PyPSA/tree/new-opt-stoch
"""

# Step 1: Imports and Configuration
import matplotlib.pyplot as plt
import pandas as pd
from xarray import DataArray
import pypsa


# Plot helpers
def plot_capacity(
    df,
    title="Capacity Mix",
    xlabel="Scenario",
    ylabel="Capacity (MW)",
    figsize=(6, 3),
    color_map=None,
    rotation=0,
):
    """
    Plot capacity mix as stacked bar chart
    """
    if color_map is None:
        color_map = COLOR_MAP

    colors = [color_map.get(c, "gray") for c in df.columns]
    ax = df.plot(kind="bar", stacked=True, figsize=figsize, color=colors)
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    plt.xticks(rotation=rotation, ha="right" if rotation > 0 else "center")
    plt.tight_layout()
    return ax


def plot_cost(
    series,
    title="Total Cost",
    xlabel="Scenario",
    ylabel="EUR",
    figsize=(4, 3),
    rotation=0,
):
    """
    Plot costs as bar chart
    """
    ax = series.plot(kind="bar", figsize=figsize)
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    plt.xticks(rotation=rotation, ha="right" if rotation > 0 else "center")
    plt.tight_layout()
    return ax


# Scenario definitions
SCENARIOS = ["low", "med", "high"]
GAS_PRICES = {"low": 40, "med": 70, "high": 100}
PROB = {"low": 0.4, "med": 0.3, "high": 0.3}
BASE = "low"
FREQ = "3h"
LOAD_MW = 1
SOLVER = "highs"
TS_URL = (
    "https://tubcloud.tu-berlin.de/s/pKttFadrbTKSJKF/download/time-series-lecture-2.csv"
)


# Technology specs
def annuity(life, rate):
    """Compute capital recovery factor."""
    return rate / (1 - (1 + rate) ** -life) if rate else 1 / life


TECH = {
    "solar": {"profile": "solar", "inv": 1e6, "m_cost": 0.01},
    "wind": {"profile": "onwind", "inv": 2e6, "m_cost": 0.02},
    "gas": {"inv": 7e5, "eff": 0.6},
    "lignite": {"inv": 1.3e6, "eff": 0.4, "m_cost": 130},
}
FOM, DR, LIFE = 3.0, 0.03, 25
for cfg in TECH.values():
    cfg["fixed_cost"] = (annuity(LIFE, DR) + FOM / 100) * cfg["inv"]

COLOR_MAP = {
    "solar": "yellow",
    "wind": "skyblue",
    "gas": "brown",
    "lignite": "black",
}

# Step 2: Load Time Series
ts = pd.read_csv(TS_URL, index_col=0, parse_dates=True)
ts = ts.resample(FREQ).asfreq()


###########################################
# Step 3: Build toy network & run deterministic scenarios
def build_network(gas_price):
    """
    Create PyPSA network:
      - DE bus and constant load
      - extendable generators for solar, wind, gas, lignite
    """
    n = pypsa.Network()
    n.set_snapshots(ts.index)
    n.snapshot_weightings = pd.Series(int(FREQ[:-1]), index=ts.index)
    n.add("Bus", "DE")
    n.add("Load", "DE_load", bus="DE", p_set=LOAD_MW)

    for tech in ["solar", "wind"]:
        cfg = TECH[tech]
        n.add(
            "Generator",
            tech,
            bus="DE",
            p_nom_extendable=True,
            p_max_pu=ts[cfg["profile"]],
            capital_cost=cfg["fixed_cost"],
            marginal_cost=cfg["m_cost"],
        )
    for tech in ["gas", "lignite"]:
        cfg = TECH[tech]
        mc = (gas_price / cfg.get("eff")) if tech == "gas" else cfg["m_cost"]
        n.add(
            "Generator",
            tech,
            bus="DE",
            p_nom_extendable=True,
            efficiency=cfg.get("eff"),
            capital_cost=cfg["fixed_cost"],
            marginal_cost=mc,
        )
    return n


caps_det = pd.DataFrame(index=SCENARIOS, columns=TECH.keys())
objs_det = pd.Series(index=SCENARIOS)

for sc in SCENARIOS:
    n = build_network(GAS_PRICES[sc])
    n.optimize(solver_name=SOLVER)
    caps_det.loc[sc] = n.generators.p_nom_opt
    objs_det.loc[sc] = n.objective


"""
Linopy LP model
===============

Variables:
----------
 * Generator-p_nom (Generator-ext)
 * Generator-p (snapshot, Generator)

Constraints:
------------
 * Generator-ext-p_nom-lower (Generator-ext)
 * Generator-ext-p_nom-upper (Generator-ext)
 * Generator-ext-p-lower (snapshot, Generator-ext)
 * Generator-ext-p-upper (snapshot, Generator-ext)
 * Bus-nodal_balance (Bus, snapshot)

"""

# Step 4: Plot Deterministic Results
plot_capacity(caps_det, title="Deterministic Capacity Mix")
plt.show()

plot_cost(objs_det, title="Deterministic Total Cost")
plt.show()


###########################################
# Step 5: Build stochastic network with PyPSA API

n_stoch = build_network(GAS_PRICES[BASE])

# Adding scenarios & probabilities to the network are super easy
n_stoch.set_scenarios(PROB)

"""
Unnamed Stochastic PyPSA Network
--------------------------------
Components:
 - Bus: 3
 - Generator: 12
 - Load: 3
Snapshots: 2920
Scenarios: 3
"""

# n_stoch
# n_stoch.scenarios
# n_stoch.generators
# n_stoch.generators_t.p_max_pu
# n_stoch.generators.loc[:, "marginal_cost"]
# n_stoch.optimize.create_model()
# n_stoch.model.constraints['Generator-ext-p-lower']

# Set data that is varying by scenario
for sc in SCENARIOS:
    if sc != BASE:
        idx = (sc, "gas")
        n_stoch.generators.loc[idx, "marginal_cost"] = (
            GAS_PRICES[sc] / n_stoch.generators.loc[idx, "efficiency"]
        )

n_stoch.optimize(solver_name=SOLVER)
caps_api = n_stoch.generators.p_nom_opt.xs("med", level="scenario")
obj_api = n_stoch.objective


"""
Linopy LP model
===============

Variables:
----------
 * Generator-p_nom (component)
 * Generator-p (scenario, component, snapshot)

Constraints:
------------
 * Generator-ext-p_nom-lower (component, scenario)
 * Generator-ext-p-lower (scenario, component, snapshot)
 * Generator-ext-p-upper (scenario, component, snapshot)
 * Bus-nodal_balance (component, scenario, snapshot)

"""

# Step 6: Plot API Stochastic Results
caps_all = caps_det.copy()
caps_all.loc["Stochastic API"] = caps_api
plot_capacity(caps_all, title="Capacity Mix: Deterministic + Stochastic")
plt.show()

objs_all = objs_det.copy()
objs_all.loc["Stochastic API"] = obj_api
plot_cost(objs_all, title="Total Cost: Deterministic + Stochastic")
plt.show()


###########################################
# Step 7: Let's manually formulate stochastic problem to reproduce the results

from pypsa.components.common import as_components
from linopy.expressions import merge


def add_stochastic(n):
    """
    Adds scenarios to default pypsa optimization problem:
      - declare dispatch vars additional scenarios
      - add capacity and nodal balance constraints per scenario
      - append objective terms and weight by scenario probabilities
    """
    m = n.optimize.create_model()
    sns = n.snapshots
    c = as_components(n, "Generator")
    cap = m["Generator-p_nom"]
    min_pu, max_pu = c.get_bounds_pu(sns, None, "p")

    for sc in ["med", "high"]:
        # operational constraints
        var = f"Generator-p-{sc}"
        disp = m.add_variables(coords=m["Generator-p"].coords, name=var)
        m.add_constraints(disp <= max_pu * cap, name=f"Generator-ext-p-upper-{sc}")
        m.add_constraints(disp >= min_pu * cap, name=f"Generator-ext-p-lower-{sc}")

        # nodal balance constraints
        buses = n.generators.bus.to_xarray().rename("Bus")
        lhs = (DataArray(1) * disp).groupby(buses).sum()
        load = n.components["Load"].as_xarray("p_set", sns)
        rhs = load.swap_dims({"component": "Bus"})
        m.add_constraints(lhs == rhs, name=f"Bus-nodal-{sc}")

    w = n.snapshot_weightings.objective.loc[sns]
    w_da = DataArray(w.values, coords={"snapshot": sns}, dims=["snapshot"])
    obj = []
    for sc in SCENARIOS:
        disp = m["Generator-p"] if sc == BASE else m[f"Generator-p-{sc}"]
        cm = n.components["Generator"].as_xarray("marginal_cost", sns)
        cm.loc[{"component": "gas"}] = GAS_PRICES[sc] / TECH["gas"]["eff"]
        cm = cm * w_da
        obj.append((disp * PROB[sc] * cm).sum())
    cap_cost = c.as_xarray("capital_cost")
    obj.append((cap * cap_cost).sum())
    m.objective = merge(obj)


n_manual_stoch = build_network(GAS_PRICES["low"])
add_stochastic(n_manual_stoch)

n_manual_stoch.optimize.solve_model(solver_name=SOLVER)

caps_manual_stoch = n_manual_stoch.generators.p_nom_opt
obj_manual_stoch = n_manual_stoch.objective
print("Manual Stochastic Capacities (MW):", caps_manual_stoch)
print("Manual Stochastic Objective:", obj_manual_stoch)

"""
Linopy LP model
===============

Variables:
----------
 * Generator-p_nom (component)
 * Generator-p (snapshot, component)
 * Generator-p-med (snapshot, component)
 * Generator-p-high (snapshot, component)

Constraints:
------------
 * Generator-ext-p_nom-lower (component)
 * Generator-ext-p-lower (snapshot, component)
 * Generator-ext-p-upper (snapshot, component)
 * Bus-nodal_balance (component, snapshot)
 * Generator-ext-p-upper-med (snapshot, component)
 * Generator-ext-p-lower-med (snapshot, component)
 * Bus-nodal-med (Bus, component, snapshot)
 * Generator-ext-p-upper-high (snapshot, component)
 * Generator-ext-p-lower-high (snapshot, component)
 * Bus-nodal-high (Bus, component, snapshot)
"""


# Step 8: Plot Final Comparison Results
caps_final_comparison = caps_det.copy()
caps_final_comparison.loc["Stochastic API"] = caps_api
caps_final_comparison.loc["Stochastic Manual"] = caps_manual_stoch

objs_final_comparison = objs_det.copy()
objs_final_comparison.loc["Stochastic API"] = obj_api
objs_final_comparison.loc["Stochastic Manual"] = obj_manual_stoch

plot_capacity(
    caps_final_comparison,
    title="Capacity Mix: Deterministic vs. Stochastic Approaches",
    xlabel="Scenario / Optimization Type",
    figsize=(10, 5),
    rotation=45,
)
plt.show()

plot_cost(
    objs_final_comparison,
    title="Objective Value: Deterministic vs. Stochastic Approaches",
    xlabel="Scenario / Optimization Type",
    ylabel="Total Cost (EUR)",
    figsize=(8, 5),
    rotation=45,
)
plt.show()
