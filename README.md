# Automated RootCauseAnalyzer
This is the automated root cause analyzer that can find the root causes of the given testing or production data using the predefined rules.

## Overview

**RuleAnalyzerApp** is a PyQt5-based graphical user interface (GUI) application designed for connecting to databases (MySQL or SQLite), retrieving data from selected tables, applying predefined rules for analysis, and generating HTML reports with key performance indicators (KPIs), visualizations, and troubleshooting information. The application supports automated runs based on configuration files and includes features for data filtering, rule-based predictions, root cause analysis, and data export options. It is built to handle large datasets efficiently, with a modular design for maintainability and extensibility.

The app features a tabbed interface for database configuration, data selection, application settings, analysis, and logging. Dialog windows enhance user interaction by providing previews of data and visualizations. It leverages **SQLAlchemy** for database interactions, **Pandas** for data manipulation, and **Matplotlib** for generating charts. Rules and troubleshooting data are loaded from JSON files, ensuring flexibility in defining analysis logic and solutions.

### Key Features
- **Database Connectivity**: Supports MySQL and SQLite databases.
- **Data Retrieval**: Filters data by state, date range, and selected tables.
- **Rule-Based Analysis**: Applies JSON-defined rules to predict outcomes (OK/NG) and identify root causes.
- **Analysis without rules for new projects**: Programmed to do the analysis without the rules for the new projects which do not have have enought data to generate the rules. Instead of rules.json, user has to add features(column names) to count the Pass/Fail of each features and plot the top 5 columns with most fails count as the root causes.
- **HTML Reports**: Generates reports with KPIs, embedded charts (pie/bar), and troubleshooting tables.
- **Auto-Run Mode**: Automates data retrieval, analysis, and report generation based on saved configurations.
- **Dialogs**: Provides `PreviewDialog` for tabular data previews and `VisualDialog` for chart visualizations.
- **Logging**: Real-time logging with a dedicated tab for monitoring application activity.
- **Data Export**: Supports CSV and XLSX formats for retrieved and analyzed data.

## Architecture

The application follows a modular design to separate concerns and maintain responsiveness:

- **GUI Components**: A tabbed interface (`QTabWidget`) with tabs for database configuration (`ConfigTab`), data selection (`DataTab`), application configuration (`AppConfigTab`), analysis, and logs. Dialogs (`PreviewDialog`, `VisualDialog`) enhance data and visualization previews.
- **State Management**: The `AppState` class centralizes global variables (database engine, DataFrames, rules, logs) for access across components.
- **Utilities**: Modules for data processing (`data_utils.py`), rule-based analysis (`analysis_utils.py`), and JSON loading (`loaders.py`).
- **Workers**: QThread-based workers (`AnalysisWorker`, `AutoRunWorker`) handle long-running tasks to prevent UI freezing.
- **Entry Point**: `main.py` initializes the app, loads JSON configurations, and manages auto-run logic.

### Data Flow
1. **Database Connection**: Establish connection via `ConfigTab`.
2. **Data Selection**: Select tables and apply filters (state, date range) in `DataTab`.
3. **Configuration**: Set report paths, date ranges, and auto-run options in `AppConfigTab`.
4. **Analysis**: Apply rules to data in `AnalysisTab`, generating predictions and root causes.
5. **Preview/Visualize**: Use `PreviewDialog` for data tables and `VisualDialog` for charts.
6. **Report Generation**: Create HTML reports with KPIs, charts, and troubleshooting.
7. **Logging**: Monitor operations via the Logs tab.

## Dependencies

- **Python**: 3.x
- **PyQt5**: For GUI components and dialogs.
- **SQLAlchemy**: For database connectivity (MySQL, SQLite).
- **Pandas**: For data manipulation and analysis.
- **NumPy**: For numerical operations.
- **Matplotlib**: For generating visualizations.
- **JSON**: Standard library for parsing configuration files.

## File Descriptions

### 1. `app_config_tab.py`
**Purpose**: Defines the `AppConfigTab` class for configuring application settings.

- **Key Class**: `AppConfigTab` (inherits `QWidget`)
  - **Description**: Provides a UI for configuring database connection details, state filters, auto-save paths, report naming, date ranges, table selection, and auto-run settings.
  - **UI Elements**:
    - Database inputs: Host, port, user, password (hidden), database name.
    - State selection: Combo box (`Auto`, `Rework`, `Single`) with apply filter checkbox.
    - Auto-save path: Text field with browse button.
    - Report settings: HTML filename, title, and week number inclusion checkbox.
    - Date range: Spin box for days back (`every`) and end date picker.
    - Table selection: Fetch tables button with dialog for selecting tables.
    - Auto-run: Checkbox to enable automatic analysis on startup.
  - **Key Methods**:
    - `load_config()`: Loads settings from `JSON_Files/app_config.json`.
    - `browse_auto_save_folder()`: Opens a file dialog to select the auto-save folder.
    - `fetch_tables()`: Connects to the database, retrieves table names, and displays a selection dialog.
    - `save_config()`: Saves current settings to `JSON_Files/app_config.json`.
  - **Usage**: Configures persistent settings for data retrieval and reporting.

### 2. `data_utils.py`
**Purpose**: Provides utility functions for data cleaning and processing.

- **Key Functions**:
  - `safe_to_datetime(series)`: Converts a Pandas series to datetime, handling errors with coercion.
  - `strip_dataframe(df)`: Removes whitespace from DataFrame column names and string values.
  - `safe_upper_map(s)`: Strips and uppercases a string, handling non-string inputs.
  - `compute_classification_metrics(y_true, y_pred, positive_label="NG")`: (Commented out) Calculates classification metrics (accuracy, precision, recall, F1, etc.).
- **Usage**: Ensures data consistency during retrieval and analysis.

### 3. `data_tab.py`
**Purpose**: Defines the `DataTab` class for selecting and retrieving data from the database.

- **Key Class**: `DataTab` (inherits `QWidget`)
  - **Description**: Provides a UI for listing database tables, selecting them, applying filters (state, date range), and retrieving data.
  - **UI Elements**:
    - Table list: `QListWidget` with checkable items for table selection.
    - Controls: Select all checkbox, refresh tables button.
    - Filters: State combo box, apply state checkbox, date range pickers (from/to).
    - Retrieve button: Initiates data retrieval with progress dialog.
  - **Key Methods**:
    - `toggle_all_tables(state)`: Checks or unchecks all tables in the list.
    - `refresh_tables()`: Fetches table names from the database and populates the list.
    - `retrieve_data()`: Queries selected tables with filters, displays progress, and shows a summary dialog (using `PreviewDialog`).
  - **Usage**: Populates `AppState.retrieved_dfs` with retrieved DataFrames.

### 4. `db_credentials.py`
**Purpose**: Defines the `ConfigTab` class for setting up database connections.

- **Key Class**: `ConfigTab` (inherits `QWidget`)
  - **Description**: Provides a UI for entering database credentials and selecting a database.
  - **UI Elements**:
    - Inputs: Host, port, user, password (hidden).
    - Buttons: Connect to server, select database from combo box, use database.
  - **Key Methods**:
    - `connect_server()`: Connects to MySQL server, lists databases; falls back to local SQLite files if connection fails.
    - `use_db()`: Sets the selected database as the active engine and updates the data tab.
  - **Usage**: Establishes the database connection for subsequent operations.

### 5. `analysis_utils.py`
**Purpose**: Provides functions for rule-based data analysis.

- **Key Functions**:
  - `clean_value(val)`: Strips whitespace from string values.
  - `_normalize_str(s)`: Strips and uppercases a string.
  - `_truthy_str(s)`, `_falsy_str(s)`: Identifies truthy/falsy string values (e.g., "TRUE", "FAIL").
  - `_get_branch_by_exact_key(rule, value)`: Matches rule branches by normalized keys, excluding reserved keywords.
  - `analyze_row_with_path(row, rule, parent_feature=None, path=None)`: Recursively applies rules to a DataFrame row, returning prediction (OK/NG), root cause, and match path.
  - `collect_rule_features(rule)`: Extracts unique feature names from a rule dictionary.
- **Usage**: Core logic for analyzing data rows based on JSON rules.

### 6. `app_state.py`
**Purpose**: Manages global application state and logging.

- **Key Class**: `AppState`
  - **Description**: Static class holding global variables and a logging signal.
  - **Attributes**:
    - `engine`: SQLAlchemy engine for database connections.
    - `selected_database`: Name of the active database.
    - `selected_tables`: List of selected table names.
    - `retrieved_dfs`: Dictionary of retrieved DataFrames.
    - `analyzed_dfs`: Dictionary of analyzed DataFrames.
    - `rules`: Dictionary of station rules from `rules.json`.
    - `troubleshooting`: Dictionary of troubleshooting data from `troubleshootings.json`.
    - `logs`: List of log entries.
    - `state`: Current state filter (e.g., "Auto").
    - `log_signal`: PyQt signal for log updates.
  - **Methods**:
    - `append_log(text)`: Adds a log entry and emits the log signal.
- **Functions**:
  - `log(msg, level='INFO')`: Logs a message with timestamp and level.
- **Usage**: Centralizes state and logging across the application.

### 7. `loaders.py`
**Purpose**: Loads and validates JSON configuration files.

- **Key Functions**:
  - `load_rules()`: Loads `rules.json` into `AppState.rules`, exiting on critical errors.
  - `load_troubleshooting()`: Loads `troubleshootings.json` into `AppState.troubleshooting`, validating structure and logging warnings for empty or invalid methods.
  - `load_features()`: Loads `featuress.json` into `AppState.features`.
- **Usage**: Initializes rules or features and troubleshooting data at startup.

### 8.1 `rule_analyzer_app.py` for rule-based analyzer
**Purpose**: Defines the main application window and core analysis/reporting logic.

- **Key Classes**:
  - **AnalysisWorker** (inherits `QThread`):
    - Runs rule-based analysis in the background.
    - Emits signals for progress, logs, completion, and errors.
    - Applies rules to rows, adding `Prediction`, `Root_Cause`, and `Match_Path` columns.
  - **AutoRunWorker** (inherits `QThread`):
    - Handles auto-run: connects to database, retrieves data, analyzes, and generates reports.
    - Emits signals for logs, completion, and errors.
  - **RuleAnalyzerApp** (inherits `QTabWidget`):
    - Main window with tabs: Database Config, Data Selection, App Config, Analysis, Logs.
    - **Key Methods**:
      - `update_for_new_data()`: Updates analysis tab with retrieved data.
      - `perform_analysis()`: Starts the analysis worker.
      - `generate_html_report()`: Creates HTML reports with KPIs, embedded charts (base64 PNG), and troubleshooting tables.
      - `perform_auto_run(config)`: Executes auto-run sequence.
      - `save_html_report(...)`: Saves HTML report and optional data exports (CSV/XLSX).
- **Usage**: Orchestrates the GUI, analysis, and reporting workflows.

### 8.2 `rule_analyzer_app.py` for pre-defined features analysis
**Purpose**: Defines the main application window and core analysis/reporting logic.

- **Key Classes**:
  - **AnalysisWorker** (inherits `QThread`):
    - Runs rule-based analysis in the background.
    - Emits signals for progress, logs, completion, and errors.
    - Applies rules to rows, adding `Prediction`, `Root_Cause`, and `Match_Path` columns.
  - **AutoRunWorker** (inherits `QThread`):
    - Handles auto-run: connects to database, retrieves data, analyzes, and generates reports.
    - Emits signals for logs, completion, and errors.
  - **RuleAnalyzerApp** (inherits `QTabWidget`):
    - Main window with tabs: Database Config, Data Selection, App Config, Analysis, Logs.
    - **Key Methods**:
      - `update_for_new_data()`: Updates analysis tab with retrieved data.
      - `perform_analysis()`: Starts the analysis worker. Plotting method differs from rule-based as it use the pre-defined features to get the root causes count.
      - `generate_html_report()`: Creates HTML reports with KPIs, embedded charts (base64 PNG), and troubleshooting tables.
      - `perform_auto_run(config)`: Executes auto-run sequence.
      - `save_html_report(...)`: Saves HTML report and optional data exports (CSV/XLSX).
- **Usage**: Orchestrates the GUI, analysis, and reporting workflows.

### 9. `dialogs.py`
**Purpose**: Defines dialog windows for previewing data and visualizations.

- **Key Classes**:
  - **PreviewDialog** (inherits `QDialog`):
    - **Description**: Displays a Pandas DataFrame in a non-editable, sortable table.
    - **Attributes**:
      - `table`: `QTableWidget` for displaying DataFrame rows and columns.
      - `warning_label`: Shows truncation warning if row limit (500) is applied.
    - **Features**:
      - Limits to 500 rows unless `allow_all_rows=True`.
      - Resizes columns to contents, supports sorting, and alternates row colors.
    - **Usage**: Previews retrieved or analyzed DataFrames (e.g., in `DataTab` summary).
  - **VisualDialog** (inherits `QDialog`):
    - **Description**: Displays a Matplotlib visualization using a provided plotting function.
    - **Attributes**:
      - `canvas`: `FigureCanvas` for rendering the Matplotlib figure.
      - `ax`: Matplotlib axes for plotting.
      - `save_btn`: Button to save the visualization as PNG, JPG, or PDF.
    - **Methods**:
      - `save_visual()`: Saves the plot to a user-specified file.
    - **Usage**: Displays charts (e.g., pie, bar) for analysis results.
- **Usage**: Enhances user interaction by providing visual and tabular data previews.

### 10. `main.py`
**Purpose**: Entry point for the application.

- **Description**:
  - Initializes QApplication and `RuleAnalyzerApp`.
  - Loads `rules.json` and `troubleshootings.json` into `AppState`.
  - Checks for auto-run configuration in `JSON_Files/app_config.json`.
  - Prompts user for auto-run confirmation (with 3-minute timeout).
  - Shows the main window or exits based on user input.
- **Usage**: Run with `python main.py`.

### 11. `app_config.json`
**Purpose**: Stores application configuration settings in JSON format.

- **Description**: This file contains persistent settings for the application, loaded and saved via `AppConfigTab`. It includes database connection details, report generation options, date ranges, selected tables, and auto-run flags. The provided content includes dummy data for demonstration.
- **Structure**:
  - **host**: Database host (e.g., "localhost").
  - **port**: Database port (e.g., "3306").
  - **user**: Database username (e.g., "root").
  - **password**: Database password (empty in dummy data).
  - **database**: Database name (e.g., "testdb").
  - **auto_save_path**: Path for saving HTML reports (e.g., "/Users/Downloads").
  - **html_filename**: Base filename for HTML reports (e.g., "ANALYSIS REPORT").
  - **html_title**: Title for HTML reports (e.g., "ROOT CAUSE ANALYSIS").
  - **include_week_no**: Boolean to append week number to filename and title.
  - **every**: Number of days back for data retrieval (e.g., 7).
  - **date_setup**: End date for data retrieval (e.g., "2025/05/12").
  - **auto_run**: Boolean to enable auto-run mode.
  - **selected_tables**: Array of table names (e.g., ["table_1", "table_2", ...]).
  - **state**: State filter (e.g., "Auto").
  - **apply_state**: Boolean to apply state filter.
- **Usage**: Loaded at startup to configure auto-run and other settings; saved when configurations are updated.

### 12. `rules.json`
**Purpose**: Defines analysis rules for stations and models in JSON format.

- **Description**: This file structures rules for different stations (e.g., "Station_1", "Station_2") and models (e.g., "ALL MODELS"). Each rule is a nested dictionary specifying features to check, branches (fail/pass/Disable), and predictions (OK/NG) with optional counts. The provided content includes dummy data with truncated rules for demonstration.
- **Structure**:
  - Top-level: Dictionary keyed by station names (e.g., "Station_1").
  - **models**: Sub-dictionary with model names (e.g., "ALL MODELS").
  - **rules**: Array of rule objects.
  - Rule Object:
    - **feature**: The data column to evaluate (e.g., "Model", "Voltage_Test").
    - Branches: Keyed by values (e.g., "EX_1", "EX_2") or reserved (fail, pass, Disable), leading to sub-rules or predictions.
    - **Prediction**: Outcome (e.g., "NG", "OK").
    - Optional: Counts like "OK": number, "NG": number.
- **Usage**: Loaded into `AppState.rules` via `load_rules()`; used in analysis to evaluate data rows.

### 13. `features.json`
**Purpose**: Defines features to count Pass/Fail in JSON format.

- **Description**: This file structures features for different stations (e.g., "Station_1", "Station_2") and features (e.g., "Column_1", "Column_2"). The features are listed under each tables they belong to . The provided content includes dummy data with truncated rules for demonstration.
- **Structure**:
  - Top-level: Dictionary keyed by station names(Table Names) (e.g., "Station_1").
  - **Features**: List of column names.
  - Rule Object:
    - **feature**: The data column to check Pass/Fail (e.g., "Current_Judge", "Hpatic Judge").
- **Usage**: Loaded into `AppState.features` via `load_features()`; used in analysis to evaluate data rows.

### 14. `troubleshootings.json`
**Purpose**: Provides troubleshooting methods for features in stations in JSON format.

- **Description**: This file maps stations to features, each with a list of possible problems and solutions. The provided content includes dummy data with repeated "Possible Problem" and "Solution" entries, some truncated for demonstration.
- **Structure**:
  - Top-level: Dictionary keyed by station names (e.g., "Station_1", "Station_2").
  - Feature Sub-dictionary: Keyed by feature names (e.g., "Voltage_Test", "Button_1_Force_Test").
  - Methods Array: List of objects with:
    - **Possible Problem**: Description of the issue (e.g., "Possible Problem").
    - **Solution**: Recommended fix (e.g., "Solution").
- **Usage**: Loaded into `AppState.troubleshooting` via `load_troubleshooting()`; incorporated into HTML reports for NG predictions.

## Key Concepts

- **Rules**: JSON structure defining features, branches (pass/fail/disable), predictions (OK/NG), and root causes. Applied row-wise to DataFrames.
- **Analysis**: Uses `analyze_row_with_path` to generate predictions, root causes, and match paths based on rules.
- **Reports**: HTML output with:
  - **KPIs**: Displayed as styled cards (e.g., total rows, NG counts).
  - **Charts**: Pie and bar charts embedded as base64 PNGs, generated via Matplotlib.
  - **Troubleshooting**: Tables listing root causes, possible problems, solutions, counts, and percentages.
- **Auto-Run**: Loads config, retrieves data for the last N days, analyzes, saves report, and exits.
- **Dialogs**: `PreviewDialog` for tabular data, `VisualDialog` for charts, improving data inspection.
- **Logging**: Real-time logs in the Logs tab, updated via `AppState.log_signal`.

## Usage Guide

1. **Setup**:
   - Place `rules.json` and `troubleshootings.json` in the `JSON_Files/` directory.
   - Ensure dependencies are installed (`pip install pyqt5 sqlalchemy pandas numpy matplotlib`).

2. **Run the Application**:
   - Execute `python main.py`.
   - If auto-run is enabled in `app_config.json`, confirm the prompt (Yes/No) or wait for the 3-minute timeout.

3. **Connect to Database**:
   - In the **Database Config** tab, enter host, port, user, password, and connect.
   - Select a database from the combo box and click "Use Database."

4. **Select Data**:
   - In the **Data Selection** tab, refresh tables, select desired tables, and apply filters (state, date range).
   - Click "Retrieve Data" to fetch data, view progress, and preview in `PreviewDialog`.

5. **Configure Application**:
   - In the **App Config** tab, set:
     - Database details (if not set in Database Config).
     - Auto-save path for HTML reports.
     - Report filename and title.
     - Date range (days back and end date).
     - Table selection and auto-run settings.
   - Save configuration to `JSON_Files/app_config.json`.

6. **Analyze Data**:
   - In the **Analysis** tab, select stations and models.
   - Run analysis to generate predictions and root causes.
   - View results in tables or charts via `PreviewDialog` or `VisualDialog`.

7. **Generate Reports**:
   - Preview or save HTML reports with KPIs, charts, and troubleshooting.
   - Optionally export data as CSV or XLSX.
   - Reports can be auto-opened in a browser.

8. **Monitor Logs**:
   - Check the **Logs** tab for real-time updates on operations, errors, and warnings.

## Example Workflow

1. **Auto-Run Example**:
   - Configure `app_config.json` with database details, selected tables, and `auto_run: true`.
   - Run `main.py`, confirm auto-run.
   - App connects to the database, retrieves data for the last 7 days, analyzes, generates an HTML report, and exits.

2. **Manual Workflow**:
   - Start the app, connect to a MySQL database (`localhost:3306`, user `root`).
   - Select tables, set date range (e.g., last week), and retrieve data.
   - Analyze with rules, view results in `PreviewDialog`.
   - Generate an HTML report with charts in `VisualDialog` and save to a folder.

## Potential Improvements

- **Robust JSON Validation**: Add stricter validation for `rules.json` and `troubleshootings.json` to handle edge cases.
- **Database Support**: Extend to support PostgreSQL or other databases via SQLAlchemy.
- **Interactive Visualizations**: Integrate interactive charts (e.g., Plotly) in `VisualDialog`.
- **Enhanced Previews**: Add filtering or search capabilities to `PreviewDialog`.
- **Auto-Run Enhancements**: Configurable timeout and retry logic for auto-run.
- **Performance**: Optimize large dataset handling in `PreviewDialog` and analysis.
- **Error Handling**: Improve user feedback for invalid configurations or data errors.

## Troubleshooting

- **Database Connection Fails**:
  - Verify host, port, user, and password in `ConfigTab`.
  - Ensure MySQL server is running or SQLite files are accessible.
- **No Tables Listed**:
  - Check database connection and refresh tables in `DataTab`.
- **Analysis Errors**:
  - Ensure `rules.json` is valid and matches data columns.
- **Report Issues**:
  - Verify auto-save path exists and is writable.
  - Check Matplotlib backend (`Agg`) for chart rendering.
- **Auto-Run Fails**:
  - Validate `app_config.json` for complete settings.

## Author

**Name:** Waiyan Htun
**Role:** Developer / Analyst
**University:** Rangsit University International Program
**Email:** [waiyansanchez2000@gmail.com](mailto:waiyansanchez2000@gmail.com)
**Portfolio:** [https://github.com/<your-username>](https://github.com/Waiyan-Tun)

---

## ⚖️ License

This project is licensed under the **MIT License** — see the [LICENSE](./LICENSE) file for details.

```
MIT License © 2025 Waiyan Htun
```

