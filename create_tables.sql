-- Mileage Tracker Pro Database Schema

-- Create Users Table

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create Trips Table

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

-- Create Indexes

-- Index for faster user lookups
CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id);

-- Index for date-based queries
CREATE INDEX IF NOT EXISTS idx_trips_created_at ON trips(created_at);

-- Index for users email
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Optional: Enable Row Level Security

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
