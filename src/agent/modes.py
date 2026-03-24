"""
Multi-domain mode system for AI Data Copilot.

This module provides:
- Mode switching (call_analytics, product_analytics, log_debugging, claims_analysis, system_metrics)
- Domain-specific system prompts
- Schema guidance for each mode
- Insight generation helpers
- Anomaly detection wrapper with context
"""

import pandas as pd
from typing import Optional
from src.tools.csv_tool import _dataframes
import os


current_mode: Optional[str] = None

MODES = {
    "call_analytics": {
        "name": "Call Analytics",
        "description": "Analyze call logs for Bolna AI",
        "schema": {
            "call_id": "unique call identifier",
            "city": "city where call originated",
            "call_duration": "duration in seconds",
            "success": "true/false - call succeeded",
            "language": "call language (English, Hindi, etc)",
        },
        "sample_file": "data/calls.csv",
    },
    "product_analytics": {
        "name": "Product Analytics", 
        "description": "Analyze user behavior for Clueso",
        "schema": {
            "user_id": "unique user identifier",
            "event_name": "event type (signup, click, purchase, etc)",
            "session_time": "time spent in seconds",
            "churn_flag": "true/false - user churned",
        },
        "sample_file": "data/events.csv",
    },
    "log_debugging": {
        "name": "Log Debugging",
        "description": "Analyze logs for Docket AI",
        "schema": {
            "timestamp": "log timestamp",
            "service": "service name",
            "error_code": "error code if any",
            "message": "log message",
        },
        "sample_file": "data/logs.csv",
    },
    "claims_analysis": {
        "name": "Claims Analysis",
        "description": "Analyze insurance claims for Aegis",
        "schema": {
            "claim_id": "unique claim identifier",
            "claim_amount": "amount in dollars",
            "region": "region code",
            "claim_type": "type of claim",
            "fraud_flag": "true/false - suspected fraud",
        },
        "sample_file": "data/claims.csv",
    },
    "system_metrics": {
        "name": "System Metrics",
        "description": "Analyze system metrics for Deeptrace",
        "schema": {
            "timestamp": "metric timestamp",
            "service": "service name",
            "cpu_usage": "CPU usage percentage",
            "memory": "memory usage MB",
            "latency": "response latency ms",
        },
        "sample_file": "data/metrics.csv",
    },
}

MODE_PROMPTS = {
    "call_analytics": """You are a call analytics expert helping analyze call logs for performance, failures, and regional trends.

Your role:
- Identify call success/failure patterns by city, language, and time
- Detect high failure rates that may indicate network or infrastructure issues
- Find regional trends that could inform capacity planning
- Provide actionable insights, not just raw data

When analyzing calls:
- Focus on failure rates, not just totals
- Compare metrics across cities and languages
- Look for patterns in call duration that indicate issues
- Flag any anomalies that warrant investigation

Always provide 1-2 insights after your analysis.""",

    "product_analytics": """You are a product analyst helping analyze user behavior for Clueso.

Your role:
- Identify user behavior patterns and retention trends
- Detect funnel drop-offs and conversion issues
- Find factors that correlate with churn
- Provide actionable product insights

When analyzing events:
- Focus on user journeys and funnels
- Identify where users drop off
- Look for patterns in session time and engagement
- Flag any unusual behavior that indicates issues

Always provide 1-2 insights after your analysis.""",

    "log_debugging": """You are a debugging engineer analyzing logs for Docket AI.

Your role:
- Identify root causes of errors and failures
- Detect error patterns and anomalies
- Find correlations between errors and services/timestamps
- Provide actionable debugging insights

When analyzing logs:
- Focus on error frequency and distribution
- Identify services with high error rates
- Look for timestamp patterns (spikes at certain times)
- Find error messages that indicate root causes

Always provide 1-2 insights after your analysis.""",

    "claims_analysis": """You are an insurance risk analyst analyzing claims for Aegis.

Your role:
- Detect fraud signals and suspicious patterns
- Identify anomalies in claim amounts and frequencies
- Find regional patterns that may indicate fraud rings
- Provide actionable risk insights

When analyzing claims:
- Focus on unusual claim amounts (3x+ average is suspicious)
- Look for rapid succession claims from same region
- Identify claim types with high fraud rates
- Flag any patterns that warrant investigation

Always provide 1-2 insights after your analysis.""",

    "system_metrics": """You are a system reliability engineer analyzing metrics for Deeptrace.

Your role:
- Analyze system performance and detect anomalies
- Identify correlations between metrics (CPU, memory, latency)
- Find services with degraded performance
- Provide actionable reliability insights

When analyzing metrics:
- Focus on latency and error rates, not just raw usage
- Look for correlations (CPU spikes causing latency)
- Identify services with unusual patterns
- Flag any metrics that indicate impending issues

Always provide 1-2 insights after your analysis.""",
}


def set_mode(mode_name: Optional[str]) -> bool:
    """Set the current mode. Returns True if successful."""
    global current_mode
    if mode_name is None:
        current_mode = None
        return True
    if mode_name in MODES:
        current_mode = mode_name
        return True
    return False


def get_mode() -> Optional[str]:
    """Get the current mode name."""
    return current_mode


def get_mode_info(mode_name: str) -> Optional[dict]:
    """Get mode information by name."""
    return MODES.get(mode_name)


def get_current_mode_info() -> Optional[dict]:
    """Get information about the current mode."""
    if current_mode:
        return MODES.get(current_mode)
    return None


def get_mode_prompt() -> str:
    """Get the system prompt for the current mode."""
    if current_mode and current_mode in MODE_PROMPTS:
        return MODE_PROMPTS[current_mode]
    return ""


def get_mode_schema() -> dict:
    """Get schema guidance for the current mode."""
    if current_mode and current_mode in MODES:
        return MODES[current_mode].get("schema", {})
    return {}


def generate_insights(df: pd.DataFrame, mode: str) -> list[str]:
    """Generate 1-2 natural language insights based on the mode and data."""
    insights = []
    
    if df is None or len(df) == 0:
        return insights
    
    try:
        if mode == "call_analytics":
            if "city" in df.columns and "success" in df.columns:
                city_success = df.groupby("city")["success"].apply(
                    lambda x: (x == True).mean() if x.dtype == bool else x.str.lower().eq("true").mean()
                ).reset_index()
                city_success.columns = ["city", "success_rate"]
                low_rate = city_success[city_success["success_rate"] < 0.5]
                if not low_rate.empty:
                    city = low_rate.iloc[0]["city"]
                    rate = low_rate.iloc[0]["success_rate"]
                    insights.append(f"High failure rate in {city} ({rate*100:.0f}% success) may indicate network issues")
            
            if "language" in df.columns and "success" in df.columns:
                lang_success = df.groupby("language")["success"].apply(
                    lambda x: (x == True).mean() if x.dtype == bool else x.str.lower().eq("true").mean()
                ).reset_index()
                lang_success.columns = ["language", "success_rate"]
                if len(lang_success) > 1:
                    best = lang_success.loc[lang_success["success_rate"].idxmax()]
                    worst = lang_success.loc[lang_success["success_rate"].idxmin()]
                    insights.append(f"{best['language']} calls have {best['success_rate']*100:.0f}% success vs {worst['language']} at {worst['success_rate']*100:.0f}%")
        
        elif mode == "product_analytics":
            if "event_name" in df.columns:
                event_counts = df["event_name"].value_counts()
                if len(event_counts) > 1:
                    top = event_counts.index[0]
                    insights.append(f"Most common event is '{top}' ({event_counts.iloc[0]} occurrences)")
            
            if "churn_flag" in df.columns and "session_time" in df.columns:
                churned = df[df["churn_flag"].astype(str).str.lower() == "true"]
                retained = df[df["churn_flag"].astype(str).str.lower() == "false"]
                if len(churned) > 0 and len(retained) > 0:
                    avg_churned = churned["session_time"].mean()
                    avg_retained = retained["session_time"].mean()
                    if avg_retained > avg_churned * 1.5:
                        insights.append(f"Churned users have {avg_churned:.0f}s avg session time vs {avg_retained:.0f}s for retained - shorter sessions correlate with churn")
        
        elif mode == "log_debugging":
            if "error_code" in df.columns and "service" in df.columns:
                error_by_service = df[df["error_code"].notna()].groupby("service").size()
                if not error_by_service.empty:
                    top_error_service = error_by_service.idxmax()
                    insights.append(f"Service '{top_error_service}' has the most errors ({error_by_service.max()})")
            
            if "timestamp" in df.columns and "error_code" in df.columns:
                df_copy = df.copy()
                try:
                    df_copy["hour"] = pd.to_datetime(df_copy["timestamp"]).dt.hour
                    errors_by_hour = df_copy[df_copy["error_code"].notna()].groupby("hour").size()
                    if not errors_by_hour.empty:
                        peak_hour = errors_by_hour.idxmax()
                        insights.append(f"Error spike detected at hour {peak_hour} - may indicate scheduled job failures")
                except:
                    pass
        
        elif mode == "claims_analysis":
            if "claim_amount" in df.columns:
                avg_amount = df["claim_amount"].mean()
                high_claims = df[df["claim_amount"] > avg_amount * 3]
                if len(high_claims) > 0:
                    insights.append(f"{len(high_claims)} claims exceed 3x the average amount (${avg_amount:.0f}) - may indicate fraud")
            
            if "region" in df.columns and "claim_amount" in df.columns:
                region_avg = df.groupby("region")["claim_amount"].mean()
                if len(region_avg) > 1:
                    high_region = region_avg.idxmax()
                    insights.append(f"Region '{high_region}' has highest avg claim amount (${region_avg.max():.0f})")
        
        elif mode == "system_metrics":
            numeric_cols = ["cpu_usage", "memory", "latency"]
            available = [c for c in numeric_cols if c in df.columns]
            
            if "cpu_usage" in available and "latency" in available:
                corr = df["cpu_usage"].corr(df["latency"])
                if corr > 0.7:
                    insights.append(f"Strong correlation between CPU and latency (r={corr:.2f}) - high CPU causes latency issues")
            
            if "memory" in available and "latency" in available:
                corr = df["memory"].corr(df["latency"])
                if corr > 0.7:
                    insights.append(f"Strong correlation between memory and latency (r={corr:.2f}) - memory pressure affects performance")
            
            if "service" in df.columns and "latency" in available:
                service_latency = df.groupby("service")["latency"].mean()
                if len(service_latency) > 1:
                    high_latency_service = service_latency.idxmax()
                    insights.append(f"Service '{high_latency_service}' has highest avg latency ({service_latency.max():.0f}ms)")
    
    except Exception as e:
        pass
    
    return insights[:2]


def detect_anomalies_with_context(file_path: str, column: str, mode: str) -> dict:
    """
    Wrap existing outlier detection with mode-specific context.
    Returns anomaly rows + plain English explanation.
    """
    from src.tools.csv_tool import detect_outliers, _ensure_loaded, _get_df
    import os
    
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    
    if df is None:
        return {"error": f"File not loaded: {file_path}"}
    
    result = detect_outliers(file_path, column)
    
    if "error" in result or result.get("outlier_count", 0) == 0:
        return result
    
    outliers = result.get("outliers", [])
    col_data = df[column]
    avg_value = col_data.mean()
    
    explanation = ""
    
    if mode == "call_analytics":
        if column in ["call_duration"]:
            explanation = f"These {len(outliers)} calls have unusually long duration (>{result['upper_bound']:.0f}s) - may indicate stuck calls or network issues"
        else:
            explanation = f"These {len(outliers)} entries exceed {result['upper_bound']:.0f}, {result['upper_bound']/avg_value:.1f}x the average"
    
    elif mode == "product_analytics":
        if column in ["session_time"]:
            explanation = f"These {len(outliers)} sessions have unusually long engagement (>{(result['upper_bound']/60):.0f} min) - may indicate automation or issues"
        else:
            explanation = f"These {len(outliers)} entries exceed {result['upper_bound']:.0f}, {result['upper_bound']/avg_value:.1f}x the average"
    
    elif mode == "log_debugging":
        explanation = f"Found {len(outliers)} unusual log entries in {column}"
    
    elif mode == "claims_analysis":
        if column in ["claim_amount"]:
            amount_avg = df["claim_amount"].mean()
            explanation = f"These {len(outliers)} claims exceed ${result['upper_bound']:.0f} ({result['upper_bound']/amount_avg:.1f}x avg) and may indicate fraud"
        else:
            explanation = f"These {len(outliers)} entries exceed {result['upper_bound']:.0f} and warrant investigation"
    
    elif mode == "system_metrics":
        if column in ["cpu_usage", "memory"]:
            explanation = f"These {len(outliers)} data points show high resource usage (>{(result['upper_bound']):.0f}%) - risk of performance degradation"
        elif column in ["latency"]:
            explanation = f"These {len(outliers)} entries show high latency (>{result['upper_bound']:.0f}ms) - users may experience slowness"
        else:
            explanation = f"These {len(outliers)} entries exceed {result['upper_bound']:.0f} and are anomalous"
    
    else:
        explanation = f"These {len(outliers)} entries exceed {result['upper_bound']:.0f} (3x IQR method) and may be anomalous"
    
    return {
        **result,
        "explanation": explanation,
    }


def list_modes() -> list[dict]:
    """List all available modes."""
    return [
        {
            "name": name,
            "description": info["description"],
            "schema_keys": list(info["schema"].keys()),
        }
        for name, info in MODES.items()
    ]
