import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import wntr
import tempfile
import os

st.set_page_config(
    page_title="EPANET Hydraulic & Risk Assessment Suite",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #F8FAFC; }
    .main-title {
        color: #0F172A;
        font-family: 'Segoe UI', Roboto, sans-serif;
        font-weight: 800;
        text-align: center;
        margin-bottom: 5px;
    }
    .sub-title {
        color: #475569;
        text-align: center;
        font-size: 1.15rem;
        margin-bottom: 25px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>💧 EPANET Hydraulic & Risk Assessment Suite</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Advanced Sequential Pipe Failure Simulation & Node Diagnostics</p>", unsafe_allow_html=True)

def map_serviceability_to_risk(ratio):
    if ratio <= 50.0:
        return 5
    elif ratio <= 60.0:
        return 4
    elif ratio <= 70.0:
        return 3
    elif ratio <= 80.0:
        return 2
    else:
        return 1

def get_node_demand_lps(junction, wn_units):
    total_demand = 0.0
    try:
        total_demand = float(junction.base_demand)
    except Exception:
        try:
            for ts in junction.demand_timeseries_list:
                if hasattr(ts, 'base_demand'):
                    total_demand += float(ts.base_demand)
                elif isinstance(ts, (list, tuple)) and len(ts) > 0:
                    total_demand += float(ts[0])
        except Exception:
            total_demand = 0.0

    if str(wn_units).upper() in ['LPS', 'SI', 'M3/S', 'M3S']:
        if total_demand < 100:
            return total_demand * 1000.0
    return total_demand

st.sidebar.header("📁 File Upload & Settings")
uploaded_file = st.sidebar.file_uploader("Upload EPANET (.inp) File", type=["inp"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".inp") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    try:
        wn = wntr.network.WaterNetworkModel(tmp_path)
        
        junction_demands_lps = {}
        for name, j in wn.junctions():
            junction_demands_lps[name] = get_node_demand_lps(j, wn.options.hydraulic.inpfile_units)

        base_total_demand = sum(junction_demands_lps.values())
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Nodes", f"{len(list(wn.junctions()))}")
        with col2:
            st.metric("Total Links / Pipes", f"{len(list(wn.pipes()))}")
        with col3:
            st.metric("Base System Demand", f"{base_total_demand:.2f} LPS")
        with col4:
            total_length = sum(p.length for name, p in wn.pipes())
            st.metric("Total Network Length", f"{total_length:.2f} m")
            
        st.divider()
        
        tab1, tab2, tab3 = st.tabs(["🌐 Network Overview", "⚡ Sequential Closure Simulation", "📊 Risk Index Analysis"])
        pipes_list = [name for name, p in wn.pipes()]
        
        with tab1:
            st.subheader("📋 Network Components Summary")
            pipes_data = [{"ID": name, "Length (m)": p.length, "Diameter (m)": p.diameter, "Roughness": p.roughness} for name, p in wn.pipes()]
            st.dataframe(pd.DataFrame(pipes_data), use_container_width=True)

        with tab2:
            st.subheader("⚡ Simulate Pipe Failures (Sequential Closure)")
            st.write("Calculates exact hydraulic availability & tracks negative pressure and unmet demands per node.")
            
            if st.button("🚀 Run Exact Pipe Failure Analysis", type="primary", use_container_width=True):
                results = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_pipes = len(pipes_list)

                for idx, pipe_name in enumerate(pipes_list):
                    status_text.text(f"Simulating failure for Pipe {pipe_name} ({idx+1}/{total_pipes})...")
                    
                    wn_sim = wntr.network.WaterNetworkModel(tmp_path)
                    pipe_to_close = wn_sim.get_link(pipe_name)
                    pipe_to_close.initial_status = wntr.network.LinkStatus.Closed
                    
                    negative_nodes_info = []
                    unmet_nodes_info = []
                    satisfied_demand = 0.0

                    try:
                        sim = wntr.sim.EpanetSimulator(wn_sim)
                        sim_results = sim.run_sim()
                        
                        pressure_df = sim_results.node['pressure']
                        last_time = pressure_df.index[-1]
                        
                        for j_name in wn_sim.junction_name_list:
                            p_val = pressure_df.loc[last_time, j_name]
                            d_lps = junction_demands_lps.get(j_name, 0.0)
                            
                            if p_val > 0:
                                satisfied_demand += d_lps
                            else:
                                negative_nodes_info.append(f"{j_name} ({p_val:.2f} m)")
                                if d_lps > 0:
                                    unmet_nodes_info.append(f"{j_name} ({d_lps:.2f} LPS)")

                    except Exception:
                        satisfied_demand = 0.0
                        negative_nodes_info = ["Simulation Failed"]
                        unmet_nodes_info = ["All Nodes Cut"]

                    satisfied_demand = min(satisfied_demand, base_total_demand)
                    ratio = (satisfied_demand / base_total_demand * 100.0) if base_total_demand > 0 else 0.0
                    risk = map_serviceability_to_risk(ratio)
                    
                    neg_str = ", ".join(negative_nodes_info) if negative_nodes_info else "None"
                    unmet_str = ", ".join(unmet_nodes_info) if unmet_nodes_info else "None"
                    
                    results.append({
                        "Closed_Pipe": pipe_name,
                        "Satisfied_Demand (LPS)": round(float(satisfied_demand), 2),
                        "Demand_Met_Ratio (%)": f"{round(float(ratio), 2)}%",
                        "Negative_Pressure_Nodes": neg_str,
                        "Unmet_Demand_Nodes": unmet_str,
                        "Risk_Index": risk
                    })
                    
                    progress_bar.progress((idx + 1) / total_pipes)
                
                status_text.empty()
                df_results = pd.DataFrame(results)
                st.session_state["df_results"] = df_results
                st.success("✅ Pipe Closure Analysis Completed Successfully!")
                
                # ترتيب الأعمدة في العرض المباشر بالتبويب الثاني
                columns_order = [
                    "Closed_Pipe", 
                    "Satisfied_Demand (LPS)", 
                    "Demand_Met_Ratio (%)", 
                    "Negative_Pressure_Nodes", 
                    "Unmet_Demand_Nodes", 
                    "Risk_Index"
                ]
                st.dataframe(df_results[columns_order], use_container_width=True)

        with tab3:
            st.subheader("📊 Risk Index Classification & Analysis")
            if "df_results" in st.session_state:
                df_res = st.session_state["df_results"]
                
                risk_counts = df_res["Risk_Index"].value_counts().reindex([1, 2, 3, 4, 5], fill_value=0)
                
                m_cols = st.columns(5)
                colors_hex = ['#2563EB', '#38BDF8', '#EAB308', '#F97316', '#DC2626']
                
                for i in range(1, 6):
                    with m_cols[i-1]:
                        st.markdown(
                            f"<div style='background-color:{colors_hex[i-1]}; padding: 10px; border-radius: 8px; text-align: center; color: white; font-weight: bold;'>"
                            f"<div style='font-size: 0.9rem;'>Risk {i}</div>"
                            f"<div style='font-size: 1.8rem;'>{risk_counts[i]}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                
                st.write("")
                col_a, col_b = st.columns([1.4, 1])
                
                with col_a:
                    st.markdown("### 📝 Results Table with Node Diagnostics")
                    columns_order = [
                        "Closed_Pipe", 
                        "Satisfied_Demand (LPS)", 
                        "Demand_Met_Ratio (%)", 
                        "Negative_Pressure_Nodes", 
                        "Unmet_Demand_Nodes", 
                        "Risk_Index"
                    ]
                    st.dataframe(df_res[columns_order], use_container_width=True, height=400)
                
                with col_b:
                    st.markdown("### 📈 Risk Index Distribution Chart")
                    color_map = {1: '#2563EB', 2: '#38BDF8', 3: '#EAB308', 4: '#F97316', 5: '#DC2626'}
                    bar_colors = [color_map[idx] for idx in range(1, 6)]
                    
                    fig2, ax2 = plt.subplots(figsize=(6, 4.5))
                    x_labels = [f"Risk {i}" for i in range(1, 6)]
                    y_values = [risk_counts[i] for i in range(1, 6)]
                    
                    bars = ax2.bar(x_labels, y_values, color=bar_colors, edgecolor='black', linewidth=0.8, width=0.6)
                    ax2.set_xlabel("Risk Index Category (1 to 5)", fontsize=11, fontweight='bold', labelpad=8)
                    ax2.set_ylabel("Count of Pipes", fontsize=11, fontweight='bold', labelpad=8)
                    ax2.set_title("Distribution of Pipes by Risk Level", fontsize=12, fontweight='bold', pad=12)
                    ax2.grid(axis='y', linestyle='--', alpha=0.5)
                    
                    max_y = max(y_values) if max(y_values) > 0 else 1
                    ax2.set_ylim(0, max_y * 1.2)
                    
                    for bar in bars:
                        height = bar.get_height()
                        ax2.annotate(f'{int(height)}',
                                     xy=(bar.get_x() + bar.get_width() / 2, height),
                                     xytext=(0, 4),
                                     textcoords="offset points",
                                     ha='center', va='bottom', fontsize=11, fontweight='bold', color='#0F172A')
                        
                    st.pyplot(fig2)

        st.markdown("---")
        st.markdown("### 🏷️ Risk Index Assessment Criteria & Ranges")
        
        range_data = [
            {"Risk Index": "Risk 1 (Very Low Risk)", "Demand Met Range (%)": "> 80.0%", "Description": "تلبية سعة الشبكة عالية جداً وتأثير الإغلاق طفيف جداً على المستخدمين."},
            {"Risk Index": "Risk 2 (Low Risk)", "Demand Met Range (%)": "70.1% - 80.0%", "Description": "تأثير محلي محدود، معظم الشبكة تعمل بضغوط كافية."},
            {"Risk Index": "Risk 3 (Moderate Risk)", "Demand Met Range (%)": "60.1% - 70.0%", "Description": "انخفاض متوسط في الضغوط وانقطاع جزئي في بعض المناطق الحيوية."},
            {"Risk Index": "Risk 4 (High Risk)", "Demand Met Range (%)": "50.1% - 60.0%", "Description": "انخفاض حاد في ضغط المياه وتأثر قطاع واسع من مستهلكي الشبكة."},
            {"Risk Index": "Risk 5 (Critical Risk)", "Demand Met Range (%)": "≤ 50.0%", "Description": "فشل هيدروليكي حرج، الانقطاع يطال غالبية أجزاء الشبكة أو خط رئيسي."}
        ]
        
        st.table(pd.DataFrame(range_data))

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
else:
    st.info("👈 Please upload an EPANET `.inp` file from the sidebar to start the analysis.")
