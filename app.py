import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta
import json
import os
# CRITICAL IMPORT FIX: Use the specific module for reliable session ID access
import streamlit.runtime.scriptrunner as st_scriptrunner 
# Note: You can remove 'from datetime import date' if it was a duplicate import

# --- 0. CONFIGURATION (Constants) ---
FILE_PATH = "tasks_data.json"  # Note: This is now only a base name
MAX_WORK_CAPACITY = 13.0
DAY_OPTIONS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PALETTE = ['#4DB6AC', '#9575CD', '#B0BEC5', '#FF8A65',
           '#4DD0E1', '#9FA8DA', '#B39DDB', '#FFAB91',
           '#80CBC4', '#A1887F', '#B3E5FC', '#FFCDD2',
           '#81C784', '#A5D6A7', '#C5E1A5', '#FFD54F',
           '#90CAF9', '#AED581', '#DCE775', '#FFECB3']

# --- PAGE CONFIG (Correctly Placed) ---
st.set_page_config(
    layout="wide",
    initial_sidebar_state="auto",
    page_title="Feasleeple",
    menu_items=None
)

# ====================================================================
# --- 1. UTILITY AND PERSISTENCE FUNCTIONS (With Session ID Fix) ---
# ====================================================================

def get_user_file_path():
    """
    Retrieves the unique session ID using the standard method 
    and constructs a unique file path for each user.
    """
    # CRITICAL FIX: Use get_script_run_ctx() which is safe in deployed environments
    ctx = st_scriptrunner.get_script_run_ctx()
    if ctx is None:
        session_id = "local_debug" # Fallback for local testing
    else:
        session_id = ctx.session_id
        
    return f"tasks_{session_id}.json"

def format_ordinal_date(date_index):
    # ... (Keep this function as is) ...
    if pd.isna(date_index): return "Date N/A"
    date_obj = date_index.to_pydatetime().date()
    day = date_obj.day
    month_name = date_obj.strftime('%B')
    year = date_obj.year
    if 11 <= day <= 13: suffix = 'th'
    else: suffixes = {1: 'st', 2: 'nd', 3: 'rd'}; suffix = suffixes.get(day % 10, 'th')
    return f"{day}{suffix} {month_name} {year}"

def format_hours_minutes(decimal_hours):
    # ... (Keep this function as is) ...
    if decimal_hours <= 0: return "0 minutes"
    hours = int(decimal_hours)
    minutes = round((decimal_hours - hours) * 60)
    parts = []
    if hours > 0: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return " ".join(parts) or "0 minutes"

def load_tasks():
    file_path = get_user_file_path()
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                for task in data:
                    task['start'] = date.fromisoformat(task['start'])
                    task['end'] = date.fromisoformat(task['end'])
                return data
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return []
    return []

def check_day_in_range(start_date, end_date, day_name):
    """Checks if a specific day name exists in the date range."""
    # Convert dates to datetime objects for accurate iteration
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # Generate all dates in the range
    date_range = pd.date_range(start=start_dt, end=end_dt)
    
    # Check if the desired day name exists in the date range
    return day_name in date_range.strftime('%A').tolist()
         
def save_tasks():
    file_path = get_user_file_path()
    data_to_save = []
    for task in st.session_state.tasks:
        task_copy = task.copy()
        task_copy['start'] = task_copy['start'].isoformat()
        task_copy['end'] = task_copy['end'].isoformat()
        data_to_save.append(task_copy)
    with open(file_path, 'w') as f:
        json.dump(data_to_save, f, indent=4)

# --- 2. SESSION STATE Initialization ---
if 'audit_start' not in st.session_state:
    st.session_state.audit_start = date.today()
if 'audit_end' not in st.session_state:
    st.session_state.audit_end = date.today() + timedelta(weeks=8)
if 'tasks' not in st.session_state:
    st.session_state.tasks = load_tasks()
if 'audit_ran' not in st.session_state:
    st.session_state.audit_ran = False
if 'audit_df' not in st.session_state:
    st.session_state.audit_df = pd.DataFrame()
if 'viz_df' not in st.session_state:
    st.session_state.viz_df = pd.DataFrame()


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
    
    # --- Checkbox to select which form to display ---
    st.markdown("##### Schedule Frequency")
    event_mode = st.radio("Select Schedule Type:", ("Recurring Task (Range)", "One-Time Event (Single Day)"))
    
    
    # ===============================================
    # A. RECURRING TASK FORM (For Date Ranges)
    # ===============================================
    if event_mode == "Recurring Task (Range)":
        with st.form("recurring_form", clear_on_submit=True):
            task_name = st.text_input("Task Name (e.g., Work, Commute, Hobby)", key='r_name')
            task_unit_time = st.number_input(
                "Unit Task Time (Hours)", min_value=0.1, max_value=MAX_WORK_CAPACITY, value=2.0, step=0.5, key='r_time'
            )
            task_days = st.multiselect(
                "Which days of the week?", options=DAY_OPTIONS, default=["Monday", "Tuesday"], key='r_days'
            )
            
            # Stable Date Range Input
            task_dates = st.date_input(
                "Start and End Date Range (Inclusive)", [date.today(), date.today() + timedelta(weeks=4)], key='r_dates'
            )

            # Safely unpack the list
            if len(task_dates) == 2:
                task_start_date = task_dates[0]
                task_end_date = task_dates[1]
            else:
                task_start_date = task_dates[0]
                task_end_date = task_dates[0]

            if st.form_submit_button("Add Task (Recurring)", type="primary"):
                existing_names = [task['name'] for task in st.session_state.tasks]
                is_valid = True
                
                # --- Validation & Consistency Checks ---
                if not task_name: st.error("Please enter a task name."); is_valid = False
                if task_name in existing_names: st.error(f"Task '{task_name}' already exists."); is_valid = False
                if not task_days: st.error("Please select at least one day for the task."); is_valid = False
                if task_start_date > task_end_date: st.error("Start date must be before or the same as the end date."); is_valid = False

                # NEW CONSISTENCY ENFORCEMENT 
                invalid_days = [day for day in task_days if not check_day_in_range(task_start_date, task_end_date, day)]
                if invalid_days:
                    st.error(f"❌ Conflict: Days do not exist in the range: {', '.join(invalid_days)}."); is_valid = False
                
                if is_valid:
                    st.session_state.tasks.append({"name": task_name, "time": task_unit_time, "days": task_days, "start": task_start_date, "end": task_end_date})
                    save_tasks(); st.session_state.audit_ran = False; st.success(f"Task '{task_name}' ({task_unit_time}h) added.")

    # ===============================================
    # B. ONE-TIME EVENT FORM
    # ===============================================
    else: # event_mode == "One-Time Event (Single Day)"
        with st.form("onetime_form", clear_on_submit=True):
            task_name = st.text_input("Task Name (e.g., Doctor Appointment)", key='o_name')
            task_unit_time = st.number_input(
                "Unit Task Time (Hours)", min_value=0.1, max_value=MAX_WORK_CAPACITY, value=1.0, step=0.5, key='o_time'
            )
            single_date = st.date_input("Select Event Date", value=date.today(), key='o_date')
            
            # Determine day of week automatically for validation display
            day_name = single_date.strftime('%A')
            st.info(f"The selected day is: **{day_name}**")

            if st.form_submit_button("Add Task (One-Time)", type="primary"):
                existing_names = [task['name'] for task in st.session_state.tasks]
                is_valid = True
                
                # --- Validation Checks ---
                if not task_name: st.error("Please enter a task name."); is_valid = False
                if task_name in existing_names: st.error(f"Task '{task_name}' already exists."); is_valid = False
                
                if is_valid:
                    # Append using the single date for both start and end, and only that one day
                    st.session_state.tasks.append({"name": task_name, "time": task_unit_time, "days": [day_name], "start": single_date, "end": single_date})
                    save_tasks(); st.session_state.audit_ran = False; st.success(f"One-time task '{task_name}' ({task_unit_time}h) added.")
                    
    st.markdown("---")
    st.caption(f"**Total Tasks Loaded:** {len(st.session_state.tasks)}")
# ==============================================================================
# 📌 PANEL 2: Time Slicing and Audit Trigger
# ==============================================================================
with col2:
    st.header("2. Audit Period")
    
    # Use tuple to signal range preference and load current state
    audit_dates = st.date_input(
        "Select Range for Burnout Check",
        value=(st.session_state.audit_start, st.session_state.audit_end), 
        min_value=date(2000, 1, 1), 
        help="The audit will check all days from the start date through the end date (inclusive)."
    )

    # --- CRITICAL FIX: Only update state when 2 dates are present ---
    if len(audit_dates) == 2:
        # If the user selects a range, save both dates
        st.session_state.audit_start = audit_dates[0]
        st.session_state.audit_end = audit_dates[1]
    
    # Use the session state values (which hold the last valid range) for execution
    audit_start = st.session_state.audit_start
    audit_end = st.session_state.audit_end

    st.markdown("---")

    if st.button("▶️ Run Daily Audit", type="primary"):
        if not st.session_state.tasks:
            st.warning("Please add at least one task to run the audit.")
        elif st.session_state.audit_start > st.session_state.audit_end:
             st.error("Audit start date cannot be after the end date.")
        else:
            audit_df = run_audit(st.session_state.audit_start, st.session_state.audit_end)
            st.session_state.audit_df = audit_df 
            st.session_state.audit_ran = True 
            st.success("Audit executed successfully.")

    st.subheader("Overall Feasibility")
    if st.session_state.audit_ran:
        overload_count = (st.session_state.audit_df['Overload_Flag'] == 'Overload Day').sum()
        
        if overload_count > 0:
            st.error(f"⚠️ You have **{overload_count} overloaded days** in this range!")
        else:
            st.success("✅ No overload days found!")
    else:
        st.info("Run the audit to see feasibility results.")

# ==============================================================================
# 📌 PANEL 3: Results and Task Management
# ==============================================================================
with col3:
    st.header("3. Audit Results")

    st.subheader("Current Tasks")
    
    # Define the delete function within the scope of col3 (which is fine)
    def delete_task(index):
        # Remove the task at the specified index
        del st.session_state.tasks[index]
        save_tasks()  # Save changes to JSON
        st.session_state.audit_ran = False
        # st.rerun is removed as it's a no-op/unnecessary

    if st.session_state.tasks:
        st.caption("Click the trash icon to delete a single task.")
        
        # 1. Define the 6-column layout for the header
        # [Name, Time, Days, Start Date, End Date, Delete Icon]
        col_name, col_time, col_days, col_start, col_end, col_delete = st.columns([1.5, 0.5, 1.5, 1.5, 1.5, 0.5]) 
        
        # Add a header row for clarity (Using the column definitions from above)
        with col_name: st.markdown("**Task**")
        with col_time: st.markdown("**Hrs**")
        with col_days: st.markdown("**Days**")
        with col_start: st.markdown("**Start**")
        with col_end: st.markdown("**End**")
        with col_delete: st.markdown(" ") # Spacer for trash icon

        st.markdown("---") # Separator between header and tasks

        # 2. Iterate and display each task row (using unique keys for alignment)
        for i, task in enumerate(st.session_state.tasks):
            # REDEFINE COLUMNS INSIDE THE LOOP with a unique key
            col_name_i, col_time_i, col_days_i, col_start_i, col_end_i, col_delete_i = st.columns([1.5, 0.5, 1.5, 1.5, 1.5, 0.5])

            # Task Name
            with col_name_i:
                st.markdown(f"**{task['name']}**")
            # Time
            with col_time_i:
                st.markdown(f"{task['time']}h")
            # Days
            with col_days_i:
                days_str = ", ".join(task['days'])
                st.markdown(f"<span style='font-size: smaller;'>{days_str}</span>", unsafe_allow_html=True)
            # Start Date
            with col_start_i:
                st.markdown(f"<span style='font-size: smaller;'>{task['start']}</span>", unsafe_allow_html=True)
            # End Date
            with col_end_i:
                st.markdown(f"<span style='font-size: smaller;'>{task['end']}</span>", unsafe_allow_html=True)
                
            # Delete Button
            with col_delete_i:
                st.button("🗑️", key=f"delete_{i}", on_click=delete_task, args=(i,))

        st.markdown("---")
        
        # KEEP the "Clear All" button for mass deletion
        if st.button("Clear ALL Tasks", key="clear_tasks"):
            st.session_state.tasks = []
            st.session_state.audit_ran = False
            save_tasks()
    else:
        st.info("No tasks added yet.")
        
    st.markdown("---")
    
    # ... (Rest of the Overloaded Days display logic follows here) ...
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

















