import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
import wntr
import tempfile
import os

st.set_page_config(
    page_title="EPANET Hydraulic Simulation Suite",
    page_icon="💧",
    layout="wide"
)

st.markdown("""
<style>
    .main-title {
        color: #1E3A8A;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-weight: 700;
        text-align: center;
        margin-bottom: 5px;
    }
    .sub-title {
        color: #4B5563;
        text-align: center;
        font-size: 1.1rem;
        margin-bottom: 25px;
    }
    .info-box {
        background-color: #F3F4F6;
        padding: 15px;
        border-radius: 8px;
        border-right: 5px solid #1E3A8A;
        margin-top: 25px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>💧 EPANET Hydraulic Simulation Suite</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Exact Hydraulic Pipe Closure Analysis (LPS Units)</p>", unsafe_allow_html=True)

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

uploaded_file = st.file_uploader("Drop your .inp file here or click to browse", type=["inp"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".inp") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    try:
        wn = wntr.network.WaterNetworkModel(tmp_path)
        
        # استخراج الطلبات بـ LPS لجميع العقد بشكل صحيح
        junction_demands_lps = {}
        for name, j in wn.junctions():
            node_demand_m3s = 0.0
            # الجمع لجميع فئات الطلب داخل العقدة
            for ts in j.demand_timeseries_list:
                node_demand_m3s += float(ts.base_demand)
            # تحويل من m3/s إلى LPS (الضرب في 1000)
            junction_demands_lps[name] = node_demand_m3s * 1000.0

        base_total_demand = sum(junction_demands_lps.values())
        
        st.success("File uploaded successfully!")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Nodes", f"{len(list(wn.junctions()))}")
        with col2:
            st.metric("Total Links", f"{len(list(wn.pipes()))}")
        with col3:
            st.metric("Base System Demand (LPS)", f"{base_total_demand:.2f}")
        with col4:
            total_length = sum(p.length for name, p in wn.pipes())
            st.metric("Total Pipe Length", f"{total_length:.2f} m")
            
        st.divider()
        
        tab1, tab2, tab3 = st.tabs(["🌐 Network Overview", "⚡ Sequential Closure Simulation", "📊 Risk Index Analysis"])
        pipes_list = [name for name, p in wn.pipes()]
        
        with tab1:
            st.subheader("Network Summary")
            pipes_data = [{"ID": name, "Length": p.length, "Diameter": p.diameter, "Roughness": p.roughness} for name, p in wn.pipes()]
            st.dataframe(pd.DataFrame(pipes_data), use_container_width=True)

        with tab2:
            st.subheader("Simulate Pipe Failures (Sequential Closure)")
            st.write("Calculates exact hydraulic availability by evaluating network connectivity & system demand.")
            
            if st.button("🚀 Run Exact Pipe Failure Analysis"):
                results = []
                progress_bar = st.progress(0)
                total_pipes = len(pipes_list)
                
                G = wn.to_graph().to_undirected()
                source_nodes = set(wn.reservoir_name_list + wn.tank_name_list)

                for idx, pipe_name in enumerate(pipes_list):
                    G_temp = G.copy()
                    pipe_obj = wn.get_link(pipe_name)
                    u, v = pipe_obj.start_node_name, pipe_obj.end_node_name
                    
                    if G_temp.has_edge(u, v):
                        G_temp.remove_edge(u, v)
                    
                    connected_to_source = set()
                    for src in source_nodes:
                        if src in G_temp:
                            connected_nodes = nx.node_connected_component(G_temp, src)
                            connected_to_source.update(connected_nodes)
                    
                    satisfied_demand = 0.0
                    for j_name, d_val in junction_demands_lps.items():
                        if j_name in connected_to_source:
                            satisfied_demand += d_val

                    ratio = (satisfied_demand / base_total_demand * 100.0) if base_total_demand > 0 else 0.0
                    risk = map_serviceability_to_risk(ratio)
                    
                    results.append({
                        "Closed_Pipe": pipe_name,
                        "Satisfied_Demand (LPS)": round(float(satisfied_demand), 2),
                        "Demand_Met_Ratio": round(float(ratio), 2),
                        "Risk_Index": risk
                    })
                    
                    progress_bar.progress((idx + 1) / total_pipes)
                    
                df_results = pd.DataFrame(results)
                st.session_state["df_results"] = df_results
                st.success("Pipe Closure Analysis Completed Successfully!")
                st.dataframe(df_results, use_container_width=True)

        with tab3:
            st.subheader("Risk Index Classification & Map")
            if "df_results" in st.session_state:
                df_res = st.session_state["df_results"]
                
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    st.subheader("Risk Distribution Table")
                    st.dataframe(df_res[["Closed_Pipe", "Satisfied_Demand (LPS)", "Demand_Met_Ratio", "Risk_Index"]], use_container_width=True)
                
                with col_b:
                    st.subheader("Risk Category Breakdown")
                    color_map = {
                        1: '#2563EB',
                        2: '#38BDF8',
                        3: '#EAB308',
                        4: '#F97316',
                        5: '#DC2626'
                    }
                    
                    counts = df_res["Risk_Index"].value_counts().sort_index()
                    bar_colors = [color_map.get(idx, '#2563EB') for idx in counts.index]
                    
                    fig2, ax2 = plt.subplots(figsize=(6, 4))
                    ax2.bar(counts.index.astype(str), counts.values, color=bar_colors)
                    ax2.set_xlabel("Risk Index (1: Low Risk -> 5: High Risk)")
                    ax2.set_ylabel("Count of Pipes")
                    ax2.set_title("Pipe Risk Index Histogram")
                    st.pyplot(fig2)
            else:
                st.info("يرجى تشغيل المحاكاة من التبويب الثاني أولاً.")

        st.markdown("""
        <div class="info-box">
            <h3>💡 مصطلحات وتعريفات التحليل الهيدروليكي:</h3>
            <ul>
                <li><b>Satisfied Demand (الطلب المستوفى):</b> كمية المياه الفعلية الواصلة للعقد المتصلة بالخزان بوحدة LPS.</li>
                <li><b>Demand Met Ratio (نسبة تلبية الطلب):</b> النسبة المئوية للمياه الواصلة مقارنة بالطلب الإجمالي.</li>
                <li><b>Risk Index (مؤشر الخطورة):</b> من 1 (منخفض) إلى 5 (حرج).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
else:
    st.info("Please upload an EPANET `.inp` file to start the automated analysis.")
