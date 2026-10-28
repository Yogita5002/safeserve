"""SafeServe demo dashboard.   Run:  streamlit run app.py
Pick a scenario, run all methods side by side, and see where each one delivered safely or unsafely."""
import pandas as pd
import pydeck as pdk
import streamlit as st
from safeserve.data_gen import generate
from safeserve.simulator import run, METHODS
from safeserve import safety as S

st.set_page_config(page_title="SafeServe", layout="wide")
st.title("SafeServe: temperature-adaptive food redistribution")
st.caption("Synthetic donors, recipients and volunteers on real Chennai coordinates. "
           "Every method is judged by the same USDA FSIS / FSSAI-based safety rule.")

with st.sidebar:
    seed = st.number_input("Scenario seed", 0, 999, 0)
    climate = st.radio("Climate", ["summer", "winter"])
    n_don = st.slider("Donations per day", 20, 80, 45)
    two_w = st.slider("Two-wheeler volunteers", 2, 12, 6)
    autos = st.slider("Auto-rickshaws", 0, 5, 2)
    chosen = st.multiselect("Methods", METHODS, default=["FCFS-Static", "SafeServe"])
    go = st.button("Run simulation", type="primary")

temps = pd.DataFrame({"hour": range(12, 25),
                      "ambient_C": [round(S.ambient_temp(h * 60, climate), 1) for h in range(12, 25)]})
st.subheader("Ambient temperature profile")
st.line_chart(temps, x="hour", y="ambient_C")

if go:
    sc = generate(int(seed), n_donations=n_don, n_two_wheelers=two_w, n_autos=autos)
    results = {}
    with st.spinner("Solving matching and routing every 20 minutes..."):
        for m in chosen:
            results[m] = run(sc, m, climate)
    table = pd.DataFrame([{k: v for k, v in r.items() if k != "log"} for r in results.values()])
    st.subheader("Results")
    st.dataframe(table[["method", "safe_meals", "unsafe_meals", "safe_rate", "unsafe_share",
                        "mean_latency_min", "km_per_safe_meal", "jain_fairness"]], width="stretch")

    for m, r in results.items():
        st.markdown(f"#### {m}: delivered donations")
        log = pd.DataFrame(r["log"])
        if log.empty:
            st.info("No deliveries")
            continue
        don = {d.id: d for d in sc.donations}
        rec = {x.id: x for x in sc.recipients}
        log["src_lat"] = log.donation.map(lambda i: don[i].lat)
        log["src_lon"] = log.donation.map(lambda i: don[i].lon)
        log["dst_lat"] = log.recipient.map(lambda i: rec[i].lat)
        log["dst_lon"] = log.recipient.map(lambda i: rec[i].lon)
        log["color"] = log.safe.map(lambda s: [30, 150, 80] if s else [220, 50, 50])
        layer = pdk.Layer("ArcLayer", data=log, get_source_position=["src_lon", "src_lat"],
                          get_target_position=["dst_lon", "dst_lat"], get_source_color="color",
                          get_target_color="color", get_width=3)
        view = pdk.ViewState(latitude=13.01, longitude=80.21, zoom=11.5)
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, map_style=None))
        st.caption("Green arcs = delivered within the safe window. Red arcs = delivered after it.")
