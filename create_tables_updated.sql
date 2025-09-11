-- Mileage Tracker Pro Database Schema
-- Updated to work with existing profiles table

-- The profiles table already exists and is linked to auth.users
-- We just need to create the trips table and link it properly

-- Create Trips Table (referencing profiles instead of users)
CREATE TABLE IF NOT EXISTS trips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    distance NUMERIC(10, 2) NOT NULL CHECK (distance >= 0),
    duration NUMERIC(10, 2) NOT NULL CHECK (duration >= 0),
    start_location TEXT,
    end_location TEXT,
    purpose TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id);
CREATE INDEX IF NOT EXISTS idx_trips_created_at ON trips(created_at);

-- Enable Row Level Security on trips
ALTER TABLE trips ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for trips
-- Allow authenticated users to see all trips (for analytics)
CREATE POLICY "Authenticated users can view all trips" 
    ON trips FOR SELECT 
    TO authenticated
    USING (true);

-- Allow users to manage their own trips
CREATE POLICY "Users can insert own trips" 
    ON trips FOR INSERT 
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own trips" 
    ON trips FOR UPDATE 
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own trips" 
    ON trips FOR DELETE 
    TO authenticated
    USING (auth.uid() = user_id);

-- Create a view for user statistics (using profiles table)
CREATE OR REPLACE VIEW user_trip_stats AS
SELECT 
    p.id,
    p.full_name,
    p.phone_number,
    p.subscription_tier,
    COUNT(t.id) as trip_count,
    COALESCE(SUM(t.distance), 0) as total_distance,
    COALESCE(SUM(t.duration), 0) as total_duration,
    COALESCE(AVG(t.distance), 0) as avg_distance,
    COALESCE(AVG(t.duration), 0) as avg_duration,
    MAX(t.created_at) as last_trip_date
FROM profiles p
LEFT JOIN trips t ON p.id = t.user_id
GROUP BY p.id, p.full_name, p.phone_number, p.subscription_tier;

-- Function to get active users count
CREATE OR REPLACE FUNCTION get_active_users_count(days_back INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(DISTINCT user_id)
        FROM trips
        WHERE created_at >= NOW() - INTERVAL '1 day' * days_back
    );
END;
$$ LANGUAGE plpgsql;
