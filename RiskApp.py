with tab2:
            st.subheader("Simulate Pipe Failures (Sequential Closure)")
            st.write("Calculates exact hydraulic availability by closing each pipe sequentially in EPANET.")
            
            if st.button("🚀 Run Exact Pipe Failure Analysis"):
                results = []
                progress_bar = st.progress(0)
                total_pipes = len(pipes_list)
                
                # استخدام Graph للتحقق من الاتصال التوبولوجي بالخزان
                G = wn.to_graph().to_undirected()
                source_nodes = set(wn.reservoir_name_list + wn.tank_name_list)

                for idx, pipe_name in enumerate(pipes_list):
                    # 1. فحص الاتصال بالخزان أولاً (Topology Check)
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
                    
                    # 2. إذا تسبب إغلاق الأنبوب في عزل الشبكة تماماً عن الخزان
                    if len(connected_to_source) <= len(source_nodes):
                        satisfied_demand = 0.0
                    else:
                        # تشغيل المحاكاة مع إغلاق الأنبوب حقيقياً
                        wn_sim = wntr.network.WaterNetworkModel(tmp_path)
                        pipe_to_close = wn_sim.get_link(pipe_name)
                        pipe_to_close.status = wntr.network.LinkStatus.Closed
                        
                        try:
                            sim = wntr.sim.EpanetSimulator(wn_sim)
                            results_sim = sim.run_sim()
                            
                            # حساب الاستهلاك الفعلي المقبول من العقد المتصلة ذات الضغط الموجب
                            demand_results = results_sim.node['demand']
                            pressure_results = results_sim.node['pressure']
                            
                            # أخذ آخر خطوة زمنية في المحاكاة
                            last_time = demand_results.index[-1]
                            satisfied_demand = 0.0
                            
                            for j_name, j in wn.junctions():
                                if j_name in connected_to_source:
                                    p_val = pressure_results.loc[last_time, j_name]
                                    d_val = demand_results.loc[last_time, j_name]
                                    if p_val >= 0 and d_val > 0:
                                        satisfied_demand += d_val
                        except Exception:
                            # في حال حدوث خطأ هيدروليكي بسبب الفصل الكامل
                            satisfied_demand = 0.0

                    ratio = (satisfied_demand / base_total_demand * 100) if base_total_demand > 0 else 0.0
                    risk = map_serviceability_to_risk(ratio)
                    
                    results.append({
                        "Closed_Pipe": pipe_name,
                        "Satisfied_Demand": round(float(satisfied_demand), 2),
                        "Demand_Met_Ratio": round(float(ratio), 2),
                        "Risk_Index": risk
                    })
                    
                    progress_bar.progress((idx + 1) / total_pipes)
                    
                df_results = pd.DataFrame(results)
                st.session_state["df_results"] = df_results
                st.success("Exact EPANET Closure Simulation Completed!")
                st.dataframe(df_results, use_container_width=True)
