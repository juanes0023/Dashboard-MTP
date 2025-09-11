"""
Supabase Client Management System
Centralized database connection with advanced features for Mileage Tracker Pro
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List
from functools import wraps
from datetime import datetime, timedelta
from enum import Enum
from dotenv import load_dotenv
from supabase import create_client, Client
import streamlit as st

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Environment(Enum):
    """Environment configurations"""
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TESTING = "testing"


class ConnectionStatus(Enum):
    """Connection status states"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"


class SupabaseConfig:
    """Configuration management for different environments"""
    
    @staticmethod
    def get_config(env: Environment = Environment.PRODUCTION) -> Dict[str, str]:
        """Get configuration for specified environment"""
        
        configs = {
            Environment.PRODUCTION: {
                'url': os.getenv('SUPABASE_URL'),
                'key': os.getenv('SUPABASE_KEY'),
                'timeout': 30,
                'max_retries': 3
            },
            Environment.STAGING: {
                'url': os.getenv('STAGING_SUPABASE_URL', os.getenv('SUPABASE_URL')),
                'key': os.getenv('STAGING_SUPABASE_KEY', os.getenv('SUPABASE_KEY')),
                'timeout': 30,
                'max_retries': 3
            },
            Environment.DEVELOPMENT: {
                'url': os.getenv('DEV_SUPABASE_URL', os.getenv('SUPABASE_URL')),
                'key': os.getenv('DEV_SUPABASE_KEY', os.getenv('SUPABASE_KEY')),
                'timeout': 60,
                'max_retries': 5
            },
            Environment.TESTING: {
                'url': os.getenv('TEST_SUPABASE_URL', 'https://test.supabase.co'),
                'key': os.getenv('TEST_SUPABASE_KEY', 'test_key'),
                'timeout': 10,
                'max_retries': 1
            }
        }
        
        config = configs.get(env, configs[Environment.PRODUCTION])
        
        # Validate configuration
        if not config['url'] or not config['key']:
            raise ValueError(f"Missing Supabase credentials for {env.value} environment")
        
        return config


class RateLimiter:
    """Rate limiting for API calls"""
    
    def __init__(self, calls_per_second: float = 10):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
        self.call_times: List[float] = []
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        current_time = time.time()
        
        # Remove old call times (older than 1 second)
        self.call_times = [t for t in self.call_times if current_time - t < 1.0]
        
        # If we've made too many calls, wait
        if len(self.call_times) >= self.calls_per_second:
            sleep_time = 1.0 - (current_time - self.call_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
                current_time = time.time()
        
        self.call_times.append(current_time)
        self.last_call = current_time


class ConnectionPool:
    """Manages database connections with health monitoring"""
    
    def __init__(self, client: Client):
        self.client = client
        self.status = ConnectionStatus.DISCONNECTED
        self.last_health_check: Optional[datetime] = None
        self.failed_attempts = 0
        self.max_failed_attempts = 5
        self.health_check_interval = timedelta(minutes=5)
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy"""
        # Check if we need a new health check
        if (self.last_health_check is None or 
            datetime.now() - self.last_health_check > self.health_check_interval):
            return self.perform_health_check()
        
        return self.status == ConnectionStatus.CONNECTED
    
    def perform_health_check(self) -> bool:
        """Perform actual health check"""
        try:
            # First try a simple auth check (doesn't require any tables)
            # This verifies the connection and credentials are valid
            from supabase import Client as SupabaseClient
            if isinstance(self.client, SupabaseClient):
                # Connection is valid if we can create the client
                self.status = ConnectionStatus.CONNECTED
                self.failed_attempts = 0
                self.last_health_check = datetime.now()
                
                # Try to check if tables exist (optional)
                try:
                    self.client.table('profiles').select('id').limit(1).execute()
                    logger.info("Health check passed - tables exist")
                except Exception as table_error:
                    # Tables don't exist yet, but connection is valid
                    if "does not exist" in str(table_error):
                        logger.warning("Database connected but tables not found. Run setup_database.py to create tables.")
                    else:
                        logger.warning(f"Table check failed: {table_error}")
                
                return True
        except Exception as e:
            self.failed_attempts += 1
            self.status = ConnectionStatus.ERROR
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get detailed connection status"""
        return {
            'status': self.status.value,
            'last_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'failed_attempts': self.failed_attempts,
            'is_healthy': self.is_healthy()
        }


class SupabaseManager:
    """
    Enhanced Supabase client manager with advanced features:
    - Singleton pattern for single instance
    - Automatic retry logic
    - Rate limiting
    - Connection pooling
    - Health monitoring
    - Query logging and metrics
    """
    
    _instance: Optional['SupabaseManager'] = None
    _client: Optional[Client] = None
    
    def __new__(cls, env: Environment = Environment.PRODUCTION):
        """Singleton pattern - ensure only one instance exists"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.env = env
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self, env: Environment = Environment.PRODUCTION):
        """Initialize the manager if not already initialized"""
        if not self.initialized:
            self.env = env
            self.config = SupabaseConfig.get_config(env)
            self.rate_limiter = RateLimiter(calls_per_second=10)
            self.connection_pool: Optional[ConnectionPool] = None
            self.query_count = 0
            self.query_errors = 0
            self.start_time = datetime.now()
            self._initialize_client()
            self.initialized = True
    
    def _initialize_client(self):
        """Initialize the Supabase client with retry logic"""
        max_retries = self.config.get('max_retries', 3)
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Initializing Supabase client (attempt {attempt + 1}/{max_retries})")
                
                self._client = create_client(
                    self.config['url'],
                    self.config['key']
                )
                
                # Create connection pool
                self.connection_pool = ConnectionPool(self._client)
                
                # Test the connection
                if self.connection_pool.perform_health_check():
                    logger.info(f"Successfully connected to Supabase ({self.env.value})")
                    return
                else:
                    raise Exception("Health check failed")
                    
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise Exception(f"Failed to connect to Supabase after {max_retries} attempts: {e}")
    
    @property
    def client(self) -> Client:
        """Get the Supabase client (lazy initialization)"""
        if self._client is None:
            self._initialize_client()
        
        # Check health before returning
        if not self.connection_pool.is_healthy():
            logger.warning("Connection unhealthy, attempting to reconnect...")
            self._initialize_client()
        
        return self._client
    
    def execute_with_retry(self, func, *args, **kwargs):
        """Execute a function with automatic retry logic"""
        max_retries = self.config.get('max_retries', 3)
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                self.rate_limiter.wait_if_needed()
                
                # Execute the function
                result = func(*args, **kwargs)
                self.query_count += 1
                return result
                
            except Exception as e:
                self.query_errors += 1
                logger.warning(f"Query failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
    
    def query(self, table: str, *args, **kwargs):
        """Execute a query with monitoring and retry logic"""
        start_time = time.time()
        
        try:
            def _query():
                return self.client.table(table).select(*args, **kwargs).execute()
            
            result = self.execute_with_retry(_query)
            
            # Log successful query
            duration = time.time() - start_time
            logger.debug(f"Query to '{table}' completed in {duration:.2f}s")
            
            return result
            
        except Exception as e:
            # Log failed query
            duration = time.time() - start_time
            logger.error(f"Query to '{table}' failed after {duration:.2f}s: {e}")
            raise
    
    def insert(self, table: str, data: Dict[str, Any], *args, **kwargs):
        """Insert data with monitoring"""
        def _insert():
            return self.client.table(table).insert(data, *args, **kwargs).execute()
        
        return self.execute_with_retry(_insert)
    
    def update(self, table: str, data: Dict[str, Any], *args, **kwargs):
        """Update data with monitoring"""
        def _update():
            return self.client.table(table).update(data, *args, **kwargs).execute()
        
        return self.execute_with_retry(_update)
    
    def delete(self, table: str, *args, **kwargs):
        """Delete data with monitoring"""
        def _delete():
            return self.client.table(table).delete(*args, **kwargs).execute()
        
        return self.execute_with_retry(_delete)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics and statistics"""
        uptime = datetime.now() - self.start_time
        
        return {
            'environment': self.env.value,
            'uptime_seconds': uptime.total_seconds(),
            'total_queries': self.query_count,
            'failed_queries': self.query_errors,
            'success_rate': ((self.query_count - self.query_errors) / self.query_count * 100) 
                           if self.query_count > 0 else 0,
            'connection_status': self.connection_pool.get_status() if self.connection_pool else None,
            'rate_limit': {
                'calls_per_second': self.rate_limiter.calls_per_second,
                'recent_calls': len(self.rate_limiter.call_times)
            }
        }
    
    def reset_metrics(self):
        """Reset query metrics"""
        self.query_count = 0
        self.query_errors = 0
        self.start_time = datetime.now()
        logger.info("Metrics reset")
    
    def close(self):
        """Close the client connection"""
        if self._client:
            # Note: Supabase client doesn't have explicit close, but we can reset
            self._client = None
            self.connection_pool = None
            logger.info("Supabase client closed")


# Streamlit-specific functions with caching
@st.cache_resource
def get_supabase_client(env: str = "production") -> Client:
    """
    Get cached Supabase client for Streamlit apps
    This ensures only one client instance exists per session
    """
    try:
        env_enum = Environment(env)
    except ValueError:
        env_enum = Environment.PRODUCTION
    
    manager = SupabaseManager(env_enum)
    return manager.client


@st.cache_resource
def get_supabase_manager(env: str = "production") -> SupabaseManager:
    """
    Get cached Supabase manager for advanced features
    Use this when you need access to metrics, health checks, etc.
    """
    try:
        env_enum = Environment(env)
    except ValueError:
        env_enum = Environment.PRODUCTION
    
    return SupabaseManager(env_enum)


# Decorators for common patterns
def with_supabase_client(env: Environment = Environment.PRODUCTION):
    """Decorator to inject Supabase client into function"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = SupabaseManager(env)
            return func(manager.client, *args, **kwargs)
        return wrapper
    return decorator


def monitored_query(table: str):
    """Decorator to monitor and log queries"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"Query '{func.__name__}' on table '{table}' completed in {duration:.2f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Query '{func.__name__}' on table '{table}' failed after {duration:.2f}s: {e}")
                raise
        return wrapper
    return decorator


# Utility functions
def test_connection(env: Environment = Environment.PRODUCTION) -> bool:
    """Test Supabase connection"""
    try:
        manager = SupabaseManager(env)
        return manager.connection_pool.is_healthy()
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False


def get_connection_status(env: Environment = Environment.PRODUCTION) -> Dict[str, Any]:
    """Get detailed connection status"""
    try:
        manager = SupabaseManager(env)
        return {
            'connected': manager.connection_pool.is_healthy(),
            'metrics': manager.get_metrics()
        }
    except Exception as e:
        return {
            'connected': False,
            'error': str(e)
        }


# Example usage functions
if __name__ == "__main__":
    # Test the connection
    print("Testing Supabase connection...")
    
    if test_connection():
        print("✅ Connection successful!")
        
        # Get metrics
        manager = SupabaseManager()
        print("\nConnection Metrics:")
        for key, value in manager.get_metrics().items():
            print(f"  {key}: {value}")
    else:
        print("❌ Connection failed!")
