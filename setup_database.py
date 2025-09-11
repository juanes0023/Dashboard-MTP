#!/usr/bin/env python3
"""
Database Setup Script for Mileage Tracker Pro
Creates necessary tables and optionally populates with sample data
"""

import sys
import os
from datetime import datetime, timedelta
import random
import uuid
from dotenv import load_dotenv
from supabase_client import get_supabase_client, get_supabase_manager, test_connection

# Load environment variables
load_dotenv()

# SQL statements to create tables
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

CREATE_TRIPS_TABLE = """
CREATE TABLE IF NOT EXISTS trips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    distance NUMERIC(10, 2) NOT NULL CHECK (distance >= 0),
    duration NUMERIC(10, 2) NOT NULL CHECK (duration >= 0),
    start_location TEXT,
    end_location TEXT,
    purpose TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

CREATE_INDEXES = """
-- Index for faster user lookups
CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id);

-- Index for date-based queries
CREATE INDEX IF NOT EXISTS idx_trips_created_at ON trips(created_at);

-- Index for users email
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""

# Enable Row Level Security (optional but recommended)
ENABLE_RLS = """
-- Enable RLS on tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE trips ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust based on your auth setup)
-- These are example policies - modify based on your needs

-- Users can read all users (for leaderboards)
CREATE POLICY IF NOT EXISTS "Users can view all users" 
    ON users FOR SELECT 
    USING (true);

-- Users can read all trips (for analytics)
CREATE POLICY IF NOT EXISTS "Users can view all trips" 
    ON trips FOR SELECT 
    USING (true);
"""


def execute_sql(client, sql: str, description: str):
    """Execute SQL statement via Supabase"""
    print(f"📝 {description}...")
    try:
        # Note: Direct SQL execution requires using Supabase's SQL editor or RPC functions
        # For now, we'll use the table creation through the Supabase dashboard
        print(f"   ⚠️  Please execute the following SQL in your Supabase SQL editor:")
        print(f"   {'-' * 50}")
        print(sql)
        print(f"   {'-' * 50}")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def check_tables_exist(client):
    """Check if required tables exist"""
    tables_exist = {'users': False, 'trips': False}
    
    for table in tables_exist.keys():
        try:
            # Try to query the table
            client.table(table).select('id').limit(1).execute()
            tables_exist[table] = True
            print(f"   ✅ Table '{table}' exists")
        except Exception as e:
            if "does not exist" in str(e):
                print(f"   ❌ Table '{table}' does not exist")
            else:
                print(f"   ⚠️  Cannot check table '{table}': {e}")
    
    return all(tables_exist.values()), tables_exist


def create_sample_data(client):
    """Create sample data for testing"""
    print("\n📊 Creating sample data...")
    
    try:
        # Create sample users
        sample_users = []
        user_names = [
            "John Smith", "Emma Johnson", "Michael Brown", "Sarah Davis", 
            "James Wilson", "Lisa Anderson", "Robert Taylor", "Mary Thomas",
            "David Jackson", "Jennifer White", "Chris Martin", "Amanda Garcia",
            "Daniel Martinez", "Michelle Robinson", "Kevin Clark"
        ]
        
        print("   Creating users...")
        for i, name in enumerate(user_names):
            email = name.lower().replace(" ", ".") + "@example.com"
            user = {
                'id': str(uuid.uuid4()),
                'email': email,
                'name': name,
                'created_at': (datetime.now() - timedelta(days=random.randint(30, 180))).isoformat()
            }
            sample_users.append(user)
        
        # Insert users
        response = client.table('users').insert(sample_users).execute()
        print(f"   ✅ Created {len(sample_users)} users")
        
        # Create sample trips
        print("   Creating trips...")
        sample_trips = []
        locations = [
            ("Home", "Office"), ("Office", "Client Site"), ("Home", "Grocery Store"),
            ("Office", "Airport"), ("Hotel", "Conference Center"), ("Home", "Gym"),
            ("Office", "Restaurant"), ("Home", "School"), ("Office", "Home")
        ]
        purposes = ["Business", "Commute", "Personal", "Client Meeting", "Conference", "Delivery"]
        
        for user in sample_users[:12]:  # Only create trips for 12 users
            num_trips = random.randint(5, 50)
            
            for _ in range(num_trips):
                start_loc, end_loc = random.choice(locations)
                trip = {
                    'id': str(uuid.uuid4()),
                    'user_id': user['id'],
                    'distance': round(random.uniform(1, 100), 2),
                    'duration': round(random.uniform(5, 180), 2),
                    'start_location': start_loc,
                    'end_location': end_loc,
                    'purpose': random.choice(purposes),
                    'created_at': (datetime.now() - timedelta(
                        days=random.randint(0, 30),
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59)
                    )).isoformat()
                }
                sample_trips.append(trip)
        
        # Insert trips in batches
        batch_size = 100
        total_inserted = 0
        for i in range(0, len(sample_trips), batch_size):
            batch = sample_trips[i:i+batch_size]
            response = client.table('trips').insert(batch).execute()
            total_inserted += len(batch)
            print(f"   ... inserted {total_inserted}/{len(sample_trips)} trips")
        
        print(f"   ✅ Created {len(sample_trips)} trips")
        
        # Show summary
        print("\n📈 Sample Data Summary:")
        print(f"   • Total Users: {len(sample_users)}")
        print(f"   • Active Users (with trips): 12")
        print(f"   • Total Trips: {len(sample_trips)}")
        print(f"   • Average Trips per Active User: {len(sample_trips) // 12}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error creating sample data: {e}")
        return False


def main():
    """Main setup process"""
    print("🚗 Mileage Tracker Pro - Database Setup")
    print("=" * 50)
    
    # Test connection
    print("\n🔌 Testing database connection...")
    
    try:
        client = get_supabase_client()
        manager = get_supabase_manager()
        print("   ✅ Successfully connected to Supabase")
        
        # Get connection metrics
        metrics = manager.get_metrics()
        print(f"   📊 Environment: {metrics.get('environment', 'unknown')}")
        
    except Exception as e:
        print(f"   ❌ Failed to connect: {e}")
        print("\n   Please check your .env file and ensure:")
        print("   1. SUPABASE_URL is set correctly")
        print("   2. SUPABASE_KEY is the service role key (not anon key)")
        sys.exit(1)
    
    # Check existing tables
    print("\n🔍 Checking existing tables...")
    all_exist, table_status = check_tables_exist(client)
    
    if all_exist:
        print("\n✅ All required tables already exist!")
        
        # Ask if user wants to add sample data
        response = input("\n   Would you like to add sample data? (y/n): ").lower()
        if response == 'y':
            create_sample_data(client)
    else:
        print("\n⚠️  Some tables are missing.")
        print("\n" + "=" * 50)
        print("📋 MANUAL SETUP REQUIRED")
        print("=" * 50)
        print("\nPlease follow these steps:")
        print("\n1. Go to your Supabase Dashboard")
        print("2. Navigate to the SQL Editor")
        print("3. Copy and run the following SQL statements:\n")
        
        # Print SQL statements
        print("-- Note: Profiles table should already exist (managed by Supabase Auth)")
        print("-- If it doesn't exist, create it:")
        print(CREATE_PROFILES_TABLE)
        print("\n-- Create Trips Table")
        print(CREATE_TRIPS_TABLE)
        print("\n-- Create Indexes")
        print(CREATE_INDEXES)
        print("\n-- Optional: Enable Row Level Security")
        print(ENABLE_RLS)
        
        print("\n" + "=" * 50)
        print("\n4. After creating tables, run this script again to add sample data")
        
        # Save SQL to file
        sql_file = "create_tables.sql"
        with open(sql_file, 'w') as f:
            f.write("-- Mileage Tracker Pro Database Schema\n\n")
            f.write("-- Note: Profiles table should already exist (managed by Supabase Auth)\n")
            f.write("-- If it doesn't exist, create it:\n")
            f.write(CREATE_PROFILES_TABLE + "\n")
            f.write("-- Create Trips Table\n")
            f.write(CREATE_TRIPS_TABLE + "\n")
            f.write("-- Create Indexes\n")
            f.write(CREATE_INDEXES + "\n")
            f.write("-- Optional: Enable Row Level Security\n")
            f.write(ENABLE_RLS)
        
        print(f"\n💾 SQL statements saved to: {sql_file}")
        print("   You can copy this file's contents to Supabase SQL Editor")
    
    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    
    if all_exist:
        print("\n🚀 Your dashboard is ready to use!")
        print("   Run: ./run_dashboard.sh")
    else:
        print("\n📝 Next steps:")
        print("   1. Create tables in Supabase (see instructions above)")
        print("   2. Run this script again to verify and add sample data")
        print("   3. Start the dashboard: ./run_dashboard.sh")


if __name__ == "__main__":
    main()
