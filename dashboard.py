"""
Mileage Tracker Pro Dashboard
A comprehensive dashboard for monitoring user activity and trip statistics
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import numpy as np
from streamlit_extras.metric_cards import style_metric_cards
# Import from our custom client manager
from supabase_client import get_supabase_client, get_supabase_manager, Client

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Mileage Tracker Pro Dashboard",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        margin: 10px 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
        background-color: #f0f2f6;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Note: Supabase client initialization is now handled by supabase_client.py
# The client is automatically cached and includes retry logic, monitoring, etc.

# Data fetching functions
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_total_users(_supabase: Client):
    """Get total number of users from profiles table"""
    try:
        response = _supabase.table('profiles').select('id', count='exact').execute()
        return response.count
    except Exception as e:
        st.error(f"Error fetching user count: {str(e)}")
        return 0

@st.cache_data(ttl=300)
def get_active_users(_supabase: Client, days=30):
    """Get active users in the last N days"""
    try:
        # Use UTC for all datetime operations
        cutoff_dt = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
        cutoff_date = cutoff_dt.isoformat()
        
        # Query trips table for active users
        response = _supabase.table('trips').select('user_id').gte('created_at', cutoff_date).execute()
        
        if response.data:
            active_users = set(trip['user_id'] for trip in response.data)
            return len(active_users)
        return 0
    except Exception as e:
        st.error(f"Error fetching active users: {str(e)}")
        return 0

@st.cache_data(ttl=300)
def get_top_active_users(_supabase: Client, limit=10):
    """Get top 10 most active users with their statistics"""
    try:
        # Get all trips with user information
        trips_response = _supabase.table('trips').select('user_id, created_at, mileage, actual_distance, start_time, end_time').execute()
        
        if not trips_response.data:
            return pd.DataFrame()
        
        # Convert to DataFrame
        trips_df = pd.DataFrame(trips_response.data)
        
        # Get user information from profiles table
        users_response = _supabase.table('profiles').select('id, full_name, phone_number, subscription_tier, created_at').execute()
        users_df = pd.DataFrame(users_response.data)
        
        # Calculate duration from start_time and end_time if available (force UTC)
        if 'start_time' in trips_df.columns and 'end_time' in trips_df.columns:
            trips_df['start_time'] = pd.to_datetime(trips_df['start_time'], errors='coerce', utc=True)
            trips_df['end_time'] = pd.to_datetime(trips_df['end_time'], errors='coerce', utc=True)
            trips_df['duration'] = (trips_df['end_time'] - trips_df['start_time']).dt.total_seconds() / 60  # Duration in minutes
        else:
            trips_df['duration'] = 0
        
        # Use actual_distance if available, otherwise use mileage
        trips_df['distance'] = trips_df['actual_distance'].fillna(trips_df['mileage']).fillna(0)
        
        # Calculate statistics per user
        user_stats = trips_df.groupby('user_id').agg({
            'user_id': 'count',  # Number of trips
            'distance': 'sum',    # Total distance
            'duration': 'sum',    # Total duration
            'created_at': lambda x: (pd.Timestamp.now(tz="UTC") - pd.to_datetime(x, utc=True).max()).days  # Days since last trip
        }).rename(columns={
            'user_id': 'trip_count',
            'distance': 'total_distance',
            'duration': 'total_duration',
            'created_at': 'days_since_last_trip'
        })
        
        # Calculate usage frequency (trips per week since first trip)
        first_trip = trips_df.groupby('user_id')['created_at'].min()
        weeks_active = (pd.Timestamp.now(tz="UTC") - pd.to_datetime(first_trip, utc=True)).dt.days / 7
        user_stats['trips_per_week'] = user_stats['trip_count'] / weeks_active.clip(lower=1)
        
        # Reset index to get user_id as column
        user_stats = user_stats.reset_index()
        
        # Merge with user information
        user_stats = user_stats.merge(users_df, left_on='user_id', right_on='id', how='left')
        
        # Select and rename columns
        user_stats = user_stats[['full_name', 'phone_number', 'subscription_tier', 'trip_count', 'trips_per_week', 
                                 'total_distance', 'total_duration', 'days_since_last_trip']]
        
        # Sort by trip count and get top 10
        top_users = user_stats.nlargest(limit, 'trip_count')
        
        return top_users
        
    except Exception as e:
        st.error(f"Error fetching top active users: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_usage_patterns(_supabase: Client):
    """Get usage patterns over time"""
    try:
        # Get trips from last 30 days
        cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
        response = _supabase.table('trips').select('created_at, user_id').gte('created_at', cutoff_date).execute()
        
        if not response.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        # Normalize timestamps to UTC and then drop tz for grouping consistency
        df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
        df['date'] = df['created_at'].dt.date
        df['hour'] = df['created_at'].dt.hour
        df['day_of_week'] = df['created_at'].dt.day_name()
        
        return df
        
    except Exception as e:
        st.error(f"Error fetching usage patterns: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_trip_statistics(_supabase: Client):
    """Get overall trip statistics"""
    try:
        response = _supabase.table('trips').select('mileage, actual_distance, start_time, end_time, created_at').execute()
        
        if not response.data:
            return {}
        
        df = pd.DataFrame(response.data)
 
        # Calculate duration from start_time and end_time if available
        if 'start_time' in df.columns and 'end_time' in df.columns:
            df['start_time'] = pd.to_datetime(df['start_time'], errors='coerce', utc=True)
            df['end_time'] = pd.to_datetime(df['end_time'], errors='coerce', utc=True)
            df['duration'] = (df['end_time'] - df['start_time']).dt.total_seconds() / 60  # Duration in minutes
        else:
            df['duration'] = 0
 
        # Use actual_distance if available, otherwise use mileage
        df['distance'] = df['actual_distance'].fillna(df['mileage']).fillna(0)
 
        # Normalize created_at to UTC for comparisons
        created_at_utc = pd.to_datetime(df['created_at'], utc=True)
        now_utc = pd.Timestamp.now(tz='UTC')

        stats = {
            'total_trips': len(df),
            'total_distance': df['distance'].sum(),
            'avg_distance': df['distance'].mean(),
            'total_duration': df['duration'].sum(),
            'avg_duration': df['duration'].mean(),
            'trips_today': len(df[created_at_utc.dt.date == now_utc.date()]),
            'trips_this_week': len(df[created_at_utc >= now_utc - pd.Timedelta(days=7)]),
            'trips_this_month': len(df[created_at_utc >= now_utc - pd.Timedelta(days=30)])
        }
        
        return stats
        
    except Exception as e:
        st.error(f"Error fetching trip statistics: {str(e)}")
        return {}

@st.cache_data(ttl=300)
def get_users_at_risk(_supabase: Client, inactivity_days: int = 14):
    """Return dataframe of users whose last trip was more than inactivity_days ago.
    Also returns the count of users who never made a trip.
    """
    try:
        # Fetch trips
        trips_resp = _supabase.table('trips').select('user_id, created_at, mileage, actual_distance').execute()
        profiles_resp = _supabase.table('profiles').select('id, full_name, phone_number, subscription_tier, created_at').execute()

        profiles_df = pd.DataFrame(profiles_resp.data or [])
        if profiles_df.empty:
            return pd.DataFrame(), 0

        trips_df = pd.DataFrame(trips_resp.data or [])
        if not trips_df.empty:
            # Normalize
            trips_df['created_at'] = pd.to_datetime(trips_df['created_at'], utc=True)
            trips_df['distance'] = pd.to_numeric(trips_df.get('actual_distance'), errors='coerce').fillna(pd.to_numeric(trips_df.get('mileage'), errors='coerce')).fillna(0)
            # Aggregate by user
            agg = trips_df.groupby('user_id').agg(
                trip_count=('user_id', 'count'),
                last_trip=('created_at', 'max'),
                total_distance=('distance', 'sum')
            ).reset_index()
        else:
            agg = pd.DataFrame(columns=['user_id', 'trip_count', 'last_trip', 'total_distance'])

        # Merge with profiles
        merged = profiles_df.merge(agg, left_on='id', right_on='user_id', how='left')
        now_utc = pd.Timestamp.now(tz='UTC')
        merged['days_since_last_trip'] = (now_utc - pd.to_datetime(merged['last_trip'], utc=True)).dt.days

        # Users with no trips
        never_used_count = int(merged['last_trip'].isna().sum())

        # At risk: last trip older than threshold
        at_risk = merged[(merged['days_since_last_trip'].notna()) & (merged['days_since_last_trip'] > inactivity_days)].copy()

        # Select columns and sort
        if not at_risk.empty:
            at_risk = at_risk[['full_name', 'phone_number', 'subscription_tier', 'trip_count', 'total_distance', 'last_trip', 'days_since_last_trip']]
            at_risk['total_distance'] = at_risk['total_distance'].fillna(0).round(1)
            at_risk['trip_count'] = at_risk['trip_count'].fillna(0).astype(int)
            at_risk = at_risk.sort_values(['days_since_last_trip', 'trip_count'], ascending=[False, False])

        return at_risk, never_used_count
    except Exception as e:
        st.error(f"Error computing users at risk: {str(e)}")
        return pd.DataFrame(), 0

@st.cache_data(ttl=300)
def get_user_retention_analysis(_supabase: Client):
    """Calculate user retention metrics and cohort analysis"""
    try:
        # Try multiple table sources for user data
        users_df = pd.DataFrame()
        use_auth_table = False
        table_source = "none"
        
        # Try auth.users table first (Supabase Auth)
        try:
            users_resp = _supabase.table('auth.users').select('id, email_confirmed_at, last_sign_in_at').execute()
            users_df = pd.DataFrame(users_resp.data or [])
            use_auth_table = True
            table_source = "auth.users"
        except:
            pass
        
        # Try users table (if auth.users fails)
        if users_df.empty:
            try:
                users_resp = _supabase.table('users').select('id, email_confirmed_at, last_sign_in_at, created_at').execute()
                users_df = pd.DataFrame(users_resp.data or [])
                use_auth_table = True
                table_source = "users"
            except:
                pass
        
        # Fallback to profiles table
        if users_df.empty:
            try:
                users_resp = _supabase.table('profiles').select('id, created_at').execute()
                users_df = pd.DataFrame(users_resp.data or [])
                use_auth_table = False
                table_source = "profiles"
            except:
                pass
        
        # Fetch trip data
        trips_resp = _supabase.table('trips').select('user_id, created_at').execute()
        trips_df = pd.DataFrame(trips_resp.data or [])
        
        # Debug information
        st.write(f"Debug: Found {len(users_df)} users and {len(trips_df)} trips")
        st.write(f"Debug: Using table source: {table_source}")
        st.write(f"Debug: Using auth table: {use_auth_table}")
        if not users_df.empty:
            st.write(f"Debug: Users columns: {list(users_df.columns)}")
            if use_auth_table and 'email_confirmed_at' in users_df.columns:
                st.write(f"Debug: Sample email_confirmed_at: {users_df['email_confirmed_at'].head(3).tolist()}")
            elif 'created_at' in users_df.columns:
                st.write(f"Debug: Sample created_at: {users_df['created_at'].head(3).tolist()}")
                st.write(f"Debug: created_at dtype: {users_df['created_at'].dtype}")
                st.write(f"Debug: created_at sample values: {users_df['created_at'].head(3).values}")
        
        if not trips_df.empty:
            st.write(f"Debug: Trips columns: {list(trips_df.columns)}")
            st.write(f"Debug: Sample trip created_at: {trips_df['created_at'].head(3).tolist()}")
            st.write(f"Debug: trips created_at dtype: {trips_df['created_at'].dtype}")
        
        if users_df.empty:
            return {}, pd.DataFrame(), {}
        
        # Normalize timestamps with error handling
        try:
            if use_auth_table and 'email_confirmed_at' in users_df.columns:
                # Use email_confirmed_at as registration date
                st.write("Debug: Using email_confirmed_at for registration date")
                users_df['created_at_parsed'] = pd.to_datetime(users_df['email_confirmed_at'], errors='coerce', utc=True)
            elif 'created_at' in users_df.columns:
                # Use created_at as registration date
                st.write("Debug: Using created_at for registration date")
                users_df['created_at_parsed'] = pd.to_datetime(users_df['created_at'], errors='coerce', utc=True)
            else:
                st.error("Debug: No suitable date column found in users data")
                return {}, pd.DataFrame(), {}
            
            # Remove rows with invalid dates
            users_df = users_df.dropna(subset=['created_at_parsed'])
            st.write(f"Debug: After date parsing, {len(users_df)} users remain")
            
            # Convert to date
            users_df['registration_date'] = users_df['created_at_parsed'].dt.date
            st.write("Debug: Successfully converted to registration_date")
            
        except Exception as e:
            st.error(f"Debug: Error in user date processing: {str(e)}")
            return {}, pd.DataFrame(), {}
        
        if not trips_df.empty:
            try:
                st.write("Debug: Processing trips data...")
                trips_df['created_at_parsed'] = pd.to_datetime(trips_df['created_at'], errors='coerce', utc=True)
                trips_df = trips_df.dropna(subset=['created_at_parsed'])  # Remove rows with invalid dates
                trips_df['trip_date'] = trips_df['created_at_parsed'].dt.date
                st.write(f"Debug: Successfully processed {len(trips_df)} trips")
                
                # Get first trip date for each user
                first_trips = trips_df.groupby('user_id')['trip_date'].min().reset_index()
                first_trips.columns = ['user_id', 'first_trip_date']
                st.write(f"Debug: Found first trips for {len(first_trips)} users")
                
                # Merge with users
                user_data = users_df.merge(first_trips, left_on='id', right_on='user_id', how='left')
                st.write(f"Debug: Successfully merged user data, {len(user_data)} total records")
            except Exception as e:
                st.error(f"Debug: Error in trips processing: {str(e)}")
                return {}, pd.DataFrame(), {}
        else:
            user_data = users_df.copy()
            user_data['first_trip_date'] = None
            st.write("Debug: No trips data, using users only")
        
        # Calculate retention metrics
        try:
            st.write("Debug: Starting retention calculations...")
            now_utc = pd.Timestamp.now(tz='UTC').date()
            
            # Users who made their first trip
            users_with_trips = user_data[user_data['first_trip_date'].notna()]
            st.write(f"Debug: Found {len(users_with_trips)} users with trips")
            
            if users_with_trips.empty:
                st.write("Debug: No users with trips found")
                return {
                    'day_1_retention': 0,
                    'day_7_retention': 0,
                    'day_30_retention': 0,
                    'total_registered': len(user_data),
                    'users_with_trips': 0,
                    'activation_rate': 0
                }, pd.DataFrame(), {}
            
            # Calculate days between registration and first trip
            st.write("Debug: Calculating days to first trip...")
            # When subtracting date objects, we get timedelta, so use .apply(lambda x: x.days)
            users_with_trips['days_to_first_trip'] = (users_with_trips['first_trip_date'] - users_with_trips['registration_date']).apply(lambda x: x.days)
            st.write("Debug: Successfully calculated days to first trip")
        except Exception as e:
            st.error(f"Debug: Error in retention calculations: {str(e)}")
            return {}, pd.DataFrame(), {}
        
        # Day 1 retention (users who made first trip within 1 day)
        day_1_retention = len(users_with_trips[users_with_trips['days_to_first_trip'] <= 1]) / len(users_with_trips) * 100
        
        # Day 7 retention (users who made first trip within 7 days)
        day_7_retention = len(users_with_trips[users_with_trips['days_to_first_trip'] <= 7]) / len(users_with_trips) * 100
        
        # Day 30 retention (users who made first trip within 30 days)
        day_30_retention = len(users_with_trips[users_with_trips['days_to_first_trip'] <= 30]) / len(users_with_trips) * 100
        
        # Activation rate (users who made at least one trip)
        activation_rate = len(users_with_trips) / len(user_data) * 100
        
        retention_metrics = {
            'day_1_retention': round(day_1_retention, 1),
            'day_7_retention': round(day_7_retention, 1),
            'day_30_retention': round(day_30_retention, 1),
            'total_registered': len(user_data),
            'users_with_trips': len(users_with_trips),
            'activation_rate': round(activation_rate, 1)
        }
        
        # Cohort analysis - group by registration week
        try:
            st.write("Debug: Starting cohort analysis...")
            # Convert registration_date to datetime if it's not already
            if not pd.api.types.is_datetime64_any_dtype(user_data['registration_date']):
                user_data['registration_date'] = pd.to_datetime(user_data['registration_date'])
                st.write("Debug: Converted registration_date to datetime")
            
            # Calculate registration week (Monday of the week)
            user_data['registration_week'] = user_data['registration_date'].apply(
                lambda x: x - pd.Timedelta(days=x.weekday()) if pd.notna(x) else None
            )
            st.write("Debug: Successfully calculated registration weeks")
            
            # Also add registration_week to users_with_trips
            if not users_with_trips.empty:
                users_with_trips = users_with_trips.copy()  # Avoid SettingWithCopyWarning
                users_with_trips['registration_week'] = users_with_trips['registration_date'].apply(
                    lambda x: pd.to_datetime(x) - pd.Timedelta(days=pd.to_datetime(x).weekday()) if pd.notna(x) else None
                )
                st.write("Debug: Added registration_week to users_with_trips")
        except Exception as e:
            st.error(f"Debug: Error in cohort analysis: {str(e)}")
            return retention_metrics, pd.DataFrame(), {}
        
        cohort_data = []
        for week in sorted(user_data['registration_week'].dropna().unique()):
            week_users = user_data[user_data['registration_week'] == week]
            week_trips = users_with_trips[users_with_trips['registration_week'] == week] if not users_with_trips.empty else pd.DataFrame()
            
            cohort_data.append({
                'cohort_week': week.strftime('%Y-%m-%d') if pd.notna(week) else 'Unknown',
                'total_users': len(week_users),
                'activated_users': len(week_trips),
                'activation_rate': len(week_trips) / len(week_users) * 100 if len(week_users) > 0 else 0
            })
        
        cohort_df = pd.DataFrame(cohort_data)
        
        # Time-to-activation distribution
        activation_dist = users_with_trips['days_to_first_trip'].value_counts().sort_index()
        activation_dist = activation_dist.head(30)  # First 30 days
        
        return retention_metrics, cohort_df, activation_dist.to_dict()
        
    except Exception as e:
        st.error(f"Error calculating retention analysis: {str(e)}")
        return {}, pd.DataFrame(), {}

def format_duration(minutes):
    """Format duration from minutes to readable format"""
    if pd.isna(minutes):
        return "N/A"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"

# Revenue Analytics Functions
@st.cache_data(ttl=300)
def get_revenue_metrics(_supabase: Client):
    """Calculate revenue metrics by subscription tier"""
    try:
        # Get all profiles with subscription tiers
        profiles = _supabase.table('profiles').select('subscription_tier, created_at').execute().data
        
        if not profiles:
            return {}
        
        df = pd.DataFrame(profiles)
        
        # Define pricing (you can adjust these based on your actual pricing)
        pricing = {
            'free': 0,
            'basic': 9.99,
            'premium': 19.99,
            'pro': 39.99,
            'enterprise': 99.99
        }
        
        # Calculate metrics
        tier_counts = df['subscription_tier'].value_counts().to_dict()
        
        # Calculate MRR (Monthly Recurring Revenue)
        mrr = sum(tier_counts.get(tier.lower(), 0) * price 
                  for tier, price in pricing.items())
        
        # Calculate ARR (Annual Recurring Revenue)
        arr = mrr * 12
        
        # Calculate average revenue per user (ARPU)
        total_users = len(df)
        arpu = mrr / total_users if total_users > 0 else 0
        
        # Tier distribution
        tier_distribution = {
            tier: {
                'count': tier_counts.get(tier, 0),
                'revenue': tier_counts.get(tier, 0) * pricing.get(tier, 0),
                'percentage': (tier_counts.get(tier, 0) / total_users * 100) if total_users > 0 else 0
            }
            for tier in pricing.keys()
        }
        
        return {
            'mrr': mrr,
            'arr': arr,
            'arpu': arpu,
            'total_users': total_users,
            'tier_distribution': tier_distribution,
            'tier_counts': tier_counts
        }
    except Exception as e:
        st.error(f"Error calculating revenue metrics: {str(e)}")
        return {}

@st.cache_data(ttl=300)
def get_growth_metrics(_supabase: Client):
    """Calculate growth metrics (WoW, MoM, QoQ)"""
    try:
        # Get all profiles with creation dates
        profiles = _supabase.table('profiles').select('created_at').execute().data
        trips = _supabase.table('trips').select('created_at').execute().data
        
        if not profiles:
            return {}
        
        # Convert to DataFrame
        users_df = pd.DataFrame(profiles)
        users_df['created_at'] = pd.to_datetime(users_df['created_at'], utc=True)
        
        trips_df = pd.DataFrame(trips) if trips else pd.DataFrame()
        if not trips_df.empty:
            trips_df['created_at'] = pd.to_datetime(trips_df['created_at'], utc=True)
        
        now = pd.Timestamp.now(tz='UTC')
        
        # Calculate user growth
        def calculate_period_growth(df, days_current, days_previous):
            current_start = now - pd.Timedelta(days=days_current)
            previous_start = now - pd.Timedelta(days=days_previous)
            previous_end = now - pd.Timedelta(days=days_current)
            
            current_count = len(df[df['created_at'] >= current_start])
            previous_count = len(df[(df['created_at'] >= previous_start) & 
                                   (df['created_at'] < previous_end)])
            
            if previous_count > 0:
                growth_rate = ((current_count - previous_count) / previous_count) * 100
            else:
                growth_rate = 100 if current_count > 0 else 0
            
            return {
                'current': current_count,
                'previous': previous_count,
                'growth_rate': growth_rate
            }
        
        # Week over Week (WoW)
        wow_users = calculate_period_growth(users_df, 7, 14)
        wow_trips = calculate_period_growth(trips_df, 7, 14) if not trips_df.empty else {'current': 0, 'previous': 0, 'growth_rate': 0}
        
        # Month over Month (MoM)
        mom_users = calculate_period_growth(users_df, 30, 60)
        mom_trips = calculate_period_growth(trips_df, 30, 60) if not trips_df.empty else {'current': 0, 'previous': 0, 'growth_rate': 0}
        
        # Quarter over Quarter (QoQ)
        qoq_users = calculate_period_growth(users_df, 90, 180)
        qoq_trips = calculate_period_growth(trips_df, 90, 180) if not trips_df.empty else {'current': 0, 'previous': 0, 'growth_rate': 0}
        
        # Daily growth chart data
        users_df['date'] = users_df['created_at'].dt.date
        daily_signups = users_df.groupby('date').size().reset_index(name='signups')
        daily_signups['cumulative'] = daily_signups['signups'].cumsum()
        
        return {
            'wow': {'users': wow_users, 'trips': wow_trips},
            'mom': {'users': mom_users, 'trips': mom_trips},
            'qoq': {'users': qoq_users, 'trips': qoq_trips},
            'daily_signups': daily_signups.tail(30)  # Last 30 days
        }
    except Exception as e:
        st.error(f"Error calculating growth metrics: {str(e)}")
        return {}

@st.cache_data(ttl=60)  # Refresh every minute for live feed
def get_recent_trips(_supabase: Client, limit=20):
    """Get recent trips for live activity feed"""
    try:
        # Get recent trips with user info
        trips = _supabase.table('trips').select(
            'id, user_id, mileage, actual_distance, start_time, end_time, created_at'
        ).order('created_at', desc=True).limit(limit).execute().data
        
        if not trips:
            return pd.DataFrame()
        
        # Get user info for these trips
        user_ids = list(set(trip['user_id'] for trip in trips))
        profiles = _supabase.table('profiles').select(
            'id, full_name, subscription_tier'
        ).in_('id', user_ids).execute().data
        
        # Create user lookup
        user_lookup = {p['id']: p for p in profiles}
        
        # Enhance trip data with user info
        enhanced_trips = []
        for trip in trips:
            user_info = user_lookup.get(trip['user_id'], {})
            
            # Calculate duration if start and end times exist
            duration = None
            if trip.get('start_time') and trip.get('end_time'):
                start = pd.to_datetime(trip['start_time'])
                end = pd.to_datetime(trip['end_time'])
                duration = (end - start).total_seconds() / 60  # in minutes
            
            enhanced_trips.append({
                'time': pd.to_datetime(trip['created_at']),
                'user': user_info.get('full_name', 'Unknown User'),
                'tier': user_info.get('subscription_tier', 'free'),
                'distance': trip.get('actual_distance') or trip.get('mileage', 0),
                'duration': duration,
                'trip_id': trip['id']
            })
        
        return pd.DataFrame(enhanced_trips)
    except Exception as e:
        st.error(f"Error fetching recent trips: {str(e)}")
        return pd.DataFrame()

def main():
    # Header
    st.title("🚗 Mileage Tracker Pro Dashboard")
    st.markdown("Real-time insights into user activity and trip statistics")
    
    # Initialize Supabase with enhanced client
    try:
        supabase = get_supabase_client()
        manager = get_supabase_manager()
    except Exception as e:
        st.error(f"⚠️ Failed to connect to database: {str(e)}")
        st.info("Please check your .env file and ensure your Supabase credentials are correct.")
        st.stop()
    
    # Sidebar for filters
    with st.sidebar:
        st.header("⚙️ Dashboard Settings")
        
        # Connection Status
        with st.expander("🔌 Connection Status", expanded=False):
            metrics = manager.get_metrics()
            conn_status = metrics.get('connection_status', {})
            
            if conn_status.get('is_healthy', False):
                st.success("✅ Database Connected")
            else:
                st.error("❌ Database Disconnected")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Queries", metrics.get('total_queries', 0))
                st.metric("Success Rate", f"{metrics.get('success_rate', 0):.1f}%")
            with col2:
                st.metric("Errors", metrics.get('failed_queries', 0))
                uptime = metrics.get('uptime_seconds', 0)
                st.metric("Uptime", f"{int(uptime // 60)}m")
        
        st.markdown("---")
        
        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        
        # Time range filter
        st.subheader("📅 Time Range")
        time_range = st.selectbox(
            "Select period for active users",
            options=[7, 14, 30, 60, 90],
            format_func=lambda x: f"Last {x} days",
            index=2
        )
        
        st.markdown("---")
        
        # Auto-refresh option
        st.subheader("🔄 Auto-Refresh")
        auto_refresh = st.checkbox("Enable auto-refresh (5 min)")
        
        if auto_refresh:
            st.info("Dashboard will refresh every 5 minutes")
        
        # Last updated time
        st.markdown("---")
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Main content area with tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Overview", "💰 Revenue", "📈 Growth", "🔴 Live Feed", "👥 Users", "📈 Retention"])
    
    with tab1:
        # Fetch key metrics
        total_users = get_total_users(supabase)
        active_users = get_active_users(supabase, time_range)
        trip_stats = get_trip_statistics(supabase)
        
        # Key metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Total Users",
                value=f"{total_users:,}",
                delta=f"{active_users} active"
            )
        
        with col2:
            st.metric(
                label="Active Users",
                value=f"{active_users:,}",
                delta=f"{(active_users/total_users*100):.1f}%" if total_users > 0 else "0%"
            )
        
        with col3:
            st.metric(
                label="Total Trips",
                value=f"{trip_stats.get('total_trips', 0):,}",
                delta=f"+{trip_stats.get('trips_today', 0)} today"
            )
        
        with col4:
            avg_trips_per_user = trip_stats.get('total_trips', 0) / total_users if total_users > 0 else 0
            st.metric(
                label="Avg Trips/User",
                value=f"{avg_trips_per_user:.1f}",
                delta=f"{trip_stats.get('trips_this_week', 0)} this week"
            )
        
        style_metric_cards()
        
        st.markdown("---")
        
        # Top Active Users Section
        st.subheader("🏆 Top 10 Most Active Users")
        
        top_users = get_top_active_users(supabase, 10)
        
        if not top_users.empty:
            # Create two columns for the table and chart
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Format the dataframe for display
                display_df = top_users.copy()
                display_df['trips_per_week'] = display_df['trips_per_week'].round(1)
                display_df['total_distance'] = display_df['total_distance'].round(1)
                display_df['total_duration'] = display_df['total_duration'].apply(format_duration)
                display_df['days_since_last_trip'] = display_df['days_since_last_trip'].astype(int)
                
                # Rename columns for better display
                display_df.columns = ['Name', 'Phone', 'Subscription', 'Total Trips', 'Trips/Week', 
                                     'Total Distance (mi)', 'Total Duration', 'Days Since Last Trip']
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Phone": st.column_config.TextColumn(width="medium"),
                        "Subscription": st.column_config.TextColumn(width="small"),
                        "Total Trips": st.column_config.NumberColumn(format="%d"),
                        "Trips/Week": st.column_config.NumberColumn(format="%.1f"),
                        "Total Distance (mi)": st.column_config.NumberColumn(format="%.1f"),
                        "Days Since Last Trip": st.column_config.NumberColumn(format="%d")
                    }
                )
            
            with col2:
                # Create a bar chart of top users
                fig = px.bar(
                    top_users.head(5),
                    x='trip_count',
                    y='full_name',
                    orientation='h',
                    title="Top 5 Users by Trip Count",
                    labels={'trip_count': 'Number of Trips', 'full_name': 'User'},
                    color='trip_count',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No user data available")
    
    # Revenue Analytics Tab
    with tab2:
        st.subheader("💰 Revenue & Subscription Analytics")
        
        revenue_metrics = get_revenue_metrics(supabase)
        
        if revenue_metrics:
            # Key revenue metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Monthly Recurring Revenue (MRR)",
                    f"${revenue_metrics.get('mrr', 0):,.2f}",
                    help="Total monthly revenue from all subscriptions"
                )
            
            with col2:
                st.metric(
                    "Annual Recurring Revenue (ARR)", 
                    f"${revenue_metrics.get('arr', 0):,.2f}",
                    help="Projected annual revenue (MRR × 12)"
                )
            
            with col3:
                st.metric(
                    "Average Revenue Per User (ARPU)",
                    f"${revenue_metrics.get('arpu', 0):.2f}",
                    help="Average monthly revenue per user"
                )
            
            with col4:
                st.metric(
                    "Paying Users",
                    f"{sum(1 for tier, data in revenue_metrics.get('tier_distribution', {}).items() if tier != 'free' and data['count'] > 0):,}",
                    f"{(sum(1 for tier, data in revenue_metrics.get('tier_distribution', {}).items() if tier != 'free' and data['count'] > 0) / revenue_metrics.get('total_users', 1) * 100):.1f}%"
                )
            
            st.markdown("---")
            
            # Subscription tier distribution
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Subscription Tier Distribution")
                
                tier_data = []
                for tier, data in revenue_metrics.get('tier_distribution', {}).items():
                    if data['count'] > 0:
                        tier_data.append({
                            'Tier': tier.capitalize(),
                            'Users': data['count'],
                            'Revenue': data['revenue'],
                            'Percentage': data['percentage']
                        })
                
                if tier_data:
                    tier_df = pd.DataFrame(tier_data)
                    
                    # Pie chart of user distribution
                    fig = px.pie(
                        tier_df,
                        values='Users',
                        names='Tier',
                        title="Users by Subscription Tier",
                        color_discrete_map={
                            'Free': '#gray',
                            'Basic': '#blue',
                            'Premium': '#green',
                            'Pro': '#purple',
                            'Enterprise': '#gold'
                        }
                    )
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### Revenue by Tier")
                
                if tier_data:
                    # Filter out free tier for revenue chart
                    revenue_df = pd.DataFrame([t for t in tier_data if t['Revenue'] > 0])
                    
                    if not revenue_df.empty:
                        fig = px.bar(
                            revenue_df,
                            x='Tier',
                            y='Revenue',
                            title="Monthly Revenue by Tier",
                            color='Revenue',
                            color_continuous_scale='Greens',
                            text='Revenue'
                        )
                        fig.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
                        fig.update_layout(showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No revenue data available (all users on free tier)")
            
            # Detailed tier breakdown table
            st.markdown("#### Detailed Tier Breakdown")
            if tier_data:
                detailed_df = pd.DataFrame(tier_data)
                detailed_df['Revenue'] = detailed_df['Revenue'].apply(lambda x: f"${x:,.2f}")
                detailed_df['Percentage'] = detailed_df['Percentage'].apply(lambda x: f"{x:.1f}%")
                
                st.dataframe(
                    detailed_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Users": st.column_config.NumberColumn(format="%d"),
                        "Revenue": st.column_config.TextColumn(),
                        "Percentage": st.column_config.TextColumn()
                    }
                )
        else:
            st.info("No revenue data available")
    
    # Growth Metrics Tab
    with tab3:
        st.subheader("📈 Growth Metrics")
        
        growth_metrics = get_growth_metrics(supabase)
        
        if growth_metrics:
            # Growth rate cards
            st.markdown("#### User Growth")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                wow = growth_metrics.get('wow', {}).get('users', {})
                delta_value = wow.get('growth_rate', 0)
                st.metric(
                    "Week over Week (WoW)",
                    f"{wow.get('current', 0)} users",
                    delta=f"{delta_value:+.1f}%" if delta_value != 0 else "0%",
                    delta_color="normal" if delta_value >= 0 else "inverse"
                )
            
            with col2:
                mom = growth_metrics.get('mom', {}).get('users', {})
                delta_value = mom.get('growth_rate', 0)
                st.metric(
                    "Month over Month (MoM)",
                    f"{mom.get('current', 0)} users",
                    delta=f"{delta_value:+.1f}%" if delta_value != 0 else "0%",
                    delta_color="normal" if delta_value >= 0 else "inverse"
                )
            
            with col3:
                qoq = growth_metrics.get('qoq', {}).get('users', {})
                delta_value = qoq.get('growth_rate', 0)
                st.metric(
                    "Quarter over Quarter (QoQ)",
                    f"{qoq.get('current', 0)} users",
                    delta=f"{delta_value:+.1f}%" if delta_value != 0 else "0%",
                    delta_color="normal" if delta_value >= 0 else "inverse"
                )
            
            st.markdown("#### Trip Growth")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                wow = growth_metrics.get('wow', {}).get('trips', {})
                delta_value = wow.get('growth_rate', 0)
                st.metric(
                    "Week over Week (WoW)",
                    f"{wow.get('current', 0)} trips",
                    delta=f"{delta_value:+.1f}%" if delta_value != 0 else "0%",
                    delta_color="normal" if delta_value >= 0 else "inverse"
                )
            
            with col2:
                mom = growth_metrics.get('mom', {}).get('trips', {})
                delta_value = mom.get('growth_rate', 0)
                st.metric(
                    "Month over Month (MoM)",
                    f"{mom.get('current', 0)} trips",
                    delta=f"{delta_value:+.1f}%" if delta_value != 0 else "0%",
                    delta_color="normal" if delta_value >= 0 else "inverse"
                )
            
            with col3:
                qoq = growth_metrics.get('qoq', {}).get('trips', {})
                delta_value = qoq.get('growth_rate', 0)
                st.metric(
                    "Quarter over Quarter (QoQ)",
                    f"{qoq.get('current', 0)} trips",
                    delta=f"{delta_value:+.1f}%" if delta_value != 0 else "0%",
                    delta_color="normal" if delta_value >= 0 else "inverse"
                )
            
            st.markdown("---")
            
            # Growth charts
            daily_signups = growth_metrics.get('daily_signups')
            if daily_signups is not None and not daily_signups.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Daily signups chart
                    fig = px.bar(
                        daily_signups,
                        x='date',
                        y='signups',
                        title="Daily New User Signups (Last 30 Days)",
                        labels={'signups': 'New Users', 'date': 'Date'}
                    )
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Cumulative growth chart
                    fig = px.line(
                        daily_signups,
                        x='date',
                        y='cumulative',
                        title="Cumulative User Growth",
                        labels={'cumulative': 'Total Users', 'date': 'Date'},
                        markers=True
                    )
                    fig.update_traces(fill='tozeroy')
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No growth data available")
    
    # Live Activity Feed Tab
    with tab4:
        st.subheader("🔴 Live Trip Activity Feed")
        
        # Auto-refresh settings
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown("**Real-time trip monitoring** - Updates every minute")
        with col2:
            if st.button("🔄 Refresh Now"):
                st.cache_data.clear()
                st.rerun()
        with col3:
            show_count = st.selectbox("Show last", [10, 20, 50, 100], index=1)
        
        # Get recent trips
        recent_trips = get_recent_trips(supabase, limit=show_count)
        
        if not recent_trips.empty:
            # Activity metrics
            col1, col2, col3, col4 = st.columns(4)
            
            # Calculate metrics for last hour
            now = pd.Timestamp.now(tz='UTC')
            last_hour = recent_trips[recent_trips['time'] >= (now - pd.Timedelta(hours=1))]
            
            with col1:
                st.metric("Trips (Last Hour)", len(last_hour))
            with col2:
                unique_users = recent_trips['user'].nunique()
                st.metric("Active Users", unique_users)
            with col3:
                avg_distance = recent_trips['distance'].mean()
                st.metric("Avg Distance", f"{avg_distance:.1f} mi")
            with col4:
                if recent_trips['duration'].notna().any():
                    avg_duration = recent_trips['duration'].mean()
                    st.metric("Avg Duration", f"{avg_duration:.0f} min")
                else:
                    st.metric("Avg Duration", "N/A")
            
            st.markdown("---")
            
            # Live feed display
            st.markdown("#### Recent Trips")
            
            # Format the dataframe for display
            display_df = recent_trips.copy()
            display_df['time'] = display_df['time'].dt.strftime('%H:%M:%S')
            display_df['distance'] = display_df['distance'].round(1).astype(str) + ' mi'
            display_df['duration'] = display_df['duration'].apply(
                lambda x: f"{x:.0f} min" if pd.notna(x) else "N/A"
            )
            
            # Add tier badges
            tier_colors = {
                'free': '⚪',
                'basic': '🔵',
                'premium': '🟢',
                'pro': '🟣',
                'enterprise': '🟡'
            }
            display_df['tier'] = display_df['tier'].apply(
                lambda x: f"{tier_colors.get(x, '⚪')} {x.capitalize()}"
            )
            
            # Rename columns
            display_df = display_df[['time', 'user', 'tier', 'distance', 'duration']]
            display_df.columns = ['Time', 'User', 'Tier', 'Distance', 'Duration']
            
            # Display as a table with custom styling
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Time": st.column_config.TextColumn(width="small"),
                    "User": st.column_config.TextColumn(width="medium"),
                    "Tier": st.column_config.TextColumn(width="small"),
                    "Distance": st.column_config.TextColumn(width="small"),
                    "Duration": st.column_config.TextColumn(width="small")
                }
            )
            
            # Activity timeline
            st.markdown("#### Activity Timeline")
            
            # Group trips by hour for the timeline
            recent_trips['hour'] = pd.to_datetime(recent_trips['time']).dt.floor('H')
            hourly_trips = recent_trips.groupby('hour').size().reset_index(name='trips')
            
            fig = px.line(
                hourly_trips,
                x='hour',
                y='trips',
                title="Trip Activity Over Time",
                labels={'trips': 'Number of Trips', 'hour': 'Time'},
                markers=True
            )
            fig.update_traces(fill='tozeroy')
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No recent trip activity")
    
    with tab5:
        st.subheader("👥 Detailed User Analytics")
        
        # User growth metrics
        col1, col2 = st.columns(2)
        
        with col1:
            # User activity distribution
            usage_data = get_usage_patterns(supabase)
            if not usage_data.empty:
                daily_active = usage_data.groupby('date')['user_id'].nunique().reset_index()
                daily_active.columns = ['Date', 'Active Users']
                
                fig = px.line(
                    daily_active,
                    x='Date',
                    y='Active Users',
                    title='Daily Active Users (Last 30 Days)',
                    markers=True
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # User engagement heatmap
            if not usage_data.empty:
                hourly_usage = usage_data.groupby(['day_of_week', 'hour']).size().reset_index(name='trips')
                
                # Create pivot table for heatmap
                heatmap_data = hourly_usage.pivot(index='hour', columns='day_of_week', values='trips').fillna(0)
                
                # Reorder days
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                heatmap_data = heatmap_data.reindex(columns=[d for d in day_order if d in heatmap_data.columns])
                
                fig = go.Figure(data=go.Heatmap(
                    z=heatmap_data.values,
                    x=heatmap_data.columns,
                    y=heatmap_data.index,
                    colorscale='Blues',
                    text=heatmap_data.values,
                    texttemplate='%{text}',
                    textfont={"size": 10}
                ))
                
                fig.update_layout(
                    title='Usage Heatmap by Day and Hour',
                    xaxis_title='Day of Week',
                    yaxis_title='Hour of Day',
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # User retention metrics
        st.markdown("---")
        st.subheader("📊 User Engagement Metrics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            engagement_rate = (active_users / total_users * 100) if total_users > 0 else 0
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=engagement_rate,
                title={'text': f"Engagement Rate ({time_range} days)"},
                domain={'x': [0, 1], 'y': [0, 1]},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 25], 'color': "lightgray"},
                        {'range': [25, 50], 'color': "gray"},
                        {'range': [50, 75], 'color': "lightblue"},
                        {'range': [75, 100], 'color': "blue"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Average trips per active user
            avg_trips_active = trip_stats.get('trips_this_month', 0) / active_users if active_users > 0 else 0
            st.metric(
                "Avg Trips per Active User",
                f"{avg_trips_active:.1f}",
                f"Last {time_range} days"
            )
            
            # Users at Risk metric (inactivity threshold adjustable below)
            risk_df, never_used_count = get_users_at_risk(supabase, 14)
            st.metric(
                "Users at Risk",
                len(risk_df),
                "Inactive > 14 days",
                delta_color="inverse"
            )
        
        with col3:
            # Power users (>10 trips)
            if not top_users.empty:
                power_users = len(top_users[top_users['trip_count'] > 10])
                st.metric(
                    "Power Users",
                    power_users,
                    ">10 trips"
                )
            
            # New vs returning ratio
            st.metric(
                "Activity Score",
                f"{min(100, int(engagement_rate * 1.5))}/100",
                "Overall health"
            )

        # Users at Risk table
        st.markdown("---")
        st.subheader("⚠️ Users at Risk")
        risk_threshold = st.slider("Inactivity threshold (days)", min_value=7, max_value=60, value=14, step=1)
        risk_df, never_used_count = get_users_at_risk(supabase, risk_threshold)
        st.caption(f"Never-used users (no trips): {never_used_count}")
        
        if not risk_df.empty:
            display_risk = risk_df.copy()
            display_risk['last_trip'] = pd.to_datetime(display_risk['last_trip']).dt.strftime('%Y-%m-%d %H:%M UTC')
            display_risk.rename(columns={
                'full_name': 'Name',
                'phone_number': 'Phone',
                'subscription_tier': 'Subscription',
                'trip_count': 'Trips',
                'total_distance': 'Total Distance (mi)',
                'days_since_last_trip': 'Days Since Last Trip',
                'last_trip': 'Last Trip'
            }, inplace=True)
            st.dataframe(display_risk, use_container_width=True, hide_index=True)
            # Download
            csv = display_risk.to_csv(index=False).encode('utf-8')
            st.download_button("Download at-risk users (CSV)", data=csv, file_name=f"users_at_risk_{risk_threshold}d.csv", mime="text/csv")
        else:
            st.info("No users meet the at-risk criteria for the selected threshold.")
        
        # Trip statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Distance",
                f"{trip_stats.get('total_distance', 0):,.0f} mi",
                f"Avg: {trip_stats.get('avg_distance', 0):.1f} mi"
            )
        
        with col2:
            total_hours = trip_stats.get('total_duration', 0) / 60
            st.metric(
                "Total Duration",
                f"{total_hours:,.0f} hrs",
                f"Avg: {format_duration(trip_stats.get('avg_duration', 0))}"
            )
        
        with col3:
            trips_per_day = trip_stats.get('total_trips', 0) / 30
            st.metric(
                "Trips per Day",
                f"{trips_per_day:.1f}",
                f"Total: {trip_stats.get('total_trips', 0):,}"
            )
        
        with col4:
            if trip_stats.get('avg_duration', 0) > 0:
                avg_speed = trip_stats.get('avg_distance', 0) / (trip_stats.get('avg_duration', 0) / 60)
            else:
                avg_speed = 0
            st.metric(
                "Avg Speed",
                f"{avg_speed:.1f} mph",
                "Per trip average"
            )
        
        st.markdown("---")
        
        # Trip distribution charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Trips by day of week
            if not usage_data.empty:
                trips_by_day = usage_data['day_of_week'].value_counts().reset_index()
                trips_by_day.columns = ['Day', 'Trips']
                
                # Order days properly
                day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                trips_by_day['Day'] = pd.Categorical(trips_by_day['Day'], categories=day_order, ordered=True)
                trips_by_day = trips_by_day.sort_values('Day')
                
                fig = px.bar(
                    trips_by_day,
                    x='Day',
                    y='Trips',
                    title='Trips by Day of Week',
                    color='Trips',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Trips by hour of day
            if not usage_data.empty:
                trips_by_hour = usage_data['hour'].value_counts().sort_index().reset_index()
                trips_by_hour.columns = ['Hour', 'Trips']
                
                fig = px.area(
                    trips_by_hour,
                    x='Hour',
                    y='Trips',
                    title='Trips by Hour of Day'
                )
                fig.update_traces(fill='tozeroy')
                fig.update_layout(height=350)
                fig.update_xaxes(tickmode='linear', tick0=0, dtick=2)
                st.plotly_chart(fig, use_container_width=True)
    
    with tab6:
        st.subheader("📈 User Retention Analysis")
        
        # Get retention data
        retention_metrics, cohort_df, activation_dist = get_user_retention_analysis(supabase)
        
        if not retention_metrics:
            st.warning("No retention data available. Please ensure you have user registration and trip data.")
            return
        
        # Key retention metrics
        st.markdown("### 🎯 Key Retention Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Day 1 Retention",
                f"{retention_metrics.get('day_1_retention', 0):.1f}%",
                "Users who made first trip within 1 day"
            )
        
        with col2:
            st.metric(
                "Day 7 Retention", 
                f"{retention_metrics.get('day_7_retention', 0):.1f}%",
                "Users who made first trip within 7 days"
            )
        
        with col3:
            st.metric(
                "Day 30 Retention",
                f"{retention_metrics.get('day_30_retention', 0):.1f}%",
                "Users who made first trip within 30 days"
            )
        
        with col4:
            st.metric(
                "Activation Rate",
                f"{retention_metrics.get('activation_rate', 0):.1f}%",
                f"{retention_metrics.get('users_with_trips', 0)}/{retention_metrics.get('total_registered', 0)} users"
            )
        
        # Retention funnel visualization
        st.markdown("---")
        st.subheader("🔄 User Activation Funnel")
        
        funnel_data = {
            'Stage': ['Registered Users', 'Day 1 Active', 'Day 7 Active', 'Day 30 Active'],
            'Count': [
                retention_metrics.get('total_registered', 0),
                int(retention_metrics.get('total_registered', 0) * retention_metrics.get('day_1_retention', 0) / 100),
                int(retention_metrics.get('total_registered', 0) * retention_metrics.get('day_7_retention', 0) / 100),
                int(retention_metrics.get('total_registered', 0) * retention_metrics.get('day_30_retention', 0) / 100)
            ],
            'Percentage': [
                100.0,
                retention_metrics.get('day_1_retention', 0),
                retention_metrics.get('day_7_retention', 0),
                retention_metrics.get('day_30_retention', 0)
            ]
        }
        
        funnel_df = pd.DataFrame(funnel_data)
        
        fig = go.Figure(go.Funnel(
            y=funnel_df['Stage'],
            x=funnel_df['Count'],
            textinfo="value+percent initial",
            marker=dict(color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
        ))
        
        fig.update_layout(
            title="User Activation Funnel",
            height=400,
            margin=dict(l=100, r=50, t=50, b=50)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Time to activation distribution
        if activation_dist:
            st.markdown("---")
            st.subheader("⏱️ Time to First Trip Distribution")
            
            days = list(activation_dist.keys())
            counts = list(activation_dist.values())
            
            fig = go.Figure(data=[
                go.Bar(x=days, y=counts, marker_color='lightblue')
            ])
            
            fig.update_layout(
                title="Days Between Registration and First Trip",
                xaxis_title="Days",
                yaxis_title="Number of Users",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Cohort analysis
        if not cohort_df.empty:
            st.markdown("---")
            st.subheader("📊 Weekly Cohort Analysis")
            
            # Display cohort table
            display_cohort = cohort_df.copy()
            display_cohort['activation_rate'] = display_cohort['activation_rate'].round(1)
            display_cohort.rename(columns={
                'cohort_week': 'Registration Week',
                'total_users': 'Total Users',
                'activated_users': 'Activated Users',
                'activation_rate': 'Activation Rate (%)'
            }, inplace=True)
            
            st.dataframe(display_cohort, use_container_width=True, hide_index=True)
            
            # Cohort visualization
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=cohort_df['cohort_week'],
                y=cohort_df['total_users'],
                mode='lines+markers',
                name='Total Users',
                line=dict(color='blue', width=3),
                marker=dict(size=8)
            ))
            
            fig.add_trace(go.Scatter(
                x=cohort_df['cohort_week'],
                y=cohort_df['activated_users'],
                mode='lines+markers',
                name='Activated Users',
                line=dict(color='green', width=3),
                marker=dict(size=8)
            ))
            
            fig.update_layout(
                title="User Registration and Activation by Week",
                xaxis_title="Registration Week",
                yaxis_title="Number of Users",
                height=400,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Retention insights and recommendations
        st.markdown("---")
        st.subheader("💡 Retention Insights & Recommendations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📈 Current Performance")
            
            day_1 = retention_metrics.get('day_1_retention', 0)
            day_7 = retention_metrics.get('day_7_retention', 0)
            day_30 = retention_metrics.get('day_30_retention', 0)
            activation = retention_metrics.get('activation_rate', 0)
            
            if day_1 < 30:
                st.warning(f"**Low Day 1 Retention ({day_1:.1f}%)** - Users aren't engaging immediately after registration")
            elif day_1 > 60:
                st.success(f"**Strong Day 1 Retention ({day_1:.1f}%)** - Great first impression!")
            else:
                st.info(f"**Moderate Day 1 Retention ({day_1:.1f}%)** - Room for improvement")
            
            if activation < 50:
                st.warning(f"**Low Activation Rate ({activation:.1f}%)** - Many users never make their first trip")
            elif activation > 80:
                st.success(f"**High Activation Rate ({activation:.1f}%)** - Excellent user onboarding!")
            else:
                st.info(f"**Moderate Activation Rate ({activation:.1f}%)** - Good foundation to build on")
        
        with col2:
            st.markdown("### 🎯 Actionable Recommendations")
            
            if day_1 < 40:
                st.markdown("""
                **🚀 Improve Day 1 Retention:**
                - Send welcome email with app tutorial
                - Offer first-trip incentives
                - Simplify onboarding process
                - Add progress indicators
                """)
            
            if activation < 60:
                st.markdown("""
                **📱 Boost Activation:**
                - Create guided first trip experience
                - Implement push notifications
                - Add gamification elements
                - Provide clear value proposition
                """)
            
            if day_7 < day_1 * 0.8:
                st.markdown("""
                **🔄 Maintain Engagement:**
                - Send follow-up messages
                - Create habit-forming features
                - Implement streak tracking
                - Offer weekly challenges
                """)
        
        # Download retention report
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Download Retention Report", use_container_width=True):
                # Create comprehensive retention report
                report_data = {
                    'Metric': ['Total Registered Users', 'Users with Trips', 'Activation Rate (%)', 
                              'Day 1 Retention (%)', 'Day 7 Retention (%)', 'Day 30 Retention (%)'],
                    'Value': [
                        retention_metrics.get('total_registered', 0),
                        retention_metrics.get('users_with_trips', 0),
                        retention_metrics.get('activation_rate', 0),
                        retention_metrics.get('day_1_retention', 0),
                        retention_metrics.get('day_7_retention', 0),
                        retention_metrics.get('day_30_retention', 0)
                    ]
                }
                
                report_df = pd.DataFrame(report_data)
                csv = report_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download CSV",
                    data=csv,
                    file_name=f"retention_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        
        with col2:
            st.info("💡 **Pro Tip:** Monitor these metrics weekly to track retention improvements and identify trends early.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray;'>
            <small>Mileage Tracker Pro Dashboard v1.0 | Data refreshes every 5 minutes | 
            Built with Streamlit & Supabase</small>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
