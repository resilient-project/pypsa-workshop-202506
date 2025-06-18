# Annex Config
custom configuration for the pan-EU system with 50 clusters and reduced temporal resolution

```yaml
run:
  name: "demo-sample-50"

scenario:
  clusters:
  - 50
  planning_horizons:
  - 2050

clustering:
  temporal:
    resolution_sector: 96h

costs:
  year: 2050

electricity:
  conventional_carriers: []
  renewable_carriers: [solar, onwind, offwind-ac, offwind-dc, hydro]
  powerplants_filter: Fueltype == 'Hydro'
  estimate_renewable_capacities:
    enable: false

lines:
  dynamic_line_rating:
    activate: false

sector:
  gas_network: true
  H2_retrofit: false
  regional_co2_sequestration_potential:
    enable: true
  co2_sequestration_potential: 250
  co2_spatial: true
  co2_network: true
  biomass_spatial: true
  biomass_transport: false
  biogas_upgrading_cc: true
  electrobiofuels: true
  regional_oil_demand: true

atlite:
  nprocesses: 16

solving:
  solver_options:
    gurobi-default:
      threads: 12
      BarConvTol: 5.e-5
```
