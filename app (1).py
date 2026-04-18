import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import linprog
import requests
from datetime import datetime
import time
import streamlit as st
print("All libraries installed successfully!")
def get_device_data():
    """
    Asks the user to input their devices and energy requirements.
    Returns a buildings DataFrame, solar area and panel efficiency.
    """
    print("=" * 60)
    print("ENERGY ROUTING SYSTEM — BUILDING SETUP")
    print("=" * 60)
    print("\nThis system will help you set up your energy routing model.")
    print("You will be asked about each device or building type")
    print("and its energy requirements throughout the day.\n")

    # Get list of devices
    print("Step 1 — What devices or buildings use energy?")
    print("Enter each one on a separate line.")
    print("When you have finished, type 'done' and press Enter.\n")

    device_names = []
    while True:
        device_names = st.text_area(
            "Enter your devices or buildings, one per line:",
            placeholder="House\nHospital\nWarehouse"
        )
        device_names = [d.strip() for d in device_names.split("\n") if d.strip()]
        if device.lower() == "done":
            if len(device_names) == 0:
                print("Please enter at least one device!")
                continue
            break
        if device:
            device_names.append(device)
            print(f"  ✓ Added: {device}")

    print(f"\nYou have entered {len(device_names)} devices: {', '.join(device_names)}")

    # Get details for each device
    device_data = []
    for device in device_names:
        print(f"\n{'=' * 60}")
        print(f"Setting up: {device.upper()}")
        print("=" * 60)

        # Number of this device
        while True:
            try:
                count = st.number_input(
                    f"How many '{device}' are there?",
                    min_value=1, step=1, value=1,
                    key=f"count_{device}"
                )
                if count > 0:
                    break
                print("Please enter a number greater than 0!")
            except ValueError:
                print("Please enter a whole number!")

        # Efficiency
        print(f"\nEfficiency of '{device}':")
        print("  1.0 = perfectly efficient (no energy wasted)")
        print("  0.5 = 50% efficient (half energy wasted)")
        print("  0.3 = 30% efficient (very inefficient)")
        while True:
            try:
                efficiency = st.slider(
                    f"Efficiency of '{device}':",
                    min_value=0.1, max_value=1.0, value=0.5, step=0.05,
                    key=f"efficiency_{device}"
                )
                if 0.1 <= efficiency <= 1.0:
                    break
                print("Please enter a value between 0.1 and 1.0!")
            except ValueError:
                print("Please enter a number!")

        # Energy demand for each time period
        print(f"\nEnergy demand for '{device}' (in kWh):")
        demands = {}
        time_labels = {
            "morning": "Morning (6am - 12pm)",
            "midday":  "Midday (12pm - 5pm)",
            "evening": "Evening (5pm - 10pm)",
            "night":   "Night (10pm - 6am)"
        }
        for period, label in time_labels.items():
            while True:
                try:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        demand_morning = st.number_input(
                            "Morning demand (kWh):",
                            min_value=0.0, value=0.0,
                            key=f"demand_morning_{device}"
                        )
                    with col2:
                        demand_midday = st.number_input(
                            "Midday demand (kWh):",
                            min_value=0.0, value=0.0,
                            key=f"demand_midday_{device}"
                        )
                    with col3:
                        demand_evening = st.number_input(
                            "Evening demand (kWh):",
                            min_value=0.0, value=0.0,
                            key=f"demand_evening_{device}"
                        )
                    with col4:
                        demand_night = st.number_input(
                            "Night demand (kWh):",
                            min_value=0.0, value=0.0,
                            key=f"demand_night_{device}"
                        )
                    if demand >= 0:
                        demands[period] = demand
                        break
                    print("Please enter a value of 0 or more!")
                except ValueError:
                    print("Please enter a number!")

        # Priority
        print(f"\nPriority of '{device}' in failure mode:")
        print("  1.0 = highest priority (e.g. hospital)")
        print("  0.5 = medium priority (e.g. office)")
        print("  0.1 = lowest priority (e.g. decoration lighting)")
        while True:
            try:
                priority = st.slider(
                    f"Priority of '{device}':",
                    min_value=0.1, max_value=1.0, value=0.5, step=0.05,
                    key=f"priority_{device}"
                )
                if 0.1 <= priority <= 1.0:
                    break
                print("Please enter a value between 0.1 and 1.0!")
            except ValueError:
                print("Please enter a number!")

        # Minimum energy requirement for each time period
        print(f"\nMinimum energy requirement for '{device}' (in kWh):")
        print("This is the bare minimum needed to keep it operational.")
        mers = {}
        for period, label in time_labels.items():
            while True:
                try:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        mer_morning = st.number_input(
                            "Morning MER (kWh):",
                            min_value=0.0, max_value=float(demand_morning), value=0.0,
                            key=f"mer_morning_{device}"
                        )
                    with col2:
                        mer_midday = st.number_input(
                            "Midday MER (kWh):",
                            min_value=0.0, max_value=float(demand_midday), value=0.0,
                            key=f"mer_midday_{device}"
                        )
                    with col3:
                        mer_evening = st.number_input(
                            "Evening MER (kWh):",
                            min_value=0.0, max_value=float(demand_evening), value=0.0,
                            key=f"mer_evening_{device}"
                        )
                    with col4:
                        mer_night = st.number_input(
                            "Night MER (kWh):",
                            min_value=0.0, max_value=float(demand_night), value=0.0,
                            key=f"mer_night_{device}"
                        )
                    if 0 <= mer <= demands[period]:
                        mers[period] = mer
                        break
                    elif mer > demands[period]:
                        print(f"MER cannot exceed demand ({demands[period]} kWh)!")
                    else:
                        print("Please enter a value of 0 or more!")
                except ValueError:
                    print("Please enter a number!")

        device_data.append({
            "Type of building": device,
            "Number of buildings": count,
            "Efficiency": efficiency,
            "Priority": priority,
            "Demand (morning)": demands["morning"],
            "Demand (midday)":  demands["midday"],
            "Demand (evening)": demands["evening"],
            "Demand (night)":   demands["night"],
            "Minimum Energy Requirement (morning)": mers["morning"],
            "Minimum Energy Requirement (midday)":  mers["midday"],
            "Minimum Energy Requirement (evening)": mers["evening"],
            "Minimum Energy Requirement (night)":   mers["night"],
        })

        print(f"\n✓ '{device}' setup complete!")

    # Convert to DataFrame
    buildings = pd.DataFrame(device_data)

    # Calculate CI Equivalent from efficiency
    buildings["CI_Equivalent"] = 1 / buildings["Efficiency"]

    # Set priority for all time periods
    for period in ["morning", "midday", "evening", "night"]:
        buildings[f"Priority ({period})"] = buildings["Priority"]

    # Solar panel setup
    print("\n" + "=" * 60)
    print("SOLAR PANEL SETUP")
    print("=" * 60)
    print("\nThe system uses live solar radiation data to estimate")
    print("how much renewable energy is available.")
    print("To do this accurately it needs to know your solar panel size.\n")

    while True:
        try:
            solar_area = st.number_input(
                "Total area of your solar panels (m²):",
                min_value=1.0, value=100.0, step=10.0
            )
            if solar_area > 0:
                break
            print("Please enter a value greater than 0!")
        except ValueError:
            print("Please enter a number!")

    while True:
        try:
            panel_efficiency = st.slider(
                "Solar panel efficiency:",
                min_value=0.05, max_value=0.5, value=0.2, step=0.01,
                format="%.2f"
            )
            if 0.05 <= panel_efficiency <= 0.5:
                break
            print("Please enter a value between 0.05 and 0.5!")
        except ValueError:
            print("Please enter a number!")

    print(f"\n✓ Solar setup: {solar_area} m² at {panel_efficiency*100:.0f}% efficiency")
    print(f"  Peak generation: {solar_area * panel_efficiency * 1000 / 1000:,.0f} kW")

    print("\n" + "=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print(f"\nTotal device types: {len(buildings)}")
    print(f"Total individual buildings: {buildings['Number of buildings'].sum()}")
    print("\nYour devices:")
    print(buildings[["Type of building", "Number of buildings", "Efficiency", "CI_Equivalent", "Priority"]].to_string(index=False))

    return buildings, solar_area, panel_efficiency

# Run the input system
buildings_raw, solar_area, panel_efficiency = get_device_data()
# Expand so each individual building gets its own row
buildings = buildings_raw.loc[
    buildings_raw.index.repeat(buildings_raw["Number of buildings"])
].reset_index(drop=True)

# Give each building a unique name
buildings["Building ID"] = buildings.groupby("Type of building").cumcount() + 1
buildings["Building Name"] = buildings["Type of building"] + " #" + buildings["Building ID"].astype(str)

print(f"Total individual buildings: {len(buildings)}")
print(buildings[["Building Name", "Demand (morning)", "CI_Equivalent"]].head(10))
def get_full_day_forecast(latitude, longitude, solar_area, panel_efficiency):
    """
    Fetches solar generation forecast for the entire day
    from Open-Meteo API. Returns estimated kWh for each
    time period based on actual forecast data, not estimates.
    """
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

        # Convert each hour's radiation to kWh
        hourly_kwh = [
            r * solar_area * panel_efficiency / 1000
            for r in hourly_radiation
        ]

        # Map hours to time periods
        # Morning  = hours 6-11
        # Midday   = hours 12-16
        # Evening  = hours 17-21
        # Night    = hours 22-23 and 0-5
        morning_kwh = sum(hourly_kwh[6:12])
        midday_kwh  = sum(hourly_kwh[12:17])
        evening_kwh = sum(hourly_kwh[17:22])
        night_kwh   = sum(hourly_kwh[22:]) + sum(hourly_kwh[0:6])

        print(f"Full day forecast fetched at {datetime.now().strftime('%H:%M:%S')}")
        print(f"Morning  (6am-12pm):  {morning_kwh:,.0f} kWh")
        print(f"Midday   (12pm-5pm):  {midday_kwh:,.0f} kWh")
        print(f"Evening  (5pm-10pm):  {evening_kwh:,.0f} kWh")
        print(f"Night    (10pm-6am):  {night_kwh:,.0f} kWh")

        return {
            "Morning": morning_kwh,
            "Midday":  midday_kwh,
            "Evening": evening_kwh,
            "Night":   night_kwh
        }

    except Exception as e:
        print(f"Error fetching forecast data: {e}")
        print("Falling back to default values")
        return None


def get_current_hour_renewable(latitude, longitude, solar_area, panel_efficiency):
    """
    Fetches live renewable energy for the current hour only.
    Used to update the current time period each hour.
    """
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

        current_hour = datetime.now().hour
        solar_radiation = data["hourly"]["shortwave_radiation"][current_hour]
        solar_kwh = solar_radiation * solar_area * panel_efficiency / 1000

        print(f"Live data fetched at {datetime.now().strftime('%H:%M:%S')}")
        print(f"Solar radiation:  {solar_radiation:.1f} W/m²")
        print(f"Total renewable:  {solar_kwh:,.0f} kWh")

        return solar_kwh

    except Exception as e:
        print(f"Error fetching live data: {e}")
        return None


def get_time_period():
    """Returns the current time period based on hour of day."""
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 17:
        return "Midday"
    elif 17 <= hour < 22:
        return "Evening"
    else:
        return "Night"


print(f"Current time period: {get_time_period()}")
print("=" * 60)
print("LOCATION SETUP")
print("=" * 60)
print("\nYour location is needed to fetch live renewable energy data.")
print("You can find your coordinates at maps.google.com")
print("(right click on your location and the coordinates appear)\n")

while True:
    try:
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
        break
    except ValueError:
        print("Please enter valid numbers!")

print(f"\n✓ Location set to: {latitude}, {longitude}")

# Fetch full day forecast for all time periods
print("\nFetching full day solar forecast...")
forecast = get_full_day_forecast(latitude, longitude, solar_area, panel_efficiency)

if forecast is not None:
    time_periods = forecast
    print("\n✓ All time periods set from real forecast data!")
else:
    print("Could not fetch forecast — using default values")
    time_periods = {
        "Morning": 2.5,
        "Midday":  6,
        "Evening": 0.2,
        "Night":   0
    }

print(f"\nTime periods (kWh):")
for period, value in time_periods.items():
    print(f"  {period}: {value:,.0f} kWh")
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

# Battery settings
while True:
    try:
        battery_capacity = st.number_input(
            "Battery capacity (kWh):",
            min_value=1.0, value=500000.0, step=1000.0
        )
        if battery_capacity > 0:
            break
        print("Please enter a value greater than 0!")
    except ValueError:
        print("Please enter a number!")

while True:
    try:
        battery_efficiency = st.slider(
            "Battery efficiency:",
            min_value=0.1, max_value=1.0, value=0.9, step=0.01,
            format="%.2f"
        )
        if 0.1 <= battery_efficiency <= 1.0:
            break
        print("Please enter a value between 0.1 and 1.0!")
    except ValueError:
        print("Please enter a number!")

print(f"\n✓ Battery: {battery_capacity:,.0f} kWh capacity at {battery_efficiency*100:.0f}% efficiency")
print("Column maps defined!")
def run_linear_programming_optimisation(buildings, time_periods, time_column_map, battery_capacity, battery_efficiency):
    """
    Uses linear programming to find the mathematically optimal
    allocation of renewable energy across all buildings and time
    periods to minimise total carbon emissions.
    """
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

    # Objective — minimise negative CI weighted allocation
    c = np.zeros(n_vars)
    for _, row in building_df.iterrows():
        t = row["time_idx"]
        b = row["building_idx"]
        c[alloc_idx(t, b)] = -row["ci"]

    # Bounds
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

    # Constraint 1 — renewable supply limit
    for t_idx, time in enumerate(time_order):
        row_constraint = np.zeros(n_vars)
        for b in range(n_buildings):
            row_constraint[alloc_idx(t_idx, b)] = 1
        row_constraint[charge_idx(t_idx)] = 1
        row_constraint[discharge_idx(t_idx)] = -1
        A_ub.append(row_constraint)
        b_ub.append(time_periods[time])

    # Constraint 2 — battery capacity
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[charge_idx(t2)] = 1
            row_constraint[discharge_idx(t2)] = -1
        A_ub.append(row_constraint)
        b_ub.append(battery_capacity)

    # Constraint 3 — battery efficiency
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[discharge_idx(t2)] = 1
            row_constraint[charge_idx(t2)] = -battery_efficiency
        A_ub.append(row_constraint)
        b_ub.append(0)

    # Run optimisation
    result = linprog(
        c,
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=bounds,
        method="highs"
    )

    if not result.success:
        print(f"Optimisation failed: {result.message}")
        return None, None

    # Extract results
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
        temp_buildings["Mode"] = "Linear Programming"

        all_results.append(temp_buildings)

    # Battery log
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

    battery_log_df = pd.DataFrame(battery_log)
    results_df = pd.concat(all_results).reset_index(drop=True)
    return results_df, battery_log_df

print("LP normal mode function defined!")
def run_lp_failure_mode(buildings, time_periods, failure_time_column_map, battery_capacity, battery_efficiency):
    """
    Two-stage linear programming failure mode.
    No fossil fuels available.
    Stage 1: Allocate MER strictly by priority order.
    Stage 2: Distribute remaining energy above MER by priority.
    """
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

    # Pre-calculate all demands, MERs and priorities
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

    # ================================================================
    # STAGE 1 — Allocate MER strictly by priority
    # ================================================================
    print("Stage 1 — Allocating MER by priority...")

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

    # Constraint 1 — total energy used <= renewable available
    for t_idx, time in enumerate(time_order):
        row_constraint = np.zeros(n_vars)
        for b in range(n_buildings):
            row_constraint[alloc_idx(t_idx, b)] = 1
        row_constraint[charge_idx(t_idx)] = 1
        row_constraint[discharge_idx(t_idx)] = -1
        A_ub_stage1.append(row_constraint)
        b_ub_stage1.append(time_periods[time])

    # Constraint 2 — battery capacity
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[charge_idx(t2)] = 1
            row_constraint[discharge_idx(t2)] = -1
        A_ub_stage1.append(row_constraint)
        b_ub_stage1.append(battery_capacity)

    # Constraint 3 — battery efficiency
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for t2 in range(t_idx + 1):
            row_constraint[discharge_idx(t2)] = 1
            row_constraint[charge_idx(t2)] = -battery_efficiency
        A_ub_stage1.append(row_constraint)
        b_ub_stage1.append(0)

    # Constraint 4 — strict priority ordering for MER
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

    result_stage1 = linprog(
        c_stage1,
        A_ub=A_ub_stage1,
        b_ub=b_ub_stage1,
        bounds=bounds_stage1,
        method="highs"
    )

    if not result_stage1.success:
        print(f"Stage 1 failed: {result_stage1.message}")
        return None, None

    print("Stage 1 complete!")

    # Calculate remaining renewable after Stage 1
    stage1_allocations = {}
    stage1_battery_charge = 0
    remaining_renewable = {}

    for t_idx, time in enumerate(time_order):
        total_allocated = sum(
            result_stage1.x[alloc_idx(t_idx, b)]
            for b in range(n_buildings)
        )
        charge = result_stage1.x[charge_idx(t_idx)]
        discharge = result_stage1.x[discharge_idx(t_idx)]
        stage1_battery_charge += charge - discharge
        remaining_renewable[t_idx] = max(
            time_periods[time] - total_allocated - charge + discharge, 0
        )
        for bdata in time_building_data[t_idx]:
            b = bdata["b_idx"]
            stage1_allocations[(t_idx, b)] = result_stage1.x[alloc_idx(t_idx, b)]

    # ================================================================
    # STAGE 2 — Distribute remaining energy above MER by priority
    # ================================================================
    print("Stage 2 — Distributing remaining energy above MER...")

    c_stage2 = np.zeros(n_vars)
    for t_idx in range(n_times):
        for bdata in time_building_data[t_idx]:
            b = bdata["b_idx"]
            c_stage2[alloc_idx(t_idx, b)] = -bdata["priority"]

    bounds_stage2 = [(0, None)] * n_vars
    for t_idx in range(n_times):
        for bdata in time_building_data[t_idx]:
            b = bdata["b_idx"]
            above_mer = max(
                bdata["demand"] - stage1_allocations.get((t_idx, b), 0), 0
            )
            bounds_stage2[alloc_idx(t_idx, b)] = (0, above_mer)
        bounds_stage2[charge_idx(t_idx)] = (0, battery_capacity)
        bounds_stage2[discharge_idx(t_idx)] = (0, battery_capacity)

    A_ub_stage2 = []
    b_ub_stage2 = []

    # Constraint — total stage 2 allocation <= remaining renewable
    for t_idx in range(n_times):
        row_constraint = np.zeros(n_vars)
        for b in range(n_buildings):
            row_constraint[alloc_idx(t_idx, b)] = 1
        row_constraint[charge_idx(t_idx)] = 1
        row_constraint[discharge_idx(t_idx)] = -1
        A_ub_stage2.append(row_constraint)
        b_ub_stage2.append(remaining_renewable[t_idx])

    # Battery constraints for stage 2
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

    result_stage2 = linprog(
        c_stage2,
        A_ub=A_ub_stage2,
        b_ub=b_ub_stage2,
        bounds=bounds_stage2,
        method="highs"
    )

    if not result_stage2.success:
        print(f"Stage 2 failed: {result_stage2.message}")
        return None, None

    print("Stage 2 complete!")

    # Combine Stage 1 and Stage 2 results
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
        temp_buildings["Mode"] = "LP Failure Mode"

        all_results.append(temp_buildings)

    # Battery log
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

    battery_log_df = pd.DataFrame(battery_log)
    results_df = pd.concat(all_results).reset_index(drop=True)
    return results_df, battery_log_df

print("LP failure mode function defined!")
def plot_device_comparison(results, run_count, current_time, mode="Normal"):
    """
    Plots renewable vs fossil fuel used for each device type
    across all time periods, just like the original per building charts.
    """
    if mode == "Normal":
        renewable_col = "renewable_kwh"
        fossil_col = "fossil_kwh"
    else:
        renewable_col = "failure_renewable_kwh"
        fossil_col = "MER Shortfall"

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

        if mode == "Normal":
            colors = ["#2ecc71", "#e74c3c"]
            labels = ["Renewable", "Fossil Fuel"]
            stacked = True
        else:
            colors = ["#2ecc71", "#e74c3c"]
            labels = ["Renewable Allocated", "MER Shortfall"]
            stacked = False

        building_data.plot(
            kind="bar", stacked=stacked, ax=axes[i],
            color=colors, edgecolor="white"
        )
        axes[i].set_title(building_type)
        axes[i].set_ylabel("Energy (kWh)")
        axes[i].set_xlabel("")
        axes[i].tick_params(axis='x', rotation=30)
        axes[i].legend(labels)

    # Hide unused chart spaces
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    plt.suptitle(
        f"Run {run_count} — {mode} Mode: Renewable vs Fossil Fuel by Device\n{current_time}",
        fontsize=14, fontweight="bold", y=1.02
    )
    plt.tight_layout()
    st.pyplot(fig)

print("Device comparison chart function defined!")
def run_hourly_live(buildings, time_periods, time_column_map, battery_capacity, battery_efficiency, latitude, longitude, solar_area, panel_efficiency, max_runs=24):
    """
    Automatically re-runs the LP optimisation every hour
    with fresh live renewable energy data.
    """
    print("=" * 60)
    print("STARTING HOURLY LIVE OPTIMISATION — NORMAL MODE")
    print("=" * 60)
    print(f"Will run every hour for {max_runs} hours")
    print("Press the stop button in JupyterLab to stop early\n")

    all_hourly_results = []
    run_count = 0

    while run_count < max_runs:
        run_count += 1
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_period = get_time_period()

        print(f"\n{'=' * 60}")
        print(f"Run {run_count} of {max_runs} — {current_time}")
        print(f"Current time period: {current_period}")
        print("=" * 60)

        # Fetch live renewable energy
        live_renewable = get_current_hour_renewable(latitude, longitude, solar_area, panel_efficiency)

        if live_renewable is not None:
            updated_time_periods = time_periods.copy()
            updated_time_periods[current_period] = live_renewable
            print(f"\nUpdated {current_period} renewable to {live_renewable:,.0f} kWh")
        else:
            updated_time_periods = time_periods.copy()
            print("Using existing values")

        # Run LP optimisation
        print("\nRunning LP optimisation...")
        results, battery_log = run_linear_programming_optimisation(
            buildings, updated_time_periods, time_column_map,
            battery_capacity, battery_efficiency
        )

        if results is not None:
            results["Run"] = run_count
            results["Timestamp"] = current_time
            all_hourly_results.append(results)

            summary = results.groupby("Time Period")[["renewable_kwh", "fossil_kwh", "emissions_prevented", "emission_potential"]].sum()
            summary = summary.reindex(["Morning", "Midday", "Evening", "Night"])

            print(f"\n===== RUN {run_count} SUMMARY =====")
            print(summary)
            print(f"\nTotal emissions prevented: {summary['emissions_prevented'].sum():,.2f} gCO2")

            # Plot results
            fig, axes = plt.subplots(1, 3, figsize=(18, 4))

            summary[["renewable_kwh", "fossil_kwh"]].plot(
                kind="bar", stacked=True, ax=axes[0],
                color=["#2ecc71", "#e74c3c"], edgecolor="white"
            )
            axes[0].set_title(f"Run {run_count} — Energy by Time Period\n{current_time}")
            axes[0].set_ylabel("Energy (kWh)")
            axes[0].tick_params(axis='x', rotation=0)
            axes[0].legend(["Renewable", "Fossil Fuel"])

            summary[["emissions_prevented", "emission_potential"]].plot(
                kind="bar", stacked=False, ax=axes[1],
                color=["#3498db", "#ff7518"], edgecolor="white"
            )
            axes[1].set_title(f"Run {run_count} — Emissions Prevented")
            axes[1].set_ylabel("gCO2")
            axes[1].tick_params(axis='x', rotation=0)
            axes[1].legend(["Prevented", "Potential"])

            battery_log.set_index("Time Period")[["Battery Charged", "Battery Discharged", "Battery Level After"]].plot(
                kind="bar", ax=axes[2],
                color=["#2ecc71", "#e74c3c", "#f39c12"], edgecolor="white"
            )
            axes[2].set_title(f"Run {run_count} — Battery Activity")
            axes[2].set_ylabel("Energy (kWh)")
            axes[2].tick_params(axis='x', rotation=0)
            axes[2].legend(["Charged", "Discharged", "Level After"])

            plt.tight_layout()
            st.pyplot(fig)
            plot_device_comparison(results, run_count, current_time, mode="Normal")

        if run_count < max_runs:
            print(f"\nWaiting 1 hour before next run...")
            time.sleep(3600)

    print("\nHourly loop complete!")

    if all_hourly_results:
        return pd.concat(all_hourly_results).reset_index(drop=True)
    return None

print("Hourly normal mode function defined!")
def run_hourly_failure_live(buildings, time_periods, failure_time_column_map, battery_capacity, battery_efficiency, latitude, longitude, solar_area, panel_efficiency, max_runs=24):
    """
    Automatically re-runs the failure mode LP optimisation
    every hour with fresh live renewable energy data.
    No fossil fuels — purely renewable and battery.
    """
    print("=" * 60)
    print("STARTING HOURLY LIVE OPTIMISATION — FAILURE MODE")
    print("=" * 60)
    print(f"Will run every hour for {max_runs} hours")
    print("No fossil fuels — renewable and battery only")
    print("Press the stop button in JupyterLab to stop early\n")

    all_hourly_results = []
    run_count = 0

    while run_count < max_runs:
        run_count += 1
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_period = get_time_period()

        print(f"\n{'=' * 60}")
        print(f"Run {run_count} of {max_runs} — {current_time}")
        print(f"Current time period: {current_period}")
        print("=" * 60)

        # Fetch live renewable energy
        live_renewable = get_current_hour_renewable(latitude, longitude, solar_area, panel_efficiency)

        if live_renewable is not None:
            updated_time_periods = time_periods.copy()
            updated_time_periods[current_period] = live_renewable
            print(f"\nUpdated {current_period} renewable to {live_renewable:,.0f} kWh")
        else:
            updated_time_periods = time_periods.copy()
            print("Using existing values")

        # Run failure mode LP optimisation
        print("\nRunning failure mode LP optimisation...")
        results, battery_log = run_lp_failure_mode(
            buildings, updated_time_periods, failure_time_column_map,
            battery_capacity, battery_efficiency
        )

        if results is not None:
            results["Run"] = run_count
            results["Timestamp"] = current_time
            all_hourly_results.append(results)

            total_buildings = len(buildings)
            period_results = results[results["Time Period"] == current_period]
            mer_met_count = period_results["MER Met"].sum()
            total_allocated = period_results["failure_renewable_kwh"].sum()
            total_shortfall = period_results["MER Shortfall"].sum()

            print(f"\n===== RUN {run_count} FAILURE MODE SUMMARY =====")
            print(f"Buildings meeting MER: {mer_met_count} / {total_buildings}")
            print(f"Total energy allocated: {total_allocated:,.2f} kWh")
            print(f"Total MER shortfall: {total_shortfall:,.2f} kWh")
            print("\nBattery log:")
            print(battery_log)

            # Plot results
            fig, axes = plt.subplots(1, 3, figsize=(18, 4))

            type_summary = period_results.groupby("Type of building")[["failure_renewable_kwh", "MER Shortfall"]].sum()
            type_summary.plot(
                kind="bar", stacked=True, ax=axes[0],
                color=["#2ecc71", "#e74c3c"], edgecolor="white"
            )
            axes[0].set_title(f"Run {run_count} — Energy vs MER Shortfall\n{current_period} | {current_time}")
            axes[0].set_ylabel("Energy (kWh)")
            axes[0].tick_params(axis='x', rotation=30)
            axes[0].legend(["Renewable Allocated", "MER Shortfall"])

            mer_by_type = period_results.groupby("Type of building")["MER Met"].sum()
            total_by_type = period_results.groupby("Type of building")["MER Met"].count()
            mer_pct = (mer_by_type / total_by_type * 100).round(1)
            mer_pct.plot(
                kind="bar", ax=axes[1],
                color="#3498db", edgecolor="white"
            )
            axes[1].set_title(f"Run {run_count} — % Buildings Meeting MER\n{current_period}")
            axes[1].set_ylabel("% Buildings")
            axes[1].set_ylim(0, 110)
            axes[1].axhline(y=100, color="red", linestyle="--", label="100% target")
            axes[1].tick_params(axis='x', rotation=30)
            axes[1].legend()

            battery_log.set_index("Time Period")[["Battery Charged", "Battery Discharged", "Battery Level After"]].plot(
                kind="bar", ax=axes[2],
                color=["#2ecc71", "#e74c3c", "#f39c12"], edgecolor="white"
            )
            axes[2].set_title(f"Run {run_count} — Battery Activity")
            axes[2].set_ylabel("Energy (kWh)")
            axes[2].tick_params(axis='x', rotation=0)
            axes[2].legend(["Charged", "Discharged", "Level After"])

            plt.tight_layout()
            st.pyplot(fig)
            plot_device_comparison(results, run_count, current_time, mode="Failure")

        if run_count < max_runs:
            print(f"\nWaiting 1 hour before next run...")
            time.sleep(3600)

    print("\nHourly failure mode loop complete!")

    if all_hourly_results:
        return pd.concat(all_hourly_results).reset_index(drop=True)
    return None

print("Hourly failure mode function defined!")
print("=" * 60)
print("WHICH MODE WOULD YOU LIKE TO RUN?")
print("=" * 60)
print("\n1. Normal mode — optimises for minimum carbon emissions")
print("   (buildings can use fossil fuels if renewable runs out)")
print("\n2. Failure mode — no fossil fuels available")
print("   (every building must get at least its minimum energy requirement)")
print("\n3. Both modes — run normal first then failure mode")

while True:
    choice = st.radio(
        "Which mode would you like to run?",
        options=["1", "2", "3"],
        format_func=lambda x: {
            "1": "Normal mode — optimises for minimum carbon emissions",
            "2": "Failure mode — no fossil fuels available",
            "3": "Both modes — run normal first then failure mode"
        }[x]
    )
    if choice in ["1", "2", "3"]:
        break
    print("Please enter 1, 2 or 3!")

while True:
    try:
        max_runs = int(input("\nHow many hours would you like to run for? (e.g. 24 for a full day): "))
        if max_runs > 0:
            break
        print("Please enter a number greater than 0!")
    except ValueError:
        print("Please enter a whole number!")

print(f"\nStarting for {max_runs} hours...")

if choice == "1":
    hourly_results = run_hourly_live(
        buildings=buildings,
        time_periods=time_periods,
        time_column_map=time_column_map,
        battery_capacity=battery_capacity,
        battery_efficiency=battery_efficiency,
        latitude=latitude,
        longitude=longitude,
        solar_area=solar_area,
        panel_efficiency=panel_efficiency,
        max_runs=max_runs
    )

elif choice == "2":
    hourly_failure_results = run_hourly_failure_live(
        buildings=buildings,
        time_periods=time_periods,
        failure_time_column_map=failure_time_column_map,
        battery_capacity=battery_capacity,
        battery_efficiency=battery_efficiency,
        latitude=latitude,
        longitude=longitude,
        solar_area=solar_area,
        panel_efficiency=panel_efficiency,
        max_runs=max_runs
    )

elif choice == "3":
    print("\nRunning normal mode first...")
    hourly_results = run_hourly_live(
        buildings=buildings,
        time_periods=time_periods,
        time_column_map=time_column_map,
        battery_capacity=battery_capacity,
        battery_efficiency=battery_efficiency,
        latitude=latitude,
        longitude=longitude,
        solar_area=solar_area,
        panel_efficiency=panel_efficiency,
        max_runs=max_runs
    )
    print("\nNow running failure mode...")
    hourly_failure_results = run_hourly_failure_live(
        buildings=buildings,
        time_periods=time_periods,
        failure_time_column_map=failure_time_column_map,
        battery_capacity=battery_capacity,
        battery_efficiency=battery_efficiency,
        latitude=latitude,
        longitude=longitude,
        solar_area=solar_area,
        panel_efficiency=panel_efficiency,
        max_runs=max_runs
    )

