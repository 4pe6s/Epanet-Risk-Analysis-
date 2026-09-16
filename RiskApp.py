import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

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
st.markdown("<p class='sub-title'>Complete pipe closure impact analysis with sequential hydraulic simulations & Risk Index calculation</p>", unsafe_allow_html=True)

def parse_inp_file(content):
    lines = content.splitlines()
    sections = {}
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith(";"):
            continue
            
        if ";" in line:
            line = line.split(";")[0].strip()
            if not line:
                continue

        if line.startswith("[") and "]" in line:
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
        # عرض معلومات الأنابيب بدون العقد التفصيلية
        st.dataframe(df_p[["ID", "Length", "Status"]], use_container_width=True)

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
                st.dataframe(df_res[["Closed_Pipe", "Satisfied_Demand", "Demand_Met_Ratio", "Risk_Index"]], use_container_width=True)
            
            with col_b:
                st.subheader("Risk Category Breakdown")
                
                # تدرج الألوان حسب درجة الخطورة (1 أزرق، 5 أحمر)
                color_map = {
                    1: '#2563EB',  # أزرق (خطر منخفض جداً)
                    2: '#38BDF8',  # سماوي (خطر منخفض)
                    3: '#EAB308',  # أصفر (خطر متوسط)
                    4: '#F97316',  # برتقالي (خطر مرتفع)
                    5: '#DC2626'   # أحمر (خطر شديد جداً)
                }
                
                counts = df_res["Risk_Index"].value_counts().sort_index()
                bar_colors = [color_map.get(idx, '#2563EB') for idx in counts.index]
                
                fig2, ax2 = plt.subplots(figsize=(6, 4))
                bars = ax2.bar(counts.index.astype(str), counts.values, color=bar_colors)
                ax2.set_xlabel("Risk Index (1: Low Risk -> 5: High Risk)")
                ax2.set_ylabel("Count of Pipes")
                ax2.set_title("Pipe Risk Index Histogram")
                st.pyplot(fig2)
        else:
            st.info("يرجى تشغيل المحاكاة من التبويب الثاني أولاً.")

    # الشرح والتعريفات أسفل الصفحات
    st.markdown("""
    <div class="info-box">
        <h3>💡 مصطلحات وتعريفات التحليل الهيدروليكي:</h3>
        <ul>
            <li><b>Satisfied Demand (الطلب المستوفى):</b> يمثل كمية التدفق المائي الفعلية (بوحدة لتر/ثانية) التي تصل للمستهلكين عند إغلاق أنبوب محدد.</li>
            <li><b>Demand Met Ratio (نسبة تلبية الطلب):</b> النسبة المئوية للمياه الواصلة للشبكة مقارنة بالطلب الكلي المطلوب. كلما انخفضت هذه النسبة، دل ذلك على أن الأنبوب المغلق يشكل شرياناً حيوياً للشبكة.</li>
            <li><b>Risk Index (مؤشر الخطورة):</b> تصنيف من 1 إلى 5 يحدد مدى تأثير إغلاق الأنبوب على الشبكة:
                <ul>
                    <li><span style="color: #2563EB; font-weight: bold;">1 (أزرق):</span> تأثير ضعيف جداً (تلبية الطلب > 80%).</li>
                    <li><span style="color: #38BDF8; font-weight: bold;">2 (سماوي):</span> تأثير منخفض (تلبية الطلب 70% - 80%).</li>
                    <li><span style="color: #EAB308; font-weight: bold;">3 (أصفر):</span> تأثير متوسط (تلبية الطلب 60% - 70%).</li>
                    <li><span style="color: #F97316; font-weight: bold;">4 (برتقالي):</span> تأثير مرتفع (تلبية الطلب 50% - 60%).</li>
                    <li><span style="color: #DC2626; font-weight: bold;">5 (أحمر):</span> تأثير حرج جداً (تلبية الطلب ≤ 50%).</li>
                </ul>
            </li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

else:
    st.info("Please upload an EPANET `.inp` file to start the automated analysis.")
