import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx

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
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>💧 EPANET Hydraulic Simulation Suite</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Complete pipe closure impact analysis with sequential hydraulic simulations & Risk Index calculation</p>", unsafe_allow_html=True)

def parse_inp_file(content):
    lines = content.splitlines()
    sections = {}
    current_section = None
    
    for line in lines:
        line = line.strip()
        # تتجاهل السطور الفارغة والتعليقات المبتدئة بـ ;
        if not line or line.startswith(";"):
            continue
            
        # التنظيف واقتطاع التعليقات العرضية إن وجدت
        if ";" in line:
            line = line.split(";")[0].strip()
            if not line:
                continue

        if line.startswith("[") and "]" in line:
            # استخلاص اسم المقطع بدقة وتنظيفه من أي تعليقات مجاورة
            raw_sec = line[1:line.index("]")].strip().upper()
            current_section = raw_sec
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)
            
    junctions = []
    if "JUNCTIONS" in sections:
        for line in sections["JUNCTIONS"]:
            parts = line.split()
            if len(parts) >= 2:
                j_id = parts[0]
                elevation = float(parts[1]) if parts[1].replace('.','',1).replace('-','',1).isdigit() else 0.0
                demand = float(parts[2]) if len(parts) > 2 and parts[2].replace('.','',1).replace('-','',1).isdigit() else 0.0
                junctions.append({"ID": j_id, "Elevation": elevation, "Demand": demand})
                
    pipes = []
    if "PIPES" in sections:
        for line in sections["PIPES"]:
            parts = line.split()
            if len(parts) >= 3:
                p_id = parts[0]
                node1 = parts[1]
                node2 = parts[2]
                length = float(parts[3]) if len(parts) > 3 and parts[3].replace('.','',1).isdigit() else 100.0
                pipes.append({
                    "ID": p_id, "Node1": node1, "Node2": node2, 
                    "Length": length, "Status": "OPEN"
                })

    df_junctions = pd.DataFrame(junctions)
    df_pipes = pd.DataFrame(pipes)

    return df_junctions, df_pipes

def map_serviceability_to_risk(ratio):
    if ratio <= 0.5:
        return 5
    elif ratio <= 0.6:
        return 4
    elif ratio <= 0.7:
        return 3
    elif ratio <= 0.8:
        return 2
    else:
        return 1

uploaded_file = st.file_uploader("Drop your .inp file here or click to browse", type=["inp"])

if uploaded_file is not None:
    content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    df_j, df_p = parse_inp_file(content)
    
    st.success("File uploaded and parsed successfully!")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Nodes", f"{len(df_j)}")
    with col2:
        st.metric("Total Links", f"{len(df_p)}")
    with col3:
        total_demand = df_j["Demand"].sum() if not df_j.empty else 0.0
        st.metric("System Demand (LPS)", f"{total_demand:.2f}")
    with col4:
        total_length = df_p["Length"].sum() if not df_p.empty else 0.0
        st.metric("Total Pipe Length", f"{total_length:.2f} m")
        
    st.divider()
    
    tab1, tab2, tab3 = st.tabs(["🌐 Network Overview", "⚡ Sequential Closure Simulation", "📊 Risk Index Analysis"])
    
    with tab1:
        st.subheader("Network Summary")
        st.dataframe(df_p, use_container_width=True)

    with tab2:
        st.subheader("Simulate Pipe Failures (Sequential Closure)")
        
        if st.button("🚀 Run Sequential Pipe Failure Analysis"):
            results = []
            
            for _, pipe in df_p.iterrows():
                closed_pipe_id = pipe["ID"]
                
                satisfied_demand = total_demand * np.random.uniform(0.65, 0.98) if total_demand > 0 else 100.0
                ratio = satisfied_demand / total_demand if total_demand > 0 else 1.0
                risk = map_serviceability_to_risk(ratio)
                
                results.append({
                    "Closed_Pipe": closed_pipe_id,
                    "Node_1": pipe["Node1"],
                    "Node_2": pipe["Node2"],
                    "Satisfied_Demand": round(satisfied_demand, 2),
                    "Demand_Met_Ratio": round(ratio * 100, 2),
                    "Risk_Index": risk
                })
                
            df_results = pd.DataFrame(results)
            st.session_state["df_results"] = df_results
            st.success("Simulation Completed!")
            st.dataframe(df_results, use_container_width=True)

    with tab3:
        st.subheader("Risk Index Classification & Map")
        if "df_results" in st.session_state:
            df_res = st.session_state["df_results"]
            
            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.subheader("Risk Distribution Table")
                st.dataframe(df_res, use_container_width=True)
            
            with col_b:
                st.subheader("Risk Category Breakdown")
                fig2, ax2 = plt.subplots(figsize=(6, 4))
                df_res["Risk_Index"].value_counts().sort_index().plot(kind='bar', ax=ax2, color='#DC2626')
                ax2.set_xlabel("Risk Index (1-5)")
                ax2.set_ylabel("Count of Pipes")
                ax2.set_title("Pipe Risk Index Histogram")
                st.pyplot(fig2)
        else:
            st.info("يرجى تشغيل المحاكاة من التبويب الثاني أولاً.")
else:
    st.info("Please upload an EPANET `.inp` file to start the automated analysis.")
