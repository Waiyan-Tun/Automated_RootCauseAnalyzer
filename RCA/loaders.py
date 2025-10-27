import json
from PyQt5.QtWidgets import QMessageBox
import sys
from app_state import log

def load_rules():
    try:
        with open("JSON_Files/rules.json", "r") as f:
            rules = json.load(f)
            log(f"Successfully loaded rules.json with {len(rules)} stations")
            return rules
    except FileNotFoundError:
        log("rules.json not found", "ERROR")
        QMessageBox.critical(None, "Error", "rules.json not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        log(f"Failed to parse rules.json: {e}", "ERROR")
        QMessageBox.critical(None, "Error", f"Invalid JSON in rules.json: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"Failed to load rules.json: {e}", "ERROR")
        QMessageBox.critical(None, "Error", f"Failed to load rules.json: {e}")
        sys.exit(1)

def load_troubleshooting():
    try:
        with open("JSON_Files/troubleshootings.json", "r") as f:
            troubleshooting = json.load(f)
            if not isinstance(troubleshooting, dict):
                raise ValueError("troubleshootings.json must be a dictionary")
            for station, features in troubleshooting.items():
                if not isinstance(features, dict):
                    raise ValueError(f"Station {station} must map to a dictionary")
                for feature, methods in features.items():
                    if not isinstance(methods, list):
                        raise ValueError(f"Troubleshooting methods for {feature} in station {station} must be a list")
                    if not methods:
                        log(f"Empty troubleshooting methods for {feature} in station {station}", "WARN")
                    for method in methods:
                        if not isinstance(method, dict) or "Possible Problem" not in method or "Solution" not in method or not isinstance(method["Possible Problem"], str) or not isinstance(method["Solution"], str) or not method["Possible Problem"].strip() or not method["Solution"].strip():
                            log(f"Invalid method for {feature} in station {station}: {method}", "WARN")
            log(f"Successfully loaded troubleshootings.json with {len(troubleshooting)} stations")
            return troubleshooting
    except FileNotFoundError:
        log("troubleshootings.json not found, using empty troubleshooting data", "WARN")
        QMessageBox.warning(None, "Warning", "troubleshootings.json not found, no troubleshooting methods available")
        return {}
    except json.JSONDecodeError as e:
        log(f"Failed to parse troubleshootings.json: {e}", "ERROR")
        QMessageBox.critical(None, "Error", f"Invalid JSON in troubleshootings.json: {e}")
        return {}
    except ValueError as e:
        log(f"Invalid structure in troubleshootings.json: {e}", "ERROR")
        QMessageBox.critical(None, "Error", f"Invalid structure in troubleshootings.json: {e}")
        return {}
    except Exception as e:
        log(f"Failed to load troubleshootings.json: {e}", "ERROR")
        QMessageBox.critical(None, "Error", f"Failed to load troubleshootings.json: {e}")
        return {}