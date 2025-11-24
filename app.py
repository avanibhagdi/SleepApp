import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta
import json
import os
import streamlit.runtime.scriptrunner as st_scriptrunner 

# --- 1. CONFIGURATION, IMPORTS, AND PAGE SETUP (MUST BE FIRST) ---

# Set the page configuration as the first Streamlit command
st.set_page_config(
    layout="wide",
    page_title="Feasleeple",
    initial_sidebar_state="collapsed", 
)

# Constants
MAX_WORK_CAPACITY = 13.0
DAY_OPTIONS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# Custom Color Palette
PALETTE = ['#4DB6AC', '#9575CD', '#B0BEC5', '#FF8A65',
           '#4DD0E1', '#9FA8DA', '#B39DDB', '#FFAB91',
           '#80CBC4', '#A1887F', '#B3E5FC', '#FFCDD2',
           '#81C784', '#A5D6A7', '#C5E1A5', '#FFD54F',
           '#90CAF9', '#AED581', '#DCE775', '#FFECB3']


# --- 2. UTILITY AND PERSISTENCE FUNCTIONS ---

def get_user_file_path():
    """
    Returns a FIXED file path for reliable local, single-user persistence.
    """
    home_dir = os.path.expanduser("~") 
    DATA_SUBDIR = os.path.join(home_dir, ".feasleeplity_data") 
    os.makedirs(DATA_SUBDIR, exist_ok=True) 

    # FIXED FILENAME
    return os.path.join(DATA_SUBDIR, "tasks_master.json")

# --- CRITICAL FIX: Use st.cache_resource for reliable loading on rerun ---
@st.cache_resource(ttl=3600) 
def load_tasks():
    """Loads tasks from a FIXED file path reliably."""
    file_path = get_user_file_path()
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                # Convert ISO string dates back to date objects
                for task in data:
                    task['start'] = date.fromisoformat(task['start'])
                    task['end'] = date.fromisoformat(task['end'])
                return data
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return []
    return []

def save_tasks():
    """Saves tasks from session state and clears the cache."""
    file_path = get_user_file_path()
    data_to_save = []
    # Convert date objects to ISO format strings for JSON serialization
    for task in st.session_state.tasks:
        task_copy = task.copy()
        task_copy['start'] = task_copy['start'].isoformat()
        task_copy['end'] = task_copy['end'].isoformat()
        data_to_save.append(task_copy)
    
    # Write to file
    with open(file_path, 'w') as f:
        json.dump(data_to_save, f, indent=4)
        
    # --- CRITICAL FIX: Clear the cached version to force reload on next rerun/refresh ---
    load_tasks.clear()

# --- CALLBACK FUNCTIONS FOR PERSISTENCE ---

# NOTE: add_task_callback is DELETED/removed. Its logic is moved to the form submit block.

def delete_task(index):
    """Callback triggered on 'Delete' button click."""
    del st.session_state.tasks[index]
    save_tasks() 
    st.session_state.audit_ran = False
    st.session_state.edit_index = None
    st.toast("Task deleted and saved.")

def clear_tasks_callback():
    """Callback triggered on 'Clear ALL Tasks' button click."""
    st.session_state.tasks = []
    save_tasks() 
    st.session_state.audit_ran = False
    st.toast("All tasks cleared and saved.")

def save_edit_callback(task_index_to_edit, new_name, new_time, new_days, new_dates):
    """Callback triggered on 'Save Changes' submit."""
    if len(new_dates) == 2:
        new_start_date = new_dates[0]
        new_end_date = new_dates[1]
    else:
        new_start_date = new_dates[0]
        new_end_date = new_dates[0]

    if new_start_date > new_end_date:
        st.error("Save Failed: Start date cannot be after the end date.")
        return 

    st.session_state.tasks[task_index_to_edit].update({
        "name": new_name,
        "time": new_time,
        "days": new_days,
        "start": new_start_date,
        "end": new_end_date
    })
    save_tasks()
    st.session_state.edit_index = None # Close the form
    st.toast(f"Task '{new_name}' updated and saved!")


# --- REMAINING UTILITY FUNCTIONS (Unchanged) ---

def calculate_total_scheduled_hours(tasks_list):
    total_hours = 0
    for task in tasks_list:
        start_date = pd.to_datetime(task['start'])
        end_date = pd.to_datetime(task['end'])
        task_time = task['time']
        task_days = task['days']
        
        days_per_week = len(task_days)
        total_days_in_range = (end_date - start_date).days + 1
        full_weeks = total_days_in_range // 7
        remaining_days = total_days_in_range % 7
        
        task_load = full_weeks * days_per_week * task_time
        
        if remaining_days > 0:
            current_date = start_date
            for _ in range(remaining_days):
                if current_date.strftime('%A') in task_days:
                    task_load += task_time
                current_date += timedelta(days=1)

        total_hours += task_load
    return total_hours

def format_ordinal_date(date_index):
    """Converts a Pandas Timestamp to the '1st December 2025' format."""
    if pd.isna(date_index): return "Date N/A"
    date_obj = date_index.to_pydatetime().date()
    day = date_obj.day
    month_name = date_obj.strftime('%B')
    year = date_obj.year
    if 11 <= day <= 13: suffix = 'th'
    else: suffixes = {1: 'st', 2: 'nd', 3: 'rd'}; suffix = suffixes.get(day % 10, 'th')
    return f"{day}{suffix} {month_name} {year}"

def format_hours_minutes(decimal_hours):
    """Converts a decimal hour value (e.g., 1.5) to '1 hour 30 minutes'."""
    if decimal_hours <= 0: return "0 minutes"
    hours = int(decimal_hours)
    minutes = round((decimal_hours - hours) * 60)
    parts = []
    if hours > 0: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return " ".join(parts) or "0 minutes"

# --- 3. SESSION STATE INITIALIZATION (Execution Order) ---

# CRITICAL: load_tasks is now a cached function, which is fine to call here.
if 'tasks' not in st.session_state:
    st.session_state.tasks = load_tasks() 
if 'audit_ran' not in st.session_state:
    st.session_state.audit_ran = False
if 'audit_df' not in st.session_state:
    st.session_state.audit_df = pd.DataFrame()
if 'viz_df' not in st.session_state:
    st.session_state.viz_df = pd.DataFrame()
if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None
if 'audit_start' not in st.session_state:
    st.session_state.audit_start = date.today()
if 'audit_end' not in st.session_state:
    st.session_state.audit_end = date.today() + timedelta(weeks=8)


# ==============================================================================
# 📌 Core Logic Function
# ==============================================================================

def run_audit(audit_start, audit_end):
    # 1. Generate Audit Range and Initialize DataFrame
    date_range = pd.date_range(start=audit_start, end=audit_end, freq='D')
    audit_df = pd.DataFrame(index=date_range)
    audit_df.index.name = 'Date'
    audit_df['DayOfWeek'] = audit_df.index.day_name()
    audit_df['Max_Capacity'] = MAX_WORK_CAPACITY
    audit_df['Task_Load'] = 0.0
    
    # 2. Calculate Task Load
    for task in st.session_state.tasks:
        task_time = task['time']
        task_days = task['days']
        
        relevant_dates = audit_df.loc[
            (audit_df.index.date >= task['start']) & 
            (audit_df.index.date <= task['end']) & 
            (audit_df['DayOfWeek'].isin(task_days))
        ]
        
        audit_df.loc[relevant_dates.index, 'Task_Load'] += task_time
        
    # 3. Audit & Set Flag
    audit_df['Overload_Hours'] = audit_df['Task_Load'] - audit_df['Max_Capacity']
    audit_df['Overload_Flag'] = audit_df['Overload_Hours'].apply(lambda x: 'Overload Day' if x > 0 else 'OK')
    
    # 4. Prepare Data for Visualization
    viz_data = [] 
    
    for date_ts, row in audit_df.iterrows():
        day_str = row['DayOfWeek']
        
        viz_data.append({
            'Date': date_ts,
            'Hours': row['Max_Capacity'],
            'Type': 'Max Capacity',
            'Task_Name': 'Max Capacity'
        })
        
        for task in st.session_state.tasks:
            if day_str in task['days'] and task['start'] <= date_ts.date() <= task['end']: 
                viz_data.append({
                    'Date': date_ts,
                    'Hours': task['time'],
                    'Type': 'Task Load',
                    'Task_Name': task['name']
                })

    st.session_state.viz_df = pd.DataFrame(viz_data)
    st.session_state.viz_df['Date'] = pd.to_datetime(st.session_state.viz_df['Date'])
    
    return audit_df

# ==============================================================================
# 📌 STREAMLIT LAYOUT
# ==============================================================================

st.title("😴 Feasleeple")
st.markdown(f"Maximum daily capacity enforced: **{MAX_WORK_CAPACITY} hours**.")
st.markdown("---")

st.info("""
**How to Use Feasleeple**

This tool helps you check your schedule's **feasibility** against a strict **13-hour maximum daily work capacity** (ensuring a 9-hour minimum sleep + 2-hour buffer).
""")

col1, col2, col3 = st.columns([0.8, 0.7, 1.5])

# ==============================================================================
# 📌 PANEL 1: Task Input
# ==============================================================================
with col1:
    st.header("1. Unit Task Time")
    
    with st.form("task_form", clear_on_submit=True):
        task_name = st.text_input("Task Name (e.g., Work, Commute, Hobby)")
        
        task_unit_time = st.number_input(
            "Unit Task Time (Hours)", 
            min_value=0.1, max_value=MAX_WORK_CAPACITY, value=2.0, step=0.5,
            help="Enter time as a decimal (e.g., 1.5 for 1 hour 30 minutes)."
        )
        
        task_days = st.multiselect(
            "Which days of the week?", 
            options=DAY_OPTIONS, default=["Monday", "Tuesday"]
        )
        
        # --- Single-Day / Range Logic (Stable) ---
        st.markdown("##### Schedule Frequency")

        is_one_time = st.checkbox("This is a one-time event (single day)")

        if is_one_time:
            single_date = st.date_input("Select Event Date", value=date.today(), key='single_date_picker')
            task_start_date = single_date
            task_end_date = single_date
            
        else:
            task_dates = st.date_input(
                "Start and End Date Range (Inclusive)",
                [date.today(), date.today() + timedelta(weeks=4)],
                key='range_picker'
            )
            # Safely unpack the list to prevent ValueError on startup
            if len(task_dates) == 2:
                task_start_date = task_dates[0]
                task_end_date = task_dates[1]
            else:
                task_start_date = task_dates[0]
                task_end_date = task_dates[0]

        # --- CRITICAL FIX: Move logic back into the standard form submit block ---
        if st.form_submit_button("Add Task"):
            is_valid = True
            if not task_name:
                st.error("Task Name is required.")
                is_valid = False
            if not task_days:
                st.error("At least one Day is required.")
                is_valid = False

            if is_valid:
                st.session_state.tasks.append({
                    "name": task_name, "time": task_unit_time, "days": task_days,
                    "start": task_start_date, "end": task_end_date      
                })
                save_tasks() # Ensure persistence!
                st.session_state.audit_ran = False
                st.success(f"Task '{task_name}' ({task_unit_time}h) added and saved.")
    
    # Display Total Scheduled Hours
    total_scheduled_hours = calculate_total_scheduled_hours(st.session_state.tasks)
    
    st.markdown("---")
    st.caption(f"**Total Tasks Loaded:** {len(st.session_state.tasks)}")
    st.caption(f"**Total Scheduled Hours (All Tasks):** {total_scheduled_hours:.1f} hours")

# ==============================================================================
# 📌 PANEL 2: Time Slicing and Audit Trigger
# ==============================================================================
with col2:
    st.header("2. Audit Period")
    
    audit_dates = st.date_input(
        "Select Range for Burnout Check",
        value=(st.session_state.audit_start, st.session_state.audit_end), 
        min_value=date(2000, 1, 1), 
        help="The audit will check all days from the start date through the end date (inclusive)."
    )

    if len(audit_dates) == 2:
        audit_start = audit_dates[0]
        audit_end = audit_dates[1]
        st.session_state.audit_start = audit_start
        st.session_state.audit_end = audit_end
    else:
        audit_start = st.session_state.audit_start
        audit_end = st.session_state.audit_end
        
    st.markdown("---")
    
    # Audit Trigger 
    if st.button("▶️ Run Daily Audit", type="primary"):
        if not st.session_state.tasks:
             st.warning("Please add at least one task to run the audit.")
        elif audit_start > audit_end:
             st.error("Audit start date cannot be after the end date.")
        else:
            audit_df = run_audit(audit_start, audit_end)
            st.session_state.audit_df = audit_df 
            st.session_state.audit_ran = True 
            
            # Audit Summary Statistics
            if not audit_df.empty:
                active_days_df = audit_df[audit_df['Task_Load'] > 0.0]
                total_hours_in_range = active_days_df['Task_Load'].sum()
                total_active_days = len(active_days_df)
                
                if total_active_days > 0:
                    average_daily_load = total_hours_in_range / total_active_days
                else:
                    average_daily_load = 0.0
                
                st.session_state.total_audited_hours = total_hours_in_range
                st.session_state.total_active_days = total_active_days
                st.session_state.avg_daily_load = average_daily_load

            st.success("Audit executed successfully.")

    # Display Red/Green Card
    st.subheader("Overall Feasibility")
    if st.session_state.audit_ran:
        overload_count = (st.session_state.audit_df['Overload_Flag'] == 'Overload Day').sum()
        
        if overload_count > 0:
            st.error(f"⚠️ You have **{overload_count} overloaded days**!")
        else:
            st.success("✅ No overload days!")
    else:
        st.info("Run the audit to see feasibility results.")
        
    # Display Audit Statistics
    st.markdown("---")
    st.subheader("Audit Summary")
    if st.session_state.audit_ran and 'total_audited_hours' in st.session_state:
        st.markdown(f"**Total Audited Hours:** {st.session_state.total_audited_hours:.1f} hours")
        st.markdown(f"**Total Active Work Days:** {st.session_state.total_active_days} days") 
        st.markdown(f"**Average Daily Load:** {st.session_state.avg_daily_load:.1f} hours/day")
    else:
        st.info("Run audit to see summary statistics.")

# ==============================================================================
# 📌 PANEL 3: Results and Task Management
# ==============================================================================
with col3:
    st.header("3. Audit Results")

    # --- 1. Current Tasks List (with Edit/Delete Buttons) ---
    st.subheader("Current Tasks")
    
    task_index_to_edit = st.session_state.edit_index 
    
    if st.session_state.tasks:
        st.caption("Click the trash icon to delete a single task.")
        
        # Header Row
        col_name, col_time, col_days, col_start, col_end, col_edit, col_delete = st.columns([1.5, 0.5, 1.0, 1.0, 1.0, 0.5, 0.5])
        with col_name: st.markdown("**Task**")
        with col_time: st.markdown("**Hrs**")
        with col_days: st.markdown("**Days**")
        with col_start: st.markdown("**Start**")
        with col_end: st.markdown("**End**")

        st.markdown("---") 

        for i, task in enumerate(st.session_state.tasks):
            col_name_i, col_time_i, col_days_i, col_start_i, col_end_i, col_edit_i, col_delete_i = st.columns([1.5, 0.5, 1.0, 1.0, 1.0, 0.5, 0.5])

            with col_name_i: st.markdown(f"**{task['name']}**")
            with col_time_i: st.markdown(f"{task['time']}h")
            with col_days_i: st.markdown(f"<span style='font-size: smaller;'>{', '.join(task['days'])}</span>", unsafe_allow_html=True)
            with col_start_i: st.markdown(f"<span style='font-size: smaller;'>{task['start']}</span>", unsafe_allow_html=True)
            with col_end_i: st.markdown(f"<span style='font-size: smaller;'>{task['end']}</span>", unsafe_allow_html=True)
            
            with col_edit_i:
                st.button("✏️", key=f"edit_{i}", on_click=lambda i=i: st.session_state.update(edit_index=i)) 
                
            # Delete button uses the callback for persistence
            with col_delete_i:
                st.button("🗑️", key=f"delete_{i}", on_click=delete_task, args=(i,))

        st.markdown("---")
        
        # Clear All button uses the callback for persistence
        st.button("Clear ALL Tasks", key="clear_tasks", on_click=clear_tasks_callback)
            
    else:
        st.info("No tasks added yet.")
        
    st.markdown("---")

    # ==============================================================================
    # 2. CONDITIONAL EDIT FORM (Appears when edit_index is set)
    # ==============================================================================
    if task_index_to_edit is not None and task_index_to_edit < len(st.session_state.tasks):
        task_to_edit = st.session_state.tasks[task_index_to_edit]
        
        st.subheader(f"✏️ Editing: {task_to_edit['name']}")

        with st.form("edit_task_form", clear_on_submit=False):
            
            # Pre-fill inputs with current task data
            new_name = st.text_input("Task Name", value=task_to_edit['name'], key='e_name')
            new_time = st.number_input("Unit Task Time (Hours)", value=task_to_edit['time'], min_value=0.1, max_value=MAX_WORK_CAPACITY, step=0.5, key='e_time')
            new_days = st.multiselect("Which days of the week?", options=DAY_OPTIONS, default=task_to_edit['days'], key='e_days')
            new_dates = st.date_input(
            "New Start and End Date Range (Inclusive)",
            value=[task_to_edit['start'], task_to_edit['end']],
            key='e_dates')

            col_save, col_cancel = st.columns([1, 1])
            
            # Save button uses callback to trigger persistence
            with col_save:
                if st.form_submit_button("Save Changes", 
                                         on_click=save_edit_callback, 
                                         args=(task_index_to_edit, new_name, new_time, new_days, new_dates)):
                    pass # Logic moved to callback
            
            with col_cancel:
                # Cancel button still closes the form
                if st.form_submit_button("Cancel"):
                    st.session_state.edit_index = None 

    # --- 3. Overloaded Days List ---
    st.subheader("Overloaded Days")
    if st.session_state.audit_ran and not st.session_state.audit_df.empty:
        overloaded_days_df = st.session_state.audit_df[st.session_state.audit_df['Overload_Flag'] == 'Overload Day'].copy()

        if not overloaded_days_df.empty:
            overloaded_days_df['Overload'] = overloaded_days_df['Overload_Hours'].apply(format_hours_minutes)
            
            output_list_markdown = []
            for date_index, row in overloaded_days_df.iterrows():
                date_str = format_ordinal_date(date_index)
                output_list_markdown.append(
                    f"* **{date_str}**: Overloaded by **{row['Overload']}**") 
            st.markdown("\n\n".join(output_list_markdown))
        else:
            st.success("No overloaded days found in the audit range!")
    elif st.session_state.audit_ran and st.session_state.audit_df.empty:
        st.warning("Audit range was empty (no days selected).")
    else:
        st.info("Run the audit to list specific overloaded days.")

# ==============================================================================
# 📌 Daily Load Visualization
# ==============================================================================
st.markdown("---")
st.subheader("Daily Load Visualization")

if st.session_state.audit_ran and not st.session_state.viz_df.empty:
    viz_df = st.session_state.viz_df
    
    chart_start = st.session_state.audit_start
    chart_end = st.session_state.audit_end

    base = alt.Chart(viz_df).encode(
        x=alt.X('Date:T', title='Date', 
                scale=alt.Scale(domain=[chart_start, chart_end])),
        tooltip=[alt.Tooltip('Date:T', title='Date'), 
                 alt.Tooltip('Task_Name', title='Task'),
                 alt.Tooltip('Hours', title='Load (h)', format='.1f')]
    )
    
    bars = base.transform_filter(
        alt.datum.Type == 'Task Load'
    ).mark_bar().encode(
        y=alt.Y('Hours:Q', aggregate='sum', title='Hours Scheduled'),
        color=alt.Color('Task_Name:N', title='Task', scale=alt.Scale(range=PALETTE))
    )
    
    rule_chart = alt.Chart(pd.DataFrame({'y': [MAX_WORK_CAPACITY]})).mark_rule(
        color='red', 
        strokeWidth=2.5, 
        opacity=0.9
    ).encode(
        y='y',
        size=alt.value(2)
    )

    chart = (rule_chart + bars).properties(
        title=f'Daily Task Load vs. {MAX_WORK_CAPACITY} Hour Capacity'
    ).interactive() 
    
    st.altair_chart(chart, use_container_width=True)
else:

    st.info("Run the audit to generate the visualization.")
