"""
Utility functions for Mileage Tracker Pro Dashboard
Includes performance monitoring, data validation, and helper functions
"""

import time
import functools
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitor and log query performance"""
    
    def __init__(self):
        self.metrics = []
    
    def track(self, func: Callable) -> Callable:
        """Decorator to track function execution time"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            self.metrics.append({
                'function': func.__name__,
                'execution_time': execution_time,
                'timestamp': datetime.now()
            })
            
            if execution_time > 1.0:  # Log slow queries
                logger.warning(f"Slow query: {func.__name__} took {execution_time:.2f}s")
            
            return result
        return wrapper
    
    def get_performance_report(self) -> pd.DataFrame:
        """Get performance metrics as DataFrame"""
        if not self.metrics:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.metrics)
        df['execution_time'] = df['execution_time'].round(3)
        return df.groupby('function').agg({
            'execution_time': ['mean', 'max', 'min', 'count']
        }).round(3)

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

class DataValidator:
    """Validate and clean data from Supabase"""
    
    @staticmethod
    def validate_users_data(data: List[Dict]) -> pd.DataFrame:
        """Validate and clean users data"""
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Ensure required columns exist
        required_cols = ['id', 'email', 'created_at']
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        
        # Add name column if missing
        if 'name' not in df.columns:
            df['name'] = df['email'].apply(lambda x: x.split('@')[0] if x else 'Unknown')
        
        # Clean email addresses
        df['email'] = df['email'].str.lower().str.strip()
        
        # Convert timestamps
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        
        return df
    
    @staticmethod
    def validate_trips_data(data: List[Dict]) -> pd.DataFrame:
        """Validate and clean trips data"""
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Ensure required columns
        required_cols = ['id', 'user_id', 'distance', 'duration', 'created_at']
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        
        # Clean numeric data
        df['distance'] = pd.to_numeric(df['distance'], errors='coerce').fillna(0)
        df['duration'] = pd.to_numeric(df['duration'], errors='coerce').fillna(0)
        
        # Remove invalid trips
        df = df[df['distance'] > 0]
        df = df[df['duration'] > 0]
        
        # Convert timestamps
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        
        # Remove future dates
        df = df[df['created_at'] <= datetime.now()]
        
        return df

class ChartHelpers:
    """Helper functions for creating consistent charts"""
    
    @staticmethod
    def apply_chart_theme(fig):
        """Apply consistent theme to Plotly charts"""
        fig.update_layout(
            font=dict(family="Arial, sans-serif", size=12),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=30, b=0),
            hoverlabel=dict(bgcolor="white", font_size=12),
            hovermode='x unified'
        )
        
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)',
            zeroline=False
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)',
            zeroline=False
        )
        
        return fig
    
    @staticmethod
    def create_color_scale(n: int) -> List[str]:
        """Generate a color scale for n items"""
        colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ]
        return colors[:n] if n <= len(colors) else colors * (n // len(colors) + 1)

class MetricsCalculator:
    """Calculate advanced metrics and KPIs"""
    
    @staticmethod
    def calculate_user_lifetime_value(trips_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate estimated lifetime value per user"""
        if trips_df.empty:
            return pd.DataFrame()
        
        # Group by user
        user_stats = trips_df.groupby('user_id').agg({
            'id': 'count',
            'distance': 'sum',
            'duration': 'sum',
            'created_at': ['min', 'max']
        })
        
        user_stats.columns = ['trip_count', 'total_distance', 'total_duration', 'first_trip', 'last_trip']
        
        # Calculate metrics
        user_stats['days_active'] = (user_stats['last_trip'] - user_stats['first_trip']).dt.days + 1
        user_stats['trips_per_day'] = user_stats['trip_count'] / user_stats['days_active'].clip(lower=1)
        user_stats['avg_distance_per_trip'] = user_stats['total_distance'] / user_stats['trip_count']
        
        # Simple LTV calculation (can be customized based on business model)
        user_stats['estimated_ltv'] = (
            user_stats['trip_count'] * 0.5 +  # Value per trip
            user_stats['total_distance'] * 0.1 +  # Value per mile
            user_stats['days_active'] * 0.2  # Value per day active
        )
        
        return user_stats.reset_index()
    
    @staticmethod
    def calculate_churn_probability(last_activity_days: int) -> float:
        """Calculate probability of churn based on days since last activity"""
        # Simple sigmoid function for churn probability
        import math
        
        if last_activity_days <= 7:
            return 0.05
        elif last_activity_days <= 14:
            return 0.15
        elif last_activity_days <= 30:
            return 0.40
        elif last_activity_days <= 60:
            return 0.75
        else:
            return 0.95
    
    @staticmethod
    def calculate_engagement_score(
        trip_count: int,
        days_active: int,
        last_activity_days: int,
        total_distance: float
    ) -> float:
        """Calculate user engagement score (0-100)"""
        
        # Normalize metrics
        trip_score = min(trip_count / 50, 1) * 30  # Max 30 points
        frequency_score = min((trip_count / max(days_active, 1)) * 10, 1) * 25  # Max 25 points
        recency_score = max(0, (30 - last_activity_days) / 30) * 25  # Max 25 points
        distance_score = min(total_distance / 1000, 1) * 20  # Max 20 points
        
        total_score = trip_score + frequency_score + recency_score + distance_score
        
        return round(total_score, 1)

class CacheManager:
    """Manage cache for better performance"""
    
    @staticmethod
    def clear_all_cache():
        """Clear all Streamlit cache"""
        st.cache_data.clear()
        st.cache_resource.clear()
        logger.info("All cache cleared")
    
    @staticmethod
    def get_cache_info() -> Dict[str, Any]:
        """Get information about current cache usage"""
        # This is a placeholder - Streamlit doesn't expose cache metrics directly
        return {
            'cache_enabled': True,
            'ttl_seconds': 300,
            'recommendation': 'Clear cache if data seems stale'
        }

class NotificationManager:
    """Handle notifications and alerts"""
    
    @staticmethod
    def check_alerts(metrics: Dict[str, Any]) -> List[str]:
        """Check for conditions that should trigger alerts"""
        alerts = []
        
        # Check for low engagement
        if metrics.get('engagement_rate', 100) < 20:
            alerts.append("⚠️ Low user engagement detected (< 20%)")
        
        # Check for high churn risk
        if metrics.get('churn_risk_rate', 0) > 30:
            alerts.append("⚠️ High churn risk: >30% of users at risk")
        
        # Check for declining activity
        if metrics.get('weekly_growth_trend', 0) < -10:
            alerts.append("📉 Weekly activity declining by >10%")
        
        # Check for system issues
        if metrics.get('total_users', 0) == 0:
            alerts.append("❌ No users found in database")
        
        return alerts
    
    @staticmethod
    def display_alerts(alerts: List[str]):
        """Display alerts in Streamlit"""
        if alerts:
            with st.container():
                st.warning("**System Alerts:**")
                for alert in alerts:
                    st.write(alert)

class ExportManager:
    """Handle data export functionality"""
    
    @staticmethod
    def prepare_export_data(
        users_df: pd.DataFrame,
        trips_df: pd.DataFrame,
        metrics: Dict[str, Any]
    ) -> Dict[str, pd.DataFrame]:
        """Prepare data for export"""
        
        export_data = {
            'users_summary': users_df,
            'trips_summary': trips_df,
            'metrics': pd.DataFrame([metrics]),
            'timestamp': datetime.now().isoformat()
        }
        
        return export_data
    
    @staticmethod
    def export_to_csv(data: pd.DataFrame, filename: str) -> bytes:
        """Export DataFrame to CSV bytes"""
        return data.to_csv(index=False).encode('utf-8')
    
    @staticmethod
    def create_download_button(data: pd.DataFrame, filename: str, label: str):
        """Create a download button in Streamlit"""
        csv = ExportManager.export_to_csv(data, filename)
        st.download_button(
            label=label,
            data=csv,
            file_name=filename,
            mime='text/csv'
        )

# Utility functions for common operations

def format_large_number(num: float) -> str:
    """Format large numbers with K, M, B suffixes"""
    if num >= 1_000_000_000:
        return f"{num/1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    else:
        return f"{num:.0f}"

def get_date_range_filter(period_days: int) -> tuple:
    """Get date range for filtering"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)
    return start_date, end_date

def calculate_period_over_period_change(
    current_value: float,
    previous_value: float
) -> Dict[str, Any]:
    """Calculate period-over-period change metrics"""
    if previous_value == 0:
        change_pct = 100 if current_value > 0 else 0
    else:
        change_pct = ((current_value - previous_value) / previous_value) * 100
    
    return {
        'current': current_value,
        'previous': previous_value,
        'change_absolute': current_value - previous_value,
        'change_percent': round(change_pct, 1),
        'trend': 'up' if change_pct > 0 else 'down' if change_pct < 0 else 'stable'
    }

def get_time_period_label(days: int) -> str:
    """Get human-readable label for time period"""
    if days == 1:
        return "Today"
    elif days == 7:
        return "Last Week"
    elif days == 30:
        return "Last Month"
    elif days == 90:
        return "Last Quarter"
    elif days == 365:
        return "Last Year"
    else:
        return f"Last {days} Days"

# Dashboard state management
class DashboardState:
    """Manage dashboard state and settings"""
    
    @staticmethod
    def init_session_state():
        """Initialize Streamlit session state"""
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        
        if 'selected_period' not in st.session_state:
            st.session_state.selected_period = 30
        
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = False
        
        if 'performance_mode' not in st.session_state:
            st.session_state.performance_mode = False
    
    @staticmethod
    def should_refresh(interval_minutes: int = 5) -> bool:
        """Check if data should be refreshed"""
        if not st.session_state.auto_refresh:
            return False
        
        time_since_refresh = datetime.now() - st.session_state.last_refresh
        return time_since_refresh.total_seconds() > (interval_minutes * 60)
    
    @staticmethod
    def update_refresh_time():
        """Update last refresh timestamp"""
        st.session_state.last_refresh = datetime.now()
