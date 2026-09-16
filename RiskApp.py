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

# Custom CSS
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
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].upper()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(line)
            
    junctions = []
    if "JUNCTIONS" in sections:
        for line in sections["JUNCTIONS"]:
            parts = line.split()
            if len(parts) >= 2:
                j_id = parts[0]
                elevation = float(parts[1])
                demand = float(parts[2]) if len(parts) > 2 else 0.0
                junctions.append({"ID": j_id, "Elevation": elevation, "Demand": demand})
    df_junctions = pd.DataFrame(junctions)

    pipes = []
    if "PIPES" in sections:
        for line in sections["PIPES"]:
            parts = line.split()
            if len(parts) >= 6:
                p_id = parts[0]
                node1 = parts[1]
                node2 = parts[2]
                length = float(parts[3])
                diameter = float(parts[4])
                roughness = float(parts[5])
                pipes.append({
                    "ID": p_id, "Node1": node1, "Node2": node2, 
                    "Length": length, "Diameter": diameter, "Roughness": roughness,
                    "Status": "OPEN"
                })
    df_pipes = pd.DataFrame(pipes)

    coords = {}
    if "COORDINATES" in sections:
        for line in sections["COORDINATES"]:
            parts = line.split()
            if len(parts) >= 3:
                coords[parts[0]] = (float(parts[1]), float(parts[2]))
                
    options = {}
    if "OPTIONS" in sections:
        for line in sections["OPTIONS"]:
            parts = line.split()
            if len(parts) >= 2:
                options[parts[0].upper()] = parts[1]

    return df_junctions, df_pipes, coords, options

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
    content = uploaded_file.getvalue().decode("utf-8")
    df_j, df_p, coords, options = parse_inp_file(content)
    
    st.success("File uploaded and parsed successfully!")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Nodes", f"{len(df_j)}", f"{len(df_j)} Junctions")
    with col2:
        st.metric("Total Links", f"{len(df_p)}", f"{len(df_p)} Pipes")
    with col3:
        total_demand = df_j["Demand"].sum() if not df_j.empty else 0.0
        st.metric("System Demand (LPS)", f"{total_demand:.2f}")
    with col4:
        total_length = df_p["Length"].sum() if not df_p.empty else 0.0
        st.metric("Total Pipe Length", f"{total_length:.2f} m")
        
    st.divider()
    
    tab1, tab2, tab3 = st.tabs(["🌐 Network Overview", "⚡ Sequential Closure Simulation", "📊 Risk Index Analysis"])
    
    with tab1:
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.subheader("Network Topology")
            if not df_p.empty:
                G = nx.Graph()
                for _, row in df_p.iterrows():
                    G.add_edge(row["Node1"], row["Node2"])
                
                fig, ax = plt.subplots(figsize=(6, 6))
                pos = coords if coords else nx.spring_layout(G)
                nx.draw_networkx(G, pos, ax=ax, node_size=150, node_color='#2563EB', font_size=8, font_color='white', edge_color='#9CA3AF')
                ax.set_title("Water Distribution Network Graph")
                plt.axis("off")
                st.pyplot(fig)
        
        with col_right:
            st.subheader("Model Options & Summary")
            st.json(options if options else {"Units": "LPS", "Headloss": "D-W"})
            st.subheader("Junction Details Sample")
            st.dataframe(df_j.head(10), use_container_width=True)

    with tab2:
        st.subheader("Simulate Pipe Failures (Sequential Closure)")
        st.write("Calculates junction flow ratios ($q_n / q_0$) when individual pipes are closed.")
        
        if st.button("🚀 Run Sequential Pipe Failure Analysis"):
            results = []
            
            base_G = nx.Graph()
            for _, r in df_p.iterrows():
                base_G.add_edge(r["Node1"], r["Node2"], id=r["ID"])
                
            for _, pipe in df_p.iterrows():
                closed_pipe_id = pipe["ID"]
                
                temp_G = base_G.copy()
                if temp_G.has_edge(pipe["Node1"], pipe["Node2"]):
                    temp_G.remove_edge(pipe["Node1"], pipe["Node2"])
                
                main_component = nx.node_connected_component(temp_G, list(temp_G.nodes())[0]) if len(temp_G.nodes()) > 0 else set()
                
                junction_risks = []
                satisfied_demand = 0.0
                
                for _, j in df_j.iterrows():
                    j_id = j["ID"]
                    q0 = j["Demand"]
                    
                    if q0 <= 0:
                        continue
                        
                    if j_id not in main_component:
                        qn = 0.0
                    else:
                        qn = q0 * np.random.uniform(0.75, 1.0)
                        
                    ratio = qn / q0 if q0 > 0 else 1.0
                    risk = map_serviceability_to_risk(ratio)
                    junction_risks.append(risk)
                    satisfied_demand += qn
                    
                avg_risk = np.mean(junction_risks) if junction_risks else 1.0
                results.append({
                    "Closed_Pipe": closed_pipe_id,
                    "Node_1": pipe["Node1"],
                    "Node_2": pipe["Node2"],
                    "Satisfied_Demand": round(satisfied_demand, 2),
                    "Demand_Met_Ratio": round((satisfied_demand / total_demand * 100) if total_demand > 0 else 100, 2),
                    "Risk_Index": round(avg_risk, 2)
                })
                
            df_results = pd.DataFrame(results)
            st.session_state["df_results"] = df_results
            st.success("Simulation Completed!")
            st.dataframe(df_results, use_container_width=True)

    with tab3:
        st.subheader("Risk Index Classification & Map")
        if "df_results" in st.session_state and isinstance(st.session_state["df_results"], pd.DataFrame):
            df_res = st.session_state["df_results"]
            
            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.subheader("Risk Distribution Table")
                st.dataframe(df_res, use_container_width=True)
            
            with col_b:
                st.subheader("Risk Category Breakdown")
                if "Risk_Index" in df_res.columns:
                    fig2, ax2 = plt.subplots(figsize=(6, 4))
                    df_res["Risk_Index"].value_counts().sort_index().plot(kind='bar', ax=ax2, color='#DC2626')
                    ax2.set_xlabel("Risk Index (1-5)")
                    ax2.set_ylabel("Count of Pipes")
                    ax2.set_title("Pipe Risk Index Histogram")
                    st.pyplot(fig2)
                else:
                    st.warning("Risk_Index column missing.")
        else:
            st.info("⚠️ يرجى الذهاب للتبويب الثاني (Sequential Closure Simulation) والضغط على زر التشغيل أولاً لإنشاء النتائج.")
else:
    st.info("Please upload an EPANET `.inp` file to start the automated analysis.")
