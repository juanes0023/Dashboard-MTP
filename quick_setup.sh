#!/bin/bash

# Quick Setup Script for Mileage Tracker Pro Dashboard
# This script handles virtual environment creation and setup automatically

echo "🚗 Mileage Tracker Pro Dashboard - Quick Setup"
echo "=============================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        echo "   Make sure Python 3 is installed: brew install python3"
        exit 1
    fi
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed successfully"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Let's set up your Supabase credentials."
    echo ""
    
    # Copy example env file
    if [ -f "env.example" ]; then
        cp env.example .env
        echo "📝 Created .env file from template"
        echo ""
        echo "Please edit the .env file with your Supabase credentials:"
        echo "  1. Open .env in your editor"
        echo "  2. Add your SUPABASE_URL"
        echo "  3. Add your SUPABASE_KEY (use service role key)"
        echo ""
        echo "You can find these in your Supabase project settings."
    else
        echo "❌ env.example file not found"
    fi
else
    echo "✅ .env file already exists"
fi

echo ""
echo "=============================================="
echo "✅ Setup complete!"
echo ""
echo "📊 To start the dashboard, run:"
echo "   source venv/bin/activate"
echo "   streamlit run dashboard.py"
echo ""
echo "Or use the run script:"
echo "   ./run_dashboard.sh"
echo ""
echo "=============================================="
