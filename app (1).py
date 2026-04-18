import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import linprog
import requests
from datetime import datetime
 
# ================================================================
# PAGE CONFIG
# ================================================================
st.set_page_config(
    page_title="Smart Energy Router",
    page_icon="⚡",
    layout="wide"
)
 
st.title("⚡ Smart Energy Routing System")
st.markdown("Optimise renewable energy distribution across your buildings using live solar data and linear programming.")
 
# ================================================================
# HELPER FUNCTIONS
# ================================================================
def get_full_day_forecast(latitude, longitude, solar_area, panel_efficiency):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ["shortwave_radiation"],
        "timezone": "Europe/London",
        "forecast_days": 1
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        hourly_radiation = data["hourly"]["shortwave_radiation"]
        hourly_kwh = [r * solar_area * panel_efficiency / 1000 for r in hourly_radiation]
        return {
            "Morning": sum(hourly_kwh[6:12]),
            "Midday":  sum(hourly_kwh[12:17]),
            "Evening": sum(hourly_kwh[17:22]),
            "Night":   sum(hourly_kwh[22:]) + sum(hourly_kwh[0:6])
        }
    except Exception as e:
        st.warning(f"Could not fetch forecast: {e}. Using default values.")
        return None
 
 
def get_time_period():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 17:
        return "Midday"
    elif 17 <= hour < 22:
        return "Evening"
    else:
        return "Night"
 
 
def run_linear_programming_optimisation(buildings, time_periods, time_column_map, battery_capacity, battery_efficiency):
    time_order = list(time_periods.keys())
    n_times = len(time_order)
 
    building_data = []
    for t_idx, time in enumerate(time_order):
        demand_col, ci_col = time_column_map[time]
        for b_idx, (_, row) in enumerate(buildings.iterrows()):
            building_data.append({
                "time_idx": t_idx,
                "time": time,
                "building_idx": b_idx,
                "Building Name": row["Building Name"],
                "Type of building": row["Type of building"],
                "demand": row[demand_col],
                "ci": row[ci_col]
            })
 
    building_df = pd.DataFrame(building_data)
    n_buildings = len(buildings)
 
    def alloc_idx(t, b):
        return t * n_buildings + b
 
    def charge_idx(t):
        return n_times * n_buildings + t
 
    def discharge_idx(t):
        return n_times * n_buildings + n_times + t
 
    n_vars = n_times * n_buildings + n_times + n_times
 
    c = np.zeros(n_vars)
    for _, row in building_df.iterrows():
        t = row["time_idx"]
        b = row["building_idx"]
        c[alloc_idx(t, b)] = -row["ci"]
 
    bounds = [(0, None)] * n_vars
    for _, row in building_df.iterrows():
        t = row["time_idx"]
        b = row["building_idx"]
        bounds[alloc_idx(t, b)] = (0, row["demand"])
    for t in range(n_times):
        bounds[charge_idx(t)] = (0, battery_capacity)
        bounds[discharge_idx(t)] = (0, battery_capacity)
 
    A_ub = []
    b_ub = []
 
    for t_idx, time in enumerate(time_order):
        row_constraint = np.zeros(n_vars)
        for b in range(n_buildings):
            row_constraint[alloc_idx(t_idx, b)] = 1
        row_constraint[charge_idx(t_idx)] = 1
        row_constraint[discharge_idx(t_idx)] = -1
        A_ub.append(row_constraint)
        b_ub.append(time_periods[time])
 
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[charge_idx(t2)] = 1
            row_constraint[discharge_idx(t2)] = -1
        A_ub.append(row_constraint)
        b_ub.append(battery_capacity)
 
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[discharge_idx(t2)] = 1
            row_constraint[charge_idx(t2)] = -battery_efficiency
        A_ub.append(row_constraint)
        b_ub.append(0)
 
    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
 
    if not result.success:
        st.error(f"Optimisation failed: {result.message}")
        return None, None
 
    all_results = []
    for t_idx, time in enumerate(time_order):
        demand_col, ci_col = time_column_map[time]
        temp_buildings = buildings.copy()
        temp_buildings["Adjusted Demand"] = temp_buildings[demand_col]
        temp_buildings["CI"] = temp_buildings[ci_col]
 
        renewable_allocated = []
        fossil_fuel_used = []
        emissions_prevented = []
        emission_potentials = []
 
        for b_idx, (_, row) in enumerate(temp_buildings.iterrows()):
            allocated = result.x[alloc_idx(t_idx, b_idx)]
            allocated = max(0, min(allocated, row["Adjusted Demand"]))
            fossil = row["Adjusted Demand"] - allocated
            prevented = allocated * row["CI"]
            potential = row["Adjusted Demand"] * row["CI"]
            renewable_allocated.append(round(allocated, 2))
            fossil_fuel_used.append(round(fossil, 2))
            emissions_prevented.append(round(prevented, 2))
            emission_potentials.append(round(potential, 2))
 
        temp_buildings["renewable_kwh"] = renewable_allocated
        temp_buildings["fossil_kwh"] = fossil_fuel_used
        temp_buildings["emissions_prevented"] = emissions_prevented
        temp_buildings["emission_potential"] = emission_potentials
        temp_buildings["Time Period"] = time
        temp_buildings["Mode"] = "Normal"
        all_results.append(temp_buildings)
 
    battery_log = []
    battery_level = 0
    for t_idx, time in enumerate(time_order):
        charge = result.x[charge_idx(t_idx)]
        discharge = result.x[discharge_idx(t_idx)]
        battery_level += charge - discharge
        battery_log.append({
            "Time Period": time,
            "Battery Charged": round(charge, 2),
            "Battery Discharged": round(discharge, 2),
            "Battery Level After": round(battery_level, 2)
        })
 
    return pd.concat(all_results).reset_index(drop=True), pd.DataFrame(battery_log)
 
 
def run_lp_failure_mode(buildings, time_periods, failure_time_column_map, battery_capacity, battery_efficiency):
    time_order = list(time_periods.keys())
    n_times = len(time_order)
    n_buildings = len(buildings)
 
    def alloc_idx(t, b):
        return t * n_buildings + b
 
    def charge_idx(t):
        return n_times * n_buildings + t
 
    def discharge_idx(t):
        return n_times * n_buildings + n_times + t
 
    n_vars = n_times * n_buildings + n_times + n_times
 
    time_building_data = {}
    for t_idx, time in enumerate(time_order):
        demand_col, ci_col, mer_col, priority_col = failure_time_column_map[time]
        rows = []
        for b_idx, (_, row) in enumerate(buildings.iterrows()):
            rows.append({
                "b_idx": b_idx,
                "demand": float(row[demand_col]),
                "mer": float(row[mer_col]),
                "priority": float(row[priority_col]),
                "ci": float(row["CI_Equivalent"])
            })
        time_building_data[t_idx] = rows
 
    # Stage 1 - MER allocation
    c_stage1 = np.zeros(n_vars)
    for t_idx in range(n_times):
        for bdata in time_building_data[t_idx]:
            b = bdata["b_idx"]
            c_stage1[alloc_idx(t_idx, b)] = -bdata["priority"]
 
    bounds_stage1 = [(0, None)] * n_vars
    for t_idx in range(n_times):
        for bdata in time_building_data[t_idx]:
            b = bdata["b_idx"]
            bounds_stage1[alloc_idx(t_idx, b)] = (0, bdata["mer"])
        bounds_stage1[charge_idx(t_idx)] = (0, battery_capacity)
        bounds_stage1[discharge_idx(t_idx)] = (0, battery_capacity)
 
    A_ub_stage1 = []
    b_ub_stage1 = []
 
    for t_idx, time in enumerate(time_order):
        row_constraint = np.zeros(n_vars)
        for b in range(n_buildings):
            row_constraint[alloc_idx(t_idx, b)] = 1
        row_constraint[charge_idx(t_idx)] = 1
        row_constraint[discharge_idx(t_idx)] = -1
        A_ub_stage1.append(row_constraint)
        b_ub_stage1.append(time_periods[time])
 
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[charge_idx(t2)] = 1
            row_constraint[discharge_idx(t2)] = -1
        A_ub_stage1.append(row_constraint)
        b_ub_stage1.append(battery_capacity)
 
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[discharge_idx(t2)] = 1
            row_constraint[charge_idx(t2)] = -battery_efficiency
        A_ub_stage1.append(row_constraint)
        b_ub_stage1.append(0)
 
    for t_idx in range(n_times):
        bdata_list = time_building_data[t_idx]
        for high_bdata in bdata_list:
            for low_bdata in bdata_list:
                if low_bdata["priority"] < high_bdata["priority"]:
                    if high_bdata["mer"] > 0:
                        row_constraint = np.zeros(n_vars)
                        row_constraint[alloc_idx(t_idx, low_bdata["b_idx"])] = high_bdata["mer"]
                        row_constraint[alloc_idx(t_idx, high_bdata["b_idx"])] = -low_bdata["mer"] if low_bdata["mer"] > 0 else -1
                        A_ub_stage1.append(row_constraint)
                        b_ub_stage1.append(0)
 
    result_stage1 = linprog(c_stage1, A_ub=A_ub_stage1, b_ub=b_ub_stage1, bounds=bounds_stage1, method="highs")
 
    if not result_stage1.success:
        st.error(f"Stage 1 failed: {result_stage1.message}")
        return None, None
 
    stage1_allocations = {}
    stage1_battery_charge = 0
    remaining_renewable = {}
 
    for t_idx, time in enumerate(time_order):
        total_allocated = sum(result_stage1.x[alloc_idx(t_idx, b)] for b in range(n_buildings))
        charge = result_stage1.x[charge_idx(t_idx)]
        discharge = result_stage1.x[discharge_idx(t_idx)]
        stage1_battery_charge += charge - discharge
        remaining_renewable[t_idx] = max(time_periods[time] - total_allocated - charge + discharge, 0)
        for bdata in time_building_data[t_idx]:
            b = bdata["b_idx"]
            stage1_allocations[(t_idx, b)] = result_stage1.x[alloc_idx(t_idx, b)]
 
    # Stage 2 - above MER allocation
    c_stage2 = np.zeros(n_vars)
    for t_idx in range(n_times):
        for bdata in time_building_data[t_idx]:
            b = bdata["b_idx"]
            c_stage2[alloc_idx(t_idx, b)] = -bdata["priority"]
 
    bounds_stage2 = [(0, None)] * n_vars
    for t_idx in range(n_times):
        for bdata in time_building_data[t_idx]:
            b = bdata["b_idx"]
            above_mer = max(bdata["demand"] - stage1_allocations.get((t_idx, b), 0), 0)
            bounds_stage2[alloc_idx(t_idx, b)] = (0, above_mer)
        bounds_stage2[charge_idx(t_idx)] = (0, battery_capacity)
        bounds_stage2[discharge_idx(t_idx)] = (0, battery_capacity)
 
    A_ub_stage2 = []
    b_ub_stage2 = []
 
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for b in range(n_buildings):
            row_constraint[alloc_idx(t_idx, b)] = 1
        row_constraint[charge_idx(t_idx)] = 1
        row_constraint[discharge_idx(t_idx)] = -1
        A_ub_stage2.append(row_constraint)
        b_ub_stage2.append(remaining_renewable[t_idx])
 
    battery_start = stage1_battery_charge
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[charge_idx(t2)] = 1
            row_constraint[discharge_idx(t2)] = -1
        A_ub_stage2.append(row_constraint)
        b_ub_stage2.append(battery_capacity - battery_start)
 
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[discharge_idx(t2)] = 1
            row_constraint[charge_idx(t2)] = -battery_efficiency
        A_ub_stage2.append(row_constraint)
        b_ub_stage2.append(battery_start)
 
    result_stage2 = linprog(c_stage2, A_ub=A_ub_stage2, b_ub=b_ub_stage2, bounds=bounds_stage2, method="highs")
 
    if not result_stage2.success:
        st.error(f"Stage 2 failed: {result_stage2.message}")
        return None, None
 
    all_results = []
    for t_idx, time in enumerate(time_order):
        demand_col, ci_col, mer_col, priority_col = failure_time_column_map[time]
        temp_buildings = buildings.copy()
        temp_buildings["Adjusted Demand"] = temp_buildings[demand_col]
        temp_buildings["MER"] = temp_buildings[mer_col]
        temp_buildings["Priority"] = temp_buildings[priority_col]
        temp_buildings["CI"] = temp_buildings["CI_Equivalent"]
 
        renewable_allocated = []
        shortfall = []
        mer_met = []
 
        for b_idx, (_, row) in enumerate(temp_buildings.iterrows()):
            stage1 = max(0, result_stage1.x[alloc_idx(t_idx, b_idx)])
            stage2 = max(0, result_stage2.x[alloc_idx(t_idx, b_idx)])
            total = min(stage1 + stage2, row["Adjusted Demand"])
            below_mer = max(row["MER"] - total, 0)
            mer_fully_met = total >= row["MER"]
            renewable_allocated.append(round(total, 2))
            shortfall.append(round(below_mer, 2))
            mer_met.append(mer_fully_met)
 
        temp_buildings["failure_renewable_kwh"] = renewable_allocated
        temp_buildings["MER Shortfall"] = shortfall
        temp_buildings["MER Met"] = mer_met
        temp_buildings["Time Period"] = time
        temp_buildings["Mode"] = "Failure"
        all_results.append(temp_buildings)
 
    battery_log = []
    battery_level = 0
    for t_idx, time in enumerate(time_order):
        charge = result_stage1.x[charge_idx(t_idx)] + result_stage2.x[charge_idx(t_idx)]
        discharge = result_stage1.x[discharge_idx(t_idx)] + result_stage2.x[discharge_idx(t_idx)]
        battery_level += charge - discharge
        battery_log.append({
            "Time Period": time,
            "Battery Charged": round(charge, 2),
            "Battery Discharged": round(discharge, 2),
            "Battery Level After": round(battery_level, 2)
        })
 
    return pd.concat(all_results).reset_index(drop=True), pd.DataFrame(battery_log)
 
 
def plot_device_comparison(results, mode="Normal"):
    if mode == "Normal":
        renewable_col = "renewable_kwh"
        fossil_col = "fossil_kwh"
        labels = ["Renewable", "Fossil Fuel"]
        stacked = True
    else:
        renewable_col = "failure_renewable_kwh"
        fossil_col = "MER Shortfall"
        labels = ["Renewable Allocated", "MER Shortfall"]
        stacked = False
 
    building_types = results["Type of building"].unique()
    cols = 3
    rows = -(-len(building_types) // cols)
 
    fig, axes = plt.subplots(rows, cols, figsize=(18, rows * 4))
    axes = axes.flatten()
 
    for i, building_type in enumerate(building_types):
        building_data = results[
            results["Type of building"] == building_type
        ].groupby("Time Period")[[renewable_col, fossil_col]].sum()
        building_data = building_data.reindex(["Morning", "Midday", "Evening", "Night"])
 
        building_data.plot(
            kind="bar", stacked=stacked, ax=axes[i],
            color=["#2ecc71", "#e74c3c"], edgecolor="white"
        )
        axes[i].set_title(building_type)
        axes[i].set_ylabel("Energy (kWh)")
        axes[i].tick_params(axis='x', rotation=30)
        axes[i].legend(labels)
 
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)
 
    plt.suptitle(
        f"{mode} Mode — Renewable vs Fossil Fuel by Device",
        fontsize=14, fontweight="bold", y=1.02
    )
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()
 
 
# ================================================================
# STEP 1 — DEVICE SETUP
# ================================================================
st.header("Step 1 — Enter Your Devices")
st.markdown("Enter each device or building type you want to include, one per line.")
 
device_names_input = st.text_area(
    "Devices / building types:",
    placeholder="House\nHospital\nWarehouse\nSchool",
    height=150
)
 
device_names = [d.strip() for d in device_names_input.split("\n") if d.strip()]
 
device_data = []
 
if device_names:
    for device in device_names:
        st.subheader(f"⚙️ {device}")
 
        col1, col2, col3 = st.columns(3)
 
        with col1:
            count = st.number_input(
                f"Number of '{device}':",
                min_value=1, step=1, value=1,
                key=f"count_{device}"
            )
 
        with col2:
            efficiency = st.slider(
                f"Efficiency of '{device}':",
                min_value=0.1, max_value=1.0, value=0.5, step=0.05,
                key=f"efficiency_{device}"
            )
 
        with col3:
            priority = st.slider(
                f"Priority of '{device}' (failure mode):",
                min_value=0.1, max_value=1.0, value=0.5, step=0.05,
                key=f"priority_{device}"
            )
 
        st.markdown("**Energy demand (kWh):**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            demand_morning = st.number_input("Morning:", min_value=0.0, value=0.0, key=f"dm_{device}")
        with col2:
            demand_midday = st.number_input("Midday:", min_value=0.0, value=0.0, key=f"dd_{device}")
        with col3:
            demand_evening = st.number_input("Evening:", min_value=0.0, value=0.0, key=f"de_{device}")
        with col4:
            demand_night = st.number_input("Night:", min_value=0.0, value=0.0, key=f"dn_{device}")
 
        st.markdown("**Minimum energy requirement — MER (kWh):**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            mer_morning = st.number_input("Morning MER:", min_value=0.0, max_value=float(demand_morning) if demand_morning > 0 else 0.0, value=0.0, key=f"mm_{device}")
        with col2:
            mer_midday = st.number_input("Midday MER:", min_value=0.0, max_value=float(demand_midday) if demand_midday > 0 else 0.0, value=0.0, key=f"md_{device}")
        with col3:
            mer_evening = st.number_input("Evening MER:", min_value=0.0, max_value=float(demand_evening) if demand_evening > 0 else 0.0, value=0.0, key=f"me_{device}")
        with col4:
            mer_night = st.number_input("Night MER:", min_value=0.0, max_value=float(demand_night) if demand_night > 0 else 0.0, value=0.0, key=f"mn_{device}")
 
        st.divider()
 
        device_data.append({
            "Type of building": device,
            "Number of buildings": count,
            "Efficiency": efficiency,
            "Priority": priority,
            "Demand (morning)": demand_morning,
            "Demand (midday)":  demand_midday,
            "Demand (evening)": demand_evening,
            "Demand (night)":   demand_night,
            "Minimum Energy Requirement (morning)": mer_morning,
            "Minimum Energy Requirement (midday)":  mer_midday,
            "Minimum Energy Requirement (evening)": mer_evening,
            "Minimum Energy Requirement (night)":   mer_night,
        })
 
# ================================================================
# STEP 2 — SOLAR SETUP
# ================================================================
st.header("Step 2 — Solar Panel Setup")
 
col1, col2 = st.columns(2)
with col1:
    solar_area = st.number_input(
        "Total solar panel area (m²):",
        min_value=1.0, value=1000.0, step=100.0
    )
with col2:
    panel_efficiency = st.slider(
        "Solar panel efficiency:",
        min_value=0.05, max_value=0.5, value=0.20, step=0.01,
        format="%.2f"
    )
 
# ================================================================
# STEP 3 — LOCATION
# ================================================================
st.header("Step 3 — Your Location")
st.markdown("Find your coordinates at [maps.google.com](https://maps.google.com) by right clicking your location.")
 
col1, col2 = st.columns(2)
with col1:
    latitude = st.number_input(
        "Latitude (e.g. 51.5074 for London):",
        value=51.5074, format="%.4f"
    )
with col2:
    longitude = st.number_input(
        "Longitude (e.g. -0.1278 for London):",
        value=-0.1278, format="%.4f"
    )
 
# ================================================================
# STEP 4 — BATTERY SETUP
# ================================================================
st.header("Step 4 — Battery Settings")
 
col1, col2 = st.columns(2)
with col1:
    battery_capacity = st.number_input(
        "Battery capacity (kWh):",
        min_value=1.0, value=500000.0, step=1000.0
    )
with col2:
    battery_efficiency = st.slider(
        "Battery efficiency:",
        min_value=0.1, max_value=1.0, value=0.9, step=0.01,
        format="%.2f"
    )
 
# ================================================================
# STEP 5 — MODE SELECTION
# ================================================================
st.header("Step 5 — Choose Mode")
 
mode_choice = st.radio(
    "Which mode would you like to run?",
    options=["Normal", "Failure", "Both"],
    format_func=lambda x: {
        "Normal": "🌱 Normal mode — optimises for minimum carbon emissions (buildings can use fossil fuels)",
        "Failure": "🚨 Failure mode — no fossil fuels, every building must meet its minimum energy requirement",
        "Both":   "⚡ Both modes — run normal then failure mode"
    }[x]
)
 
# ================================================================
# STEP 6 — RUN
# ================================================================
st.header("Step 6 — Run Optimisation")
 
if st.button("🚀 Run Optimisation", type="primary"):
 
    # Validate inputs
    if not device_names:
        st.error("Please enter at least one device in Step 1!")
        st.stop()
 
    if not device_data:
        st.error("Please fill in device details in Step 1!")
        st.stop()
 
    with st.spinner("Setting up buildings..."):
 
        # Build DataFrame
        buildings_raw = pd.DataFrame(device_data)
        buildings_raw["CI_Equivalent"] = 1 / buildings_raw["Efficiency"]
        for period in ["morning", "midday", "evening", "night"]:
            buildings_raw[f"Priority ({period})"] = buildings_raw["Priority"]
 
        # Expand into individual buildings
        buildings = buildings_raw.loc[
            buildings_raw.index.repeat(buildings_raw["Number of buildings"])
        ].reset_index(drop=True)
        buildings["Building ID"] = buildings.groupby("Type of building").cumcount() + 1
        buildings["Building Name"] = buildings["Type of building"] + " #" + buildings["Building ID"].astype(str)
 
        st.success(f"✓ {len(buildings)} individual buildings set up!")
 
    with st.spinner("Fetching live solar forecast..."):
 
        # Fetch full day forecast
        forecast = get_full_day_forecast(latitude, longitude, solar_area, panel_efficiency)
 
        if forecast is not None:
            time_periods = forecast
            st.success("✓ Live solar forecast fetched!")
        else:
            time_periods = {
                "Morning": solar_area * panel_efficiency * 300,
                "Midday":  solar_area * panel_efficiency * 600,
                "Evening": solar_area * panel_efficiency * 200,
                "Night":   solar_area * panel_efficiency * 10
            }
            st.warning("Using estimated values instead.")
 
        # Show forecast
        forecast_df = pd.DataFrame([
            {"Time Period": k, "Renewable Available (kWh)": round(v, 2)}
            for k, v in time_periods.items()
        ])
        st.dataframe(forecast_df, hide_index=True)
 
    # Column maps
    time_column_map = {
        "Morning": ("Demand (morning)", "CI_Equivalent"),
        "Midday":  ("Demand (midday)",  "CI_Equivalent"),
        "Evening": ("Demand (evening)", "CI_Equivalent"),
        "Night":   ("Demand (night)",   "CI_Equivalent")
    }
 
    failure_time_column_map = {
        "Morning": ("Demand (morning)", "CI_Equivalent", "Minimum Energy Requirement (morning)", "Priority (morning)"),
        "Midday":  ("Demand (midday)",  "CI_Equivalent", "Minimum Energy Requirement (midday)",  "Priority (midday)"),
        "Evening": ("Demand (evening)", "CI_Equivalent", "Minimum Energy Requirement (evening)", "Priority (evening)"),
        "Night":   ("Demand (night)",   "CI_Equivalent", "Minimum Energy Requirement (night)",   "Priority (night)")
    }
 
    # Demand overview chart
    st.subheader("📊 Energy Demand Overview")
    demand_summary = buildings_raw.copy()
    for col in ["Demand (morning)", "Demand (midday)", "Demand (evening)", "Demand (night)"]:
        demand_summary[col] = demand_summary[col] * demand_summary["Number of buildings"]
    demand_summary = demand_summary.set_index("Type of building")[
        ["Demand (morning)", "Demand (midday)", "Demand (evening)", "Demand (night)"]
    ]
    demand_summary.columns = ["Morning", "Midday", "Evening", "Night"]
 
    fig, ax = plt.subplots(figsize=(12, 4))
    demand_summary.T.plot(kind="bar", ax=ax, edgecolor="white")
    ax.set_title("Total Energy Demand by Device and Time Period")
    ax.set_ylabel("Energy (kWh)")
    ax.set_xlabel("Time Period")
    ax.tick_params(axis='x', rotation=0)
    ax.legend(title="Device", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()
 
    # ================================================================
    # NORMAL MODE
    # ================================================================
    if mode_choice in ["Normal", "Both"]:
        st.header("🌱 Normal Mode Results")
 
        with st.spinner("Running normal mode LP optimisation..."):
            normal_results, normal_battery_log = run_linear_programming_optimisation(
                buildings, time_periods, time_column_map,
                battery_capacity, battery_efficiency
            )
 
        if normal_results is not None:
            normal_summary = normal_results.groupby("Time Period")[
                ["renewable_kwh", "fossil_kwh", "emissions_prevented", "emission_potential"]
            ].sum().reindex(["Morning", "Midday", "Evening", "Night"])
 
            st.success(f"✓ Normal mode complete! Total emissions prevented: {normal_summary['emissions_prevented'].sum():,.2f} gCO2")
 
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Renewable Used", f"{normal_summary['renewable_kwh'].sum():,.0f} kWh")
            with col2:
                st.metric("Total Fossil Fuel Used", f"{normal_summary['fossil_kwh'].sum():,.0f} kWh")
            with col3:
                st.metric("Total Emissions Prevented", f"{normal_summary['emissions_prevented'].sum():,.0f} gCO2")
 
            # Summary charts
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            normal_summary[["renewable_kwh", "fossil_kwh"]].plot(
                kind="bar", stacked=True, ax=axes[0],
                color=["#2ecc71", "#e74c3c"], edgecolor="white"
            )
            axes[0].set_title("Energy Source by Time Period")
            axes[0].set_ylabel("Energy (kWh)")
            axes[0].tick_params(axis='x', rotation=0)
            axes[0].legend(["Renewable", "Fossil Fuel"])
 
            normal_summary[["emissions_prevented", "emission_potential"]].plot(
                kind="bar", stacked=False, ax=axes[1],
                color=["#3498db", "#ff7518"], edgecolor="white"
            )
            axes[1].set_title("Emissions Prevented vs Potential")
            axes[1].set_ylabel("gCO2")
            axes[1].tick_params(axis='x', rotation=0)
            axes[1].legend(["Prevented", "Potential"])
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
 
            # Battery log
            st.subheader("🔋 Battery Activity")
            st.dataframe(normal_battery_log, hide_index=True)
 
            fig, ax = plt.subplots(figsize=(10, 4))
            normal_battery_log.set_index("Time Period")[
                ["Battery Charged", "Battery Discharged", "Battery Level After"]
            ].plot(kind="bar", ax=ax, color=["#2ecc71", "#e74c3c", "#f39c12"], edgecolor="white")
            ax.set_title("Battery Activity by Time Period")
            ax.set_ylabel("Energy (kWh)")
            ax.tick_params(axis='x', rotation=0)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
 
            # Per device comparison
            st.subheader("📊 Renewable vs Fossil Fuel by Device")
            plot_device_comparison(normal_results, mode="Normal")
 
            # Full results table
            with st.expander("View full results table"):
                st.dataframe(
                    normal_results[[
                        "Building Name", "Type of building", "Time Period",
                        "Adjusted Demand", "renewable_kwh", "fossil_kwh",
                        "emissions_prevented", "emission_potential"
                    ]],
                    hide_index=True
                )
 
    # ================================================================
    # FAILURE MODE
    # ================================================================
    if mode_choice in ["Failure", "Both"]:
        st.header("🚨 Failure Mode Results")
 
        with st.spinner("Running failure mode LP optimisation..."):
            failure_results, failure_battery_log = run_lp_failure_mode(
                buildings, time_periods, failure_time_column_map,
                battery_capacity, battery_efficiency
            )
 
        if failure_results is not None:
            total_buildings = len(buildings)
            total_mer_met = failure_results.groupby("Time Period")["MER Met"].sum()
            total_shortfall = failure_results.groupby("Time Period")["MER Shortfall"].sum()
 
            st.success(f"✓ Failure mode complete!")
 
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Buildings Meeting MER (Morning)",
                    f"{int(total_mer_met.get('Morning', 0))} / {total_buildings}"
                )
            with col2:
                st.metric(
                    "Buildings Meeting MER (Evening)",
                    f"{int(total_mer_met.get('Evening', 0))} / {total_buildings}"
                )
            with col3:
                st.metric(
                    "Total MER Shortfall",
                    f"{failure_results['MER Shortfall'].sum():,.0f} kWh"
                )
 
            # Summary charts
            failure_summary = failure_results.groupby("Time Period")[
                ["failure_renewable_kwh", "MER Shortfall"]
            ].sum().reindex(["Morning", "Midday", "Evening", "Night"])
 
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            failure_summary.plot(
                kind="bar", stacked=True, ax=axes[0],
                color=["#2ecc71", "#e74c3c"], edgecolor="white"
            )
            axes[0].set_title("Energy Allocated vs MER Shortfall by Time Period")
            axes[0].set_ylabel("Energy (kWh)")
            axes[0].tick_params(axis='x', rotation=0)
            axes[0].legend(["Renewable Allocated", "MER Shortfall"])
 
            mer_pct = (total_mer_met / total_buildings * 100).reindex(
                ["Morning", "Midday", "Evening", "Night"]
            )
            mer_pct.plot(kind="bar", ax=axes[1], color="#3498db", edgecolor="white")
            axes[1].set_title("% Buildings Meeting MER by Time Period")
            axes[1].set_ylabel("% Buildings")
            axes[1].set_ylim(0, 110)
            axes[1].axhline(y=100, color="red", linestyle="--", label="100% target")
            axes[1].tick_params(axis='x', rotation=0)
            axes[1].legend()
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
 
            # Battery log
            st.subheader("🔋 Battery Activity")
            st.dataframe(failure_battery_log, hide_index=True)
 
            fig, ax = plt.subplots(figsize=(10, 4))
            failure_battery_log.set_index("Time Period")[
                ["Battery Charged", "Battery Discharged", "Battery Level After"]
            ].plot(kind="bar", ax=ax, color=["#2ecc71", "#e74c3c", "#f39c12"], edgecolor="white")
            ax.set_title("Battery Activity by Time Period")
            ax.set_ylabel("Energy (kWh)")
            ax.tick_params(axis='x', rotation=0)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
 
            # Per device comparison
            st.subheader("📊 Renewable vs MER Shortfall by Device")
            plot_device_comparison(failure_results, mode="Failure")
 
            # Full results table
            with st.expander("View full results table"):
                st.dataframe(
                    failure_results[[
                        "Building Name", "Type of building", "Time Period",
                        "Adjusted Demand", "MER", "failure_renewable_kwh",
                        "MER Shortfall", "MER Met", "Priority"
                    ]],
                    hide_index=True
                )
