import streamlit as st
import json
import pandas as pd
from model.DataBaseHandler import DataBaseHandler
import os
import numpy as np

# Load database authentication
db_auth = json.loads(os.environ.get('DataBaseAuth', '{}'))
db_handler = DataBaseHandler(db_auth)

# File for saving queries
QUERY_FILE = "saved_queries.json"


def load_saved_queries():
    """Load existing queries from file."""
    if os.path.exists(QUERY_FILE):
        with open(QUERY_FILE, "r") as file:
            return json.load(file)
    return {}


def save_query(query_name, active_filters):
    """Save query including both filtering conditions and selected values."""
    saved_queries = load_saved_queries()
    saved_queries[query_name] = active_filters

    with open(QUERY_FILE, "w") as file:
        json.dump(saved_queries, file, indent=4)


# Set Streamlit config
st.set_page_config(layout="wide")
st.title("Job Postings Viewer")

# Sidebar Navigation
menu = st.sidebar.radio(
    "Navigation", ["View Jobs", "Response Explanation", "View Unprocessed Jobs"])


def load_data(view_type):
    """Load job data based on view selection."""
    loaded = db_handler.fetch_all_jobs()

    # Define priority columns
    ordering = [col for col in ['insert_timestamp', 'job_title',
                                'applied', 'posting_url', 'job_id'] if col in loaded.columns]
    other_cols = [col for col in loaded.columns if col not in ordering]
    loaded = loaded[ordering + other_cols]

    # Convert columns to appropriate types
    if 'applied' in loaded.columns:
        loaded['applied'] = loaded['applied'].astype(bool)
    if 'id' in loaded.columns:
        loaded['id'] = loaded['id'].astype(str)

    # Ensure JSON column is parsed correctly
    loaded["agent_response"] = loaded["agent_response"].apply(
        lambda x: json.loads(x) if pd.notna(x) else {})

    if view_type == "View Jobs":
        json_expanded = loaded["agent_response"].apply(
            lambda data: {key: data[key]["response"] for key in data
                          if "response" in data[key]})
    elif view_type == "Response Explanation":
        json_expanded = loaded["agent_response"].apply(
            lambda data: {key: data[key]["explanation"] for key in data
                          if "explanation" in data[key]})
    else:
        return db_handler.fetch_unprocessed_jobs()

    json_expanded = json_expanded.apply(pd.Series)
    loaded = pd.concat([loaded.drop(columns=["agent_response"]), json_expanded], axis=1)

    loaded.columns = [col.replace('?', '').replace(' ', '_') if '?' in col else col
                      for col in loaded.columns]

    return loaded


def filter_contains(df, column, value=None):
    """Filters column based on user input using 'Contains' logic."""
    if not value:
        value = st.sidebar.text_input(f"Enter keyword for '{column}'")

    if value:
        condition = df[column].str.contains(value, case=False, na=False)
        return condition, {'func': 'filter_contains', 'value': value}
    return None, None


def filter_list_search(df, column, selected_values=None):
    """Filters column using a selectable list of values sorted by frequency."""
    if not selected_values:
        column_values = df[column].value_counts()
        selected_values = st.sidebar.multiselect(
            f"Select values for '{column}'", options=column_values.index.tolist())
    if selected_values:
        condition = df[column].isin(selected_values)
        return condition, {'func': 'filter_list_search', 'value': selected_values}
    return None, None


def filter_slider(df, column, selected_values=None):
    """Filters numerical columns using a range slider."""
    if selected_values:
        min_value, max_value = selected_values[0], selected_values[1]
    else:
        min_value, max_value = df[column].min(), df[column].max()
        start_value, end_value = st.sidebar.slider(
            f"Select range for '{column}'", min_value=min_value, max_value=max_value,
            value=(min_value, max_value))
    condition = (df[column] >= start_value) & (df[column] <= end_value)
    return condition, {'func': 'filter_slider', 'value': [start_value, end_value]}


def filter_datetime_slider(df, column, selected_values=None):
    """Filters datetime columns using a date range slider."""
    df[column] = pd.to_datetime(df[column])
    min_date, max_date = df[column].min(), df[column].max()
    start_date = st.sidebar.date_input(
        "Start Date", min_value=min_date, max_value=max_date, value=min_date)
    end_date = st.sidebar.date_input("End Date", min_value=min_date,
                                     max_value=max_date, value=max_date) + pd.Timedelta(1, unit='D')
    condition = (df[column] >= start_date) & (df[column] <= end_date)
    return condition, {'func': 'filter_datetime_slider', 'value': None}


def filter_boolean(df, column, bool_choice=None):
    """Filters Boolean columns using a radio button."""
    if bool_choice is None:
        bool_choice = st.sidebar.radio(f"Filter '{column}'", ["All", True, False])
    if bool_choice != "All":
        condition = df[column] == bool_choice
        return condition, {'func': 'filter_boolean', 'value': bool_choice}
    return None, None


st.sidebar.subheader("Query Management")

saved_queries = load_saved_queries()
selected_query = st.sidebar.selectbox("Load Saved Query", ["None"] + list(saved_queries.keys()))

df = load_data(menu)

st.sidebar.subheader("Filter Job Postings")
selected_columns = st.sidebar.multiselect("Select columns to filter by", df.columns)

# Load filters & values from selected query
if selected_query != "None":
    active_filters = saved_queries.get(selected_query, {})
    selected_columns.extend(active_filters.keys())
else:
    active_filters = {}

query_conditions = []

for column in selected_columns:
    col_dtype = df[column].dtype
    st.sidebar.subheader(f"Filter {column}")

    saved_col = saved_queries.get(selected_query, {}).get(column)

    if saved_col:
        condition, saved_data = eval(saved_col['func'])(df, column, saved_col['value'])
    elif pd.api.types.is_string_dtype(df[column]) or pd.api.types.is_object_dtype(df[column]):
        filter_type = st.sidebar.radio(f"Filter type for '{column}'", ["List Search", "Contains"],
                                       key=column)
        condition, saved_data = filter_contains(df, column) if filter_type == "Contains" \
            else filter_list_search(df, column)
    elif pd.api.types.is_bool_dtype(df[column]):
        condition, saved_data = filter_boolean(df, column)
    elif pd.api.types.is_numeric_dtype(df[column]):
        condition, saved_data = filter_slider(df, column)
    elif pd.api.types.is_datetime64_any_dtype(df[column]):
        condition, saved_data = filter_datetime_slider(df, column)
    else:
        raise TypeError(f"Cannot filter column '{column}' for type {col_dtype}")

    if condition is not None:
        query_conditions.append(condition)  # ✅ Only store Boolean Series
        active_filters[column] = saved_data  # ✅ Store function metadata separately

# Apply filters dynamically
if query_conditions:
    df_filtered = df[np.logical_and.reduce(query_conditions)]  # ✅ Now only contains Boolean Series
else:
    df_filtered = df

# 🔹 Allow users to save the query
if st.sidebar.button("Save Query"):
    query_name = st.sidebar.text_input("Query Name")
    if query_name:
        save_query(query_name, active_filters)
        st.sidebar.success(f"Query '{query_name}' saved!")

# 🔹 Allow user to name & save current query
query_name = st.sidebar.text_input("Enter query name to save")
if st.sidebar.button("💾 Save Query"):
    save_query(query_name, active_filters)
    st.sidebar.success(f"Query '{query_name}' saved!")

# 🔹 Sort Table Option
if sort_by := st.sidebar.selectbox("Sort by column", df.columns):
    sort_order = st.sidebar.radio("Sort Order", ["Descending", "Ascending"])
    df_filtered = df_filtered.sort_values(by=sort_by, ascending=(sort_order == "Ascending"))

# 🔹 Refresh Data Button
if st.button("🔄 Refresh Data"):
    st.rerun()

# Display DataFrame
if df.empty:
    st.write("No matching records found.")
else:
    edited_df = st.data_editor(df_filtered, height=600, use_container_width=True, num_rows='dynamic',
                               column_config={
                                   'posting_url': st.column_config.LinkColumn(),
                                   'applied': st.column_config.CheckboxColumn('Applied')},
                               hide_index=True)

    if st.button("✅ Apply Changes"):
        applied_updates = [(row["id"], row["applied"]) for idx, row in edited_df.iterrows()]

        # 🔹 Update database with applied status
        db_handler.update_applied_status(applied_updates)

        # 🔹 Sync changes to dataframe in memory
        df.update(edited_df)

        st.success("Applied status updated successfully!")

    st.download_button(
        label="⬇️ Download Data as CSV",
        data=edited_df.to_csv(index=False),
        file_name="job_postings.csv",
        mime="text/csv"
    )
