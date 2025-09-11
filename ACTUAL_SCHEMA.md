# Mileage Tracker Pro - Actual Database Schema

## ✅ Schema Successfully Mapped

The dashboard has been updated to work with your actual database schema.

### 📊 **Profiles Table** (Existing)
- `id` (UUID) - Primary key
- `full_name` (Text)
- `photo_url` (Text)
- `phone_number` (Text)
- `subscription_tier` (Text)
- `created_at` (Timestamp)
- `updated_at` (Timestamp)

### 🚗 **Trips Table** (Existing)
Your actual trips table has these columns:
- `id` (UUID) - Primary key
- `user_id` (UUID) - Foreign key to profiles.id
- `date` (Date)
- `start_time` (Time)
- `end_time` (Time)
- `start_location` (Text)
- `end_location` (Text)
- **`mileage`** (Numeric) - Base distance field
- **`actual_distance`** (Numeric) - Actual distance traveled
- `planned_distance` (Numeric)
- `purpose` (Text)
- `is_round_trip` (Boolean)
- `notes` (Text)
- `status` (Text)
- `waypoints` (Array/JSON)
- `actual_route` (JSON)
- `planned_route` (JSON)
- `fuel_used` (Numeric)
- `reimbursement` (Numeric)
- `created_at` (Timestamp)
- `updated_at` (Timestamp)

## 🔄 **Key Mappings**

The dashboard now uses:

| Dashboard Metric | Source Column(s) | Logic |
|-----------------|------------------|-------|
| **Distance** | `actual_distance` or `mileage` | Uses `actual_distance` if available, falls back to `mileage` |
| **Duration** | Calculated from `end_time - start_time` | Converts to minutes |
| **User Name** | `profiles.full_name` | From profiles table |
| **User Contact** | `profiles.phone_number` | From profiles table |
| **Subscription** | `profiles.subscription_tier` | From profiles table |

## 📈 **Additional Features Available**

With your schema, you can now track:
- **Fuel efficiency**: Using `fuel_used` and distance
- **Reimbursement tracking**: Using `reimbursement` field
- **Round trip analysis**: Using `is_round_trip` flag
- **Route analysis**: Using `actual_route` vs `planned_route`
- **Trip status**: Using `status` field
- **Waypoint analysis**: Using `waypoints` data

## 🚀 **Dashboard Functionality**

The dashboard now correctly:
1. ✅ Displays user information from `profiles` table
2. ✅ Calculates trip distances using `actual_distance` or `mileage`
3. ✅ Computes trip duration from `start_time` and `end_time`
4. ✅ Shows subscription tiers for users
5. ✅ Handles missing data gracefully

## 💡 **Future Enhancements**

Based on your schema, you could add:
1. **Fuel Economy Dashboard**: Miles per gallon calculations
2. **Reimbursement Reports**: Total reimbursements by user/period
3. **Route Accuracy**: Compare planned vs actual routes
4. **Round Trip Analysis**: Efficiency of round trips
5. **Status Tracking**: Completed vs planned trips

## 🔧 **Query Examples**

```sql
-- Get total mileage per user
SELECT 
    p.full_name,
    SUM(COALESCE(t.actual_distance, t.mileage)) as total_miles,
    SUM(t.fuel_used) as total_fuel,
    SUM(t.reimbursement) as total_reimbursement
FROM profiles p
LEFT JOIN trips t ON p.id = t.user_id
GROUP BY p.id, p.full_name;

-- Get trips with calculated duration
SELECT 
    t.*,
    EXTRACT(EPOCH FROM (t.end_time - t.start_time))/60 as duration_minutes
FROM trips t
WHERE t.start_time IS NOT NULL 
  AND t.end_time IS NOT NULL;
```

## ✅ **Status**
- Dashboard: **Running**
- Schema: **Correctly Mapped**
- URL: **http://localhost:8501**
