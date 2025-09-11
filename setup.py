#!/usr/bin/env python3
"""
Setup script for Mileage Tracker Pro Dashboard
Handles initial configuration and dependency installation
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.8 or higher"""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python version: {sys.version.split()[0]}")

def check_virtual_environment():
    """Check if we're in a virtual environment"""
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if not in_venv:
        print("\n⚠️  You're not in a virtual environment.")
        print("   This is required on macOS/Linux to avoid system package conflicts.")
        print("\n   To create and activate a virtual environment:")
        print("   $ python3 -m venv venv")
        print("   $ source venv/bin/activate")
        print("\n   Then run this setup script again.")
        
        response = input("\n   Would you like me to create a virtual environment for you? (y/n): ").lower()
        if response == 'y':
            create_virtual_environment()
        else:
            print("\n   Please create a virtual environment and run setup again.")
            sys.exit(1)
    else:
        print("✅ Running in virtual environment")

def create_virtual_environment():
    """Create and provide instructions for virtual environment"""
    print("\n📦 Creating virtual environment...")
    try:
        subprocess.check_call([sys.executable, "-m", "venv", "venv"])
        print("✅ Virtual environment created successfully!")
        print("\n   Now activate it and run setup again:")
        print("   $ source venv/bin/activate")
        print("   $ python setup.py")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating virtual environment: {e}")
        sys.exit(1)

def install_dependencies():
    """Install required packages"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        print("\n   If you're on macOS/Linux, make sure you're in a virtual environment.")
        sys.exit(1)

def setup_environment():
    """Setup environment variables"""
    env_file = Path(".env")
    env_example = Path("env.example")
    
    if env_file.exists():
        print("\n✅ .env file already exists")
        response = input("   Do you want to update it? (y/n): ").lower()
        if response != 'y':
            return
    
    if not env_example.exists():
        print("❌ env.example file not found")
        return
    
    print("\n🔧 Setting up environment variables...")
    
    # Read example file
    with open(env_example, 'r') as f:
        content = f.read()
    
    # Get Supabase credentials
    print("\n📝 Please enter your Supabase credentials:")
    print("   (You can find these in your Supabase project settings)")
    
    supabase_url = input("\n   Supabase URL (e.g., https://xxxxx.supabase.co): ").strip()
    supabase_key = input("   Supabase Service Role Key: ").strip()
    
    # Optional database URL
    print("\n   Optional: Direct database connection")
    db_url = input("   Database URL (press Enter to skip): ").strip()
    
    # Create .env file
    env_content = f"""# Supabase Configuration
SUPABASE_URL={supabase_url}
SUPABASE_KEY={supabase_key}
"""
    
    if db_url:
        env_content += f"\n# Direct Database Connection\nDATABASE_URL={db_url}\n"
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print("✅ .env file created successfully")

def test_connection():
    """Test Supabase connection"""
    print("\n🔍 Testing Supabase connection...")
    
    try:
        from dotenv import load_dotenv
        from supabase import create_client
        
        load_dotenv()
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            print("❌ Supabase credentials not found in .env file")
            return False
        
        client = create_client(url, key)
        
        # Try to fetch users count
        response = client.table('users').select('id', count='exact').execute()
        
        print(f"✅ Connection successful! Found {response.count} users in database")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        print("\n   Please check:")
        print("   1. Your Supabase URL and Key are correct")
        print("   2. The 'users' table exists in your database")
        print("   3. You're using the service role key (not anon key)")
        return False

def create_sample_data():
    """Option to create sample data for testing"""
    print("\n📊 Sample Data Setup")
    response = input("   Would you like to create sample data for testing? (y/n): ").lower()
    
    if response != 'y':
        return
    
    try:
        from dotenv import load_dotenv
        from supabase import create_client
        from datetime import datetime, timedelta
        import random
        import uuid
        
        load_dotenv()
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        client = create_client(url, key)
        
        print("\n   Creating sample data...")
        
        # Create sample users
        sample_users = []
        for i in range(20):
            user = {
                'id': str(uuid.uuid4()),
                'email': f'user{i+1}@example.com',
                'name': f'Test User {i+1}',
                'created_at': (datetime.now() - timedelta(days=random.randint(30, 180))).isoformat()
            }
            sample_users.append(user)
        
        # Insert users
        client.table('users').insert(sample_users).execute()
        
        # Create sample trips
        sample_trips = []
        for user in sample_users[:15]:  # Only 15 users have trips
            num_trips = random.randint(1, 50)
            for _ in range(num_trips):
                trip = {
                    'id': str(uuid.uuid4()),
                    'user_id': user['id'],
                    'distance': round(random.uniform(1, 100), 2),
                    'duration': random.randint(5, 180),
                    'created_at': (datetime.now() - timedelta(
                        days=random.randint(0, 30),
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59)
                    )).isoformat()
                }
                sample_trips.append(trip)
        
        # Insert trips in batches
        batch_size = 100
        for i in range(0, len(sample_trips), batch_size):
            batch = sample_trips[i:i+batch_size]
            client.table('trips').insert(batch).execute()
        
        print(f"✅ Created {len(sample_users)} users and {len(sample_trips)} trips")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {str(e)}")

def main():
    """Main setup process"""
    print("🚗 Mileage Tracker Pro Dashboard Setup")
    print("=" * 40)
    
    # Check Python version
    check_python_version()
    
    # Check virtual environment (for macOS/Linux)
    check_virtual_environment()
    
    # Install dependencies
    install_dependencies()
    
    # Setup environment
    setup_environment()
    
    # Test connection
    if test_connection():
        # Offer to create sample data
        create_sample_data()
    
    print("\n" + "=" * 40)
    print("✅ Setup complete!")
    print("\n📊 To start the dashboard, run:")
    print("   streamlit run dashboard.py")
    print("\n💡 Tips:")
    print("   - Check README.md for detailed documentation")
    print("   - Use database_queries.py for advanced analytics")
    print("   - Enable auto-refresh in the sidebar for real-time updates")

if __name__ == "__main__":
    main()
