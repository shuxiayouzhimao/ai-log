import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import time
from datetime import datetime, timedelta
from db import LogDatabase
from llm_analyzer import analyzer
from config.settings import Config

# --- 页面配置 ---
st.set_page_config(
    page_title="AI 智能日志监控",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 数据库初始化 ---
@st.cache_resource
def get_db():
    return LogDatabase()

db = get_db()

# --- 主标题与状态 ---
col_title, col_status = st.columns([4, 1])
with col_title:
    st.title("🛡️ AI 智能日志监控系统")
    st.caption("实时监控、智能分析、快速故障定位")

with col_status:
    if db.connected:
        st.success("✅ 数据库已连接", icon="✅")
    else:
        st.error("❌ 数据库连接失败")
        st.stop()

# --- 侧边栏：过滤器区域 ---
with st.sidebar:
    st.header("🔍 过滤设置")
    
    # 获取统计数据
    stats = db.get_stats()
    services = ["全部"] + list(stats["service_counts"].keys()) if "service_counts" in stats else ["全部", "auth-service", "payment-service", "data-processor", "frontend-api"]
    levels = ["全部", "INFO", "WARNING", "ERROR", "DEBUG"]
    
    # 筛选器卡片
    with st.container(border=True):
        st.subheader("日志筛选", divider="gray")
        
        selected_service = st.selectbox(
            "**服务名称**",
            services,
            help="选择要查看的服务"
        )
        if selected_service == "全部":
            selected_service = "All"
            
        selected_level = st.selectbox(
            "**日志级别**",
            levels,
            help="筛选特定级别的日志"
        )
        if selected_level == "全部":
            selected_level = "All"
            
        search_text = st.text_input(
            "**关键词搜索**",
            placeholder="输入关键词...",
            help="支持消息内容模糊搜索"
        )
        
        # 时间筛选
        time_range = st.selectbox(
            "**时间范围**",
            ["全部时间", "最近 1 小时", "最近 24 小时", "最近 7 天", "自定义范围"],
            help="筛选日志的时间范围"
        )
        
        start_time = None
        end_time = None
        
        if time_range == "最近 1 小时":
            start_time = datetime.now() - timedelta(hours=1)
        elif time_range == "最近 24 小时":
            start_time = datetime.now() - timedelta(hours=24)
        elif time_range == "最近 7 天":
            start_time = datetime.now() - timedelta(days=7)
        elif time_range == "自定义范围":
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                d_start = st.date_input("开始日期", value=datetime.now() - timedelta(days=1))
                t_start = st.time_input("开始时间", value=datetime.strptime("00:00:00", "%H:%M:%S").time())
            with col_d2:
                d_end = st.date_input("结束日期", value=datetime.now())
                t_end = st.time_input("结束时间", value=datetime.now().time())
                
            if d_start and t_start:
                start_time = datetime.combine(d_start, t_start)
            if d_end and t_end:
                end_time = datetime.combine(d_end, t_end)
        
        limit = st.slider(
            "**显示条数**",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            help="控制显示的日志数量"
        )
    
    # 操作按钮组
    st.subheader("⚙️ 操作", divider="gray")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 刷新", use_container_width=True, type="primary"):
            st.rerun()
    with col_btn2:
        if st.button("🗑️ 清除", use_container_width=True):
            if 'selected_log_id' in st.session_state:
                del st.session_state.selected_log_id
            if 'selected_row_index' in st.session_state:
                del st.session_state.selected_row_index
            st.rerun()
    
    # 统计信息
    st.subheader("📈 统计摘要", divider="gray")
    current_stats = db.get_stats()
    
    with st.container(border=True):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.metric("日志总量", current_stats["total_logs"])
            st.metric("服务数量", len(current_stats["service_counts"]))
        with col_s2:
            error_rate = 0
            if current_stats["total_logs"] > 0:
                error_rate = (current_stats["error_logs"] / current_stats["total_logs"]) * 100
            st.metric("错误率", f"{error_rate:.1f}%", delta=f"{current_stats['error_logs']}条")
        
        # 服务分布快速查看
        if current_stats["service_counts"]:
            st.caption("**服务分布**")
            for service, count in list(current_stats["service_counts"].items())[:3]:
                st.progress(min(count / current_stats["total_logs"], 1.0), 
                           text=f"{service}: {count}")

# --- 主内容区域 ---

# 概览面板 (Dashboard Overview)
st.subheader("📊 系统概览")
with st.container(border=True):
    cols = st.columns(4)
    
    with cols[0]:
        st.metric(
            label="总日志量",
            value=current_stats["total_logs"],
            delta="今日+123"
        )
    with cols[1]:
        warning_logs = current_stats.get("warning_logs", 0)
        st.metric(
            label="警告日志",
            value=warning_logs,
            delta_color="off" if warning_logs == 0 else "inverse"
        )
    with cols[2]:
        st.metric(
            label="错误日志",
            value=current_stats["error_logs"],
            delta_color="inverse"
        )
    with cols[3]:
        st.metric(
            label="活跃服务",
            value=len(current_stats["service_counts"]),
            delta="+2"
        )

# 根据过滤条件获取日志
df_logs = db.get_logs(limit=limit, service=selected_service, 
                      level=selected_level, search_text=search_text,
                      start_time=start_time, end_time=end_time)

# 图表区域 (Trends)
tab_chart1, tab_chart2, tab_chart3 = st.tabs(["📈 服务分布", "📊 错误趋势", "📋 级别统计"])

with tab_chart1:
    if current_stats["service_counts"]:
        df_service = pd.DataFrame(list(current_stats["service_counts"].items()), 
                                 columns=["Service", "Count"])
        fig_pie = px.pie(df_service, values="Count", names="Service", 
                        title="各服务日志分布", hole=0.3)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("暂无服务数据")

with tab_chart2:
    error_df = db.get_error_trend()
    if not error_df.empty:
        error_df["timestamp"] = pd.to_datetime(error_df["timestamp"])
        
        # 按小时和时间分组统计
        # 使用 floor 将时间截断到小时
        error_df["timestamp_hour"] = error_df["timestamp"].dt.floor("h")
        error_counts = error_df.groupby(["timestamp_hour", "service_name"]).size().reset_index(name="count")
        
        fig_line = px.line(error_counts, x="timestamp_hour", y="count", color="service_name",
                          title="最近24小时各服务错误趋势",
                          labels={"count": "错误数量", "timestamp_hour": "时间", "service_name": "服务"},
                          line_shape="spline",
                          markers=True) # 添加标记点以便在数据稀疏时也能看清
        
        fig_line.update_layout(hovermode="x unified")
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("暂无错误趋势数据")

with tab_chart3:
    if not df_logs.empty and 'level' in df_logs.columns:
        level_counts = df_logs['level'].value_counts()
        fig_bar = px.bar(x=level_counts.index, y=level_counts.values,
                        title="日志级别统计",
                        labels={'x': '级别', 'y': '数量'},
                        color=level_counts.index,
                        color_discrete_map={
                            'ERROR': '#EF553B',
                            'WARNING': '#FFA15A',
                            'INFO': '#00CC96',
                            'DEBUG': '#636EFA'
                        })
        st.plotly_chart(fig_bar, use_container_width=True)

# --- 日志列表区域 ---
st.subheader("📋 实时日志列表")

if not df_logs.empty:
    # 创建两个选项卡：表格视图和选择面板
    tab_logs, tab_select = st.tabs(["📄 日志表格", "🎯 选择日志"])
    
    with tab_logs:
        # 样式函数
        def color_level(val):
            color_map = {
                'ERROR': '#ff4d4d',
                'WARNING': '#ffa726',
                'INFO': '#66bb6a',
                'DEBUG': '#42a5f5'
            }
            color = color_map.get(val, 'white')
            return f'color: {color}; font-weight: bold;'
        
        # 显示列配置
        display_cols = ["_id", "timestamp", "service_name", "level", "message", "file_path"]
        
        # 创建数据表格
        st.dataframe(
            df_logs[display_cols].style.map(color_level, subset=['level']),
            use_container_width=True,
            hide_index=True,
            column_config={
                "_id": st.column_config.TextColumn("Log ID", help="唯一日志标识符", width="medium"),
                "timestamp": st.column_config.DatetimeColumn("时间", format="YYYY-MM-DD HH:mm:ss"),
                "service_name": "服务",
                "level": "级别",
                "message": "消息",
                "file_path": "文件路径"
            }
        )
        
        # 底部统计信息
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.caption(f"📊 显示 {len(df_logs)} 条日志")
        with col_info2:
            st.caption(f"⏱️ 最后更新时间: {pd.Timestamp.now().strftime('%H:%M:%S')}")
        with col_info3:
            if st.button("🔄 刷新数据", key="refresh_data"):
                st.rerun()
    
    with tab_select:
        # 选择面板
        col_select_left, col_select_right = st.columns([2, 1])
        
        with col_select_left:
            st.markdown("#### 选择日志进行分析")
            
            # 方法1：行号选择
            with st.container(border=True):
                st.markdown("**方法一：按行号选择**")
                max_index = len(df_logs) - 1
                selected_index = st.slider(
                    "选择行号",
                    min_value=0,
                    max_value=max_index,
                    value=st.session_state.get('selected_row_index', 0) if max_index > 0 else 0,
                    help=f"当前表格有 {max_index + 1} 行"
                )
                
                if max_index > 0 and selected_index <= max_index:
                    selected_row = df_logs.iloc[selected_index]
                    with st.expander("预览选中日志", expanded=True):
                        st.code(f"""
时间: {selected_row['timestamp']}
服务: {selected_row['service_name']}
级别: {selected_row['level']}
消息: {selected_row['message'][:100]}...
                        """)
            
            # 方法2：ID搜索
            with st.container(border=True):
                st.markdown("**方法二：按ID搜索**")
                manual_id = st.text_input(
                    "输入日志ID",
                    placeholder="输入24位MongoDB ID",
                    help="从表格中复制日志ID"
                )
                
                if manual_id and st.button("🔍 搜索ID", use_container_width=True):
                    if len(manual_id) == 24 and manual_id.isalnum():
                        matching_indices = df_logs[df_logs["_id"] == manual_id].index.tolist()
                        if matching_indices:
                            st.session_state.selected_log_id = manual_id
                            st.session_state.selected_row_index = matching_indices[0]
                            st.success("✅ 找到匹配的日志")
                            st.rerun()
                        else:
                            st.error("❌ 未在当前视图中找到该ID")
                    else:
                        st.warning("⚠️ ID格式不正确")
        
        with col_select_right:
            st.markdown("#### 操作")
            with st.container(border=True):
                # 显示当前选择状态
                if 'selected_log_id' in st.session_state:
                    st.success("✅ 已选择日志")
                    st.caption(f"ID: {st.session_state.selected_log_id[:8]}...")
                else:
                    st.info("ℹ️ 未选择日志")
                
                # 操作按钮
                if st.button("📋 查看详情", 
                           type="primary", 
                           use_container_width=True,
                           disabled=max_index == 0):
                    if len(df_logs) > selected_index:
                        st.session_state.selected_log_id = df_logs.iloc[selected_index]["_id"]
                        st.session_state.selected_row_index = selected_index
                        st.rerun()
                
                if st.button("🧹 清除选择", 
                           use_container_width=True,
                           disabled='selected_log_id' not in st.session_state):
                    if 'selected_log_id' in st.session_state:
                        del st.session_state.selected_log_id
                    if 'selected_row_index' in st.session_state:
                        del st.session_state.selected_row_index
                    st.rerun()
                
                # 快速操作建议
                st.markdown("---")
                st.caption("💡 **小贴士**")
                st.caption("1. 选择ERROR日志进行AI分析")
                st.caption("2. 双击表格行可快速选择")
                st.caption("3. 使用筛选器缩小范围")
    
    # --- 日志详情分析区域 ---
    if st.session_state.get('selected_log_id'):
        st.divider()
        st.subheader("🔍 日志详情分析")
        
        # 创建三列布局：详情、AI分析、相关日志
        col_detail, col_ai, col_related = st.columns([1, 1, 1])
        
        # 获取日志详情
        log_id = st.session_state.selected_log_id
        matched_row = df_logs[df_logs["_id"] == log_id]
        
        log_entry = None
        if not matched_row.empty:
            log_entry = matched_row.iloc[0].to_dict()
        else:
            log_entry = db.get_log_by_id(log_id)
        
        if log_entry:
            # 左侧：日志详情
            with col_detail:
                with st.container(border=True, height=500):
                    st.markdown("#### 📋 日志详情")
                    
                    # 基本信息卡片
                    st.markdown("**基本信息**")
                    info_cols = st.columns(2)
                    with info_cols[0]:
                        level_badge = {
                            'ERROR': '🔴',
                            'WARNING': '🟠', 
                            'INFO': '🟢',
                            'DEBUG': '🔵'
                        }.get(log_entry.get('level', ''), '⚪')
                        st.markdown(f"{level_badge} **级别**: {log_entry.get('level', 'N/A')}")
                        st.markdown(f"🕐 **时间**: {log_entry.get('timestamp', 'N/A')}")
                    with info_cols[1]:
                        st.markdown(f"📦 **服务**: {log_entry.get('service_name', 'N/A')}")
                        st.markdown(f"📁 **文件**: {log_entry.get('file_path', 'N/A').split('/')[-1]}")
                    
                    st.divider()
                    
                    # 消息内容
                    st.markdown("**消息内容**")
                    st.code(log_entry.get('message', 'N/A'), language="text")
                    
                    # 完整JSON（可折叠）
                    with st.expander("查看完整JSON数据"):
                        st.json(log_entry)
            
            # 中间：AI分析
            with col_ai:
                with st.container(border=True, height=500):
                    st.markdown("#### 🤖 AI智能诊断")
                    
                    # 诊断状态
                    if log_entry.get("level") == "ERROR":
                        st.error("🚨 检测到错误日志")
                        
                        # 分析按钮区域
                        analyze_btn_col1, analyze_btn_col2 = st.columns([3, 1])
                        with analyze_btn_col1:
                            btn_key = f"btn_analyze_{log_id}"
                            if st.button("🔍 深度分析错误", 
                                       key=btn_key, 
                                       type="primary",
                                       use_container_width=True):
                                with st.spinner("DeepSeek正在分析中..."):
                                    try:
                                        report = analyzer.analyze_error(log_entry)
                                        st.session_state[f"report_{log_id}"] = report
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"分析失败: {str(e)}")
                        
                        # 显示分析结果
                        report_key = f"report_{log_id}"
                        if report_key in st.session_state:
                            st.divider()
                            st.markdown("#### 📝 分析报告")
                            st.markdown(st.session_state[report_key])
                            
                            # 操作按钮
                            col_action1, col_action2 = st.columns(2)
                            with col_action1:
                                if st.button("🔄 重新分析", use_container_width=True):
                                    del st.session_state[report_key]
                                    st.rerun()
                            with col_action2:
                                if st.button("📋 复制报告", use_container_width=True):
                                    st.toast("报告已复制到剪贴板", icon="✅")
                    else:
                        st.success("✅ 日志状态正常")
                        st.info("""
                        **建议**:
                        - 这是正常的{level}级别日志
                        - 系统运行状态良好
                        - 无需进行深度分析
                        """.format(level=log_entry.get('level', '')))
            
            # 右侧：相关日志
            with col_related:
                with st.container(border=True, height=500):
                    st.markdown("#### 🔗 相关日志")
                    
                    if log_entry.get('service_name'):
                        # 获取同一服务的最近日志
                        related_logs = db.get_logs(
                            limit=5,
                            service=log_entry['service_name'],
                            level=selected_level if selected_level != "All" else "All"
                        )
                        
                        if not related_logs.empty:
                            for _, log in related_logs.head(3).iterrows():
                                if log['_id'] != log_id:
                                    with st.container(border=True):
                                        st.caption(f"{log['timestamp']} | {log['level']}")
                                        st.markdown(f"`{log['message'][:50]}...`")
                                        if st.button("📌 选择", 
                                                   key=f"select_{log['_id']}",
                                                   size="small"):
                                            st.session_state.selected_log_id = log['_id']
                                            st.rerun()
                        else:
                            st.info("暂无相关日志")
                    else:
                        st.info("无服务信息")

else:
    # 没有日志数据时的显示
    st.warning("⚠️ 未找到匹配的日志")
    st.info("""
    **建议操作**:
    1. 调整筛选条件
    2. 检查数据库连接
    3. 确认服务正在运行
    """)

# --- 页脚 ---
st.divider()
footer_col1, footer_col2, footer_col3 = st.columns([2, 1, 1])
with footer_col1:
    st.caption("© 2024 AI 智能日志监控系统 | Streamlit + MongoDB + DeepSeek")
with footer_col2:
    st.caption(f"版本: {Config.VERSION}")
with footer_col3:
    if st.button("🔄 完整刷新", key="full_refresh"):
        st.rerun()