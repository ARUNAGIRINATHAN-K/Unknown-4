import dearpygui.dearpygui as dpg
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import io
import os

# Global variables
df = None
filtered_df = None

def load_csv(sender=None, app_data=None):
    """Callback for the file dialog.
    Support being called either directly (no args) or by Dear PyGui with (sender, app_data).
    """
    global df, filtered_df
    # app_data (when provided by DPG) contains the selection dict with 'file_path_name'
    selection = None
    if app_data and isinstance(app_data, dict) and 'file_path_name' in app_data:
        selection = app_data
    else:
        # Fallback to reading the stored widget value
        try:
            selection = dpg.get_value("file_dialog")
        except Exception:
            selection = None

    if selection and 'file_path_name' in selection:
        file_path = selection['file_path_name']
        # Update visible selected file field
        try:
            dpg.set_value("selected_file", file_path)
        except Exception:
            pass

        try:
            # Support CSV and Excel files
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ('.xls', '.xlsx'):
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path)
            filtered_df = df.copy()
            dpg.set_value("status_text", f"Loaded: {file_path} | Rows: {len(df)}, Columns: {len(df.columns)}")
            populate_table()
            populate_column_selectors()
            show_summary()
            update_all_plots()
        except Exception as e:
            dpg.set_value("status_text", f"Error loading file: {str(e)}")

def populate_table():
    if df is None:
        return
    with dpg.table(tag="data_table", header_row=True, borders_innerH=True, borders_outerH=True,
                   borders_innerV=True, borders_outerV=True, width=800, height=300):
        for col in df.columns:
            dpg.add_table_column(label=col)
        for i in range(min(50, len(df))):  # Show first 50 rows
            with dpg.table_row():
                for col in df.columns:
                    val = str(df.iloc[i][col]) if pd.notna(df.iloc[i][col]) else "NA"
                    dpg.add_text(val[:50])  # Truncate long text

def populate_column_selectors():
    cols = list(df.select_dtypes(include=['float64', 'int64']).columns)
    cat_cols = list(df.select_dtypes(include=['object', 'category']).columns)
    
    dpg.delete_item("hist_col_group", children_only=True)
    dpg.delete_item("scatter_x_group", children_only=True)
    dpg.delete_item("scatter_y_group", children_only=True)
    
    with dpg.group(parent="hist_col_group"):
        dpg.add_combo(label="Histogram Column", items=cols, default_value=cols[0] if cols else "", 
                      callback=update_histogram, tag="hist_combo")
    
    with dpg.group(parent="scatter_x_group"):
        dpg.add_combo(label="X Axis", items=cols, default_value=cols[0] if cols else "", 
                      callback=update_scatter, tag="scatter_x_combo")
    with dpg.group(parent="scatter_y_group"):
        dpg.add_combo(label="Y Axis", items=cols[1] if len(cols)>1 else cols[0] if cols else "", 
                      callback=update_scatter, tag="scatter_y_combo")

def show_summary():
    if df is None:
        return
    summary = []
    numeric_df = df.select_dtypes(include=['float64', 'int64'])
    
    for col in numeric_df.columns:
        col_data = numeric_df[col]
        summary.append({
            "Column": col,
            "Mean": round(col_data.mean(), 3),
            "Median": round(col_data.median(), 3),
            "Std": round(col_data.std(), 3),
            "Missing": col_data.isna().sum(),
            "Min": round(col_data.min(), 3),
            "Max": round(col_data.max(), 3)
        })
    
    dpg.delete_item("summary_table", children_only=True)
    with dpg.table(tag="summary_table", parent="summary_panel", header_row=True):
        for header in ["Column", "Mean", "Median", "Std", "Missing", "Min", "Max"]:
            dpg.add_table_column(label=header)
        for row in summary:
            with dpg.table_row():
                for key in ["Column", "Mean", "Median", "Std", "Missing", "Min", "Max"]:
                    dpg.add_text(str(row[key]))

def apply_filters():
    global filtered_df
    if df is None:
        return
    filtered_df = df.copy()
    
    # Apply numeric range filters
    for col in df.select_dtypes(include=['float64', 'int64']).columns:
        min_val = dpg.get_value(f"min_{col}")
        max_val = dpg.get_value(f"max_{col}")
        if min_val is not None:
            filtered_df = filtered_df[filtered_df[col] >= min_val]
        if max_val is not None:
            filtered_df = filtered_df[filtered_df[col] <= max_val]
    
    update_all_plots()

def update_histogram():
    if filtered_df is None:
        return
    col = dpg.get_value("hist_combo")
    if col and col in filtered_df.columns:
        fig = px.histogram(filtered_df, x=col, nbins=30, title=f"Histogram of {col}")
        fig.update_layout(height=400)
        dpg.set_value("hist_plot", fig.to_html(include_plotlyjs="cdn"))

def update_scatter():
    if filtered_df is None:
        return
    x_col = dpg.get_value("scatter_x_combo")
    y_col = dpg.get_value("scatter_y_combo")
    if x_col and y_col and x_col in filtered_df.columns and y_col in filtered_df.columns:
        fig = px.scatter(filtered_df, x=x_col, y=y_col, title=f"{x_col} vs {y_col}",
                         trendline="ols")
        fig.update_layout(height=500)
        dpg.set_value("scatter_plot", fig.to_html(include_plotlyjs="cdn"))

def update_correlation():
    if filtered_df is None:
        return
    numeric_df = filtered_df.select_dtypes(include=['float64', 'int64'])
    if numeric_df.shape[1] < 2:
        dpg.set_value("corr_plot", "<h3>Not enough numeric columns</h3>")
        return
    corr = numeric_df.corr()
    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.columns,
        colorscale='RdBu',
        zmid=0
    ))
    fig.update_layout(title="Correlation Heatmap", height=500)
    dpg.set_value("corr_plot", fig.to_html(include_plotlyjs="cdn"))

def update_all_plots():
    update_histogram()
    update_scatter()
    update_correlation()

# GUI Setup
dpg.create_context()

with dpg.file_dialog(directory_selector=False, show=False, callback=load_csv, tag="file_dialog", width=700, height=400):
    dpg.add_file_extension("*.csv")
    dpg.add_file_extension("*.xls")
    dpg.add_file_extension("*.xlsx")
    # Allow showing all files as a fallback so users can see files if specific filters hide them
    dpg.add_file_extension("*.*")

with dpg.window(label="CSV Data Visualizer", width=1400, height=900):
    dpg.add_text("CSV Data Explorer", tag="status_text")
    dpg.add_button(label="Upload CSV", callback=lambda: dpg.show_item("file_dialog"))
    # Visible field to show the selected file path
    dpg.add_input_text(label="Selected File", tag="selected_file", readonly=True, width=600)
    dpg.add_separator()
    
    with dpg.group(horizontal=True):
        with dpg.child_window(width=850, height=650):
            with dpg.tab_bar():
                with dpg.tab(label="Data Table"):
                    dpg.add_text("Preview (first 50 rows):")
                    with dpg.group(): 
                        dpg.add_table(tag="data_table")
                
                with dpg.tab(label="Summary"):
                    dpg.add_text("Numeric Column Statistics:")
                    with dpg.child_window(height=500, tag="summary_panel"):
                        pass
                
                with dpg.tab(label="Filters"):
                    dpg.add_text("Range Filters (leave blank to ignore):")
                    if df is not None:
                        for col in df.select_dtypes(include=['float64', 'int64']).columns:
                            col_min, col_max = df[col].min(), df[col].max()
                            with dpg.group(horizontal=True):
                                dpg.add_text(f"{col}:")
                                dpg.add_input_float(label="Min", tag=f"min_{col}", default_value=None, width=100)
                                dpg.add_input_float(label="Max", tag=f"max_{col}", default_value=None, width=100)
                    dpg.add_button(label="Apply Filters", callback=apply_filters)
        
        with dpg.child_window(width=520):
            with dpg.group():
                dpg.add_text("Histogram")
                with dpg.group(horizontal=True, tag="hist_col_group"): pass
                if hasattr(dpg, "plotly_plot"):
                    with dpg.plotly_plot(tag="hist_plot", height=250):
                        pass
                else:
                    # Fallback: create a multiline text widget to hold Plotly HTML
                    dpg.add_input_text(tag="hist_plot", default_value="", multiline=True, height=250)
                
                dpg.add_spacer(height=10)
                dpg.add_text("Scatter Plot")
                with dpg.group(horizontal=True):
                    with dpg.group(tag="scatter_x_group"): pass
                    with dpg.group(tag="scatter_y_group"): pass
                if hasattr(dpg, "plotly_plot"):
                    with dpg.plotly_plot(tag="scatter_plot", height=300):
                        pass
                else:
                    dpg.add_input_text(tag="scatter_plot", default_value="", multiline=True, height=300)
                
                dpg.add_spacer(height=10)
                dpg.add_text("Correlation Heatmap")
                if hasattr(dpg, "plotly_plot"):
                    with dpg.plotly_plot(tag="corr_plot", height=300):
                        pass
                else:
                    dpg.add_input_text(tag="corr_plot", default_value="", multiline=True, height=300)

dpg.create_viewport(title='CSV Visualizer with Dear PyGui', width=1400, height=940)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()