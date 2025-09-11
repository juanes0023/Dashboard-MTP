#!/usr/bin/env python3
"""
Database Inspector for Mileage Tracker Pro
Provides comprehensive visibility into your Supabase database structure
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from supabase_client import get_supabase_client, get_supabase_manager
import pandas as pd
from tabulate import tabulate

# Load environment variables
load_dotenv()

class DatabaseInspector:
    """Comprehensive database inspection tool"""
    
    def __init__(self):
        self.client = get_supabase_client()
        self.manager = get_supabase_manager()
        self.tables_info = {}
        
    def get_all_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        # Common tables we expect
        common_tables = ['profiles', 'trips', 'users', 'vehicles', 'categories', 'settings']
        existing_tables = []
        
        print("\n🔍 Scanning for tables...")
        for table in common_tables:
            try:
                # Try to query each table
                result = self.client.table(table).select('id').limit(1).execute()
                existing_tables.append(table)
                print(f"  ✅ Found table: {table}")
            except Exception as e:
                if "does not exist" not in str(e):
                    print(f"  ⚠️  Error checking {table}: {str(e)[:50]}...")
        
        return existing_tables
    
    def inspect_table(self, table_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific table"""
        info = {
            'name': table_name,
            'columns': {},
            'row_count': 0,
            'sample_data': None,
            'error': None
        }
        
        try:
            # Get sample data to infer schema
            result = self.client.table(table_name).select('*').limit(5).execute()
            
            if result.data:
                # Get row count
                count_result = self.client.table(table_name).select('id', count='exact').execute()
                info['row_count'] = count_result.count
                
                # Analyze columns from sample data
                sample = result.data[0]
                for col_name, value in sample.items():
                    info['columns'][col_name] = {
                        'type': type(value).__name__ if value is not None else 'unknown',
                        'nullable': any(row.get(col_name) is None for row in result.data),
                        'sample_values': list(set([row.get(col_name) for row in result.data[:3] if row.get(col_name) is not None]))[:3]
                    }
                
                # Store sample data
                info['sample_data'] = result.data[:2]  # Keep 2 sample rows
            else:
                info['row_count'] = 0
                info['columns'] = {'No data': {'type': 'empty', 'nullable': True, 'sample_values': []}}
                
        except Exception as e:
            info['error'] = str(e)
            
        return info
    
    def analyze_relationships(self, tables: List[str]) -> Dict[str, List[str]]:
        """Analyze relationships between tables"""
        relationships = {}
        
        for table in tables:
            relationships[table] = []
            
            # Get sample data to check for foreign keys
            try:
                result = self.client.table(table).select('*').limit(1).execute()
                if result.data:
                    for col_name in result.data[0].keys():
                        # Common foreign key patterns
                        if col_name.endswith('_id') and col_name != 'id':
                            potential_table = col_name.replace('_id', '')
                            if potential_table in tables or potential_table + 's' in tables:
                                relationships[table].append(f"{col_name} -> {potential_table}")
            except:
                pass
                
        return relationships
    
    def get_statistics(self, table_name: str) -> Dict[str, Any]:
        """Get statistics for a specific table"""
        stats = {}
        
        try:
            # For trips table
            if table_name == 'trips':
                result = self.client.table('trips').select('*').execute()
                if result.data:
                    df = pd.DataFrame(result.data)
                    
                    # Numeric columns statistics
                    numeric_cols = ['mileage', 'actual_distance', 'planned_distance', 'fuel_used', 'reimbursement']
                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                            stats[col] = {
                                'min': df[col].min(),
                                'max': df[col].max(),
                                'mean': df[col].mean(),
                                'sum': df[col].sum(),
                                'null_count': df[col].isna().sum()
                            }
                    
                    # Date statistics
                    if 'created_at' in df.columns:
                        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
                        stats['date_range'] = {
                            'earliest': df['created_at'].min(),
                            'latest': df['created_at'].max(),
                            'total_days': (df['created_at'].max() - df['created_at'].min()).days if not df['created_at'].isna().all() else 0
                        }
            
            # For profiles table
            elif table_name == 'profiles':
                result = self.client.table('profiles').select('*').execute()
                if result.data:
                    df = pd.DataFrame(result.data)
                    
                    # Subscription tier distribution
                    if 'subscription_tier' in df.columns:
                        stats['subscription_distribution'] = df['subscription_tier'].value_counts().to_dict()
                    
                    # User creation timeline
                    if 'created_at' in df.columns:
                        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
                        stats['user_growth'] = {
                            'first_user': df['created_at'].min(),
                            'latest_user': df['created_at'].max(),
                            'users_last_30_days': len(df[df['created_at'] >= pd.Timestamp.now() - pd.Timedelta(days=30)])
                        }
                        
        except Exception as e:
            stats['error'] = str(e)
            
        return stats
    
    def generate_report(self):
        """Generate comprehensive database report"""
        print("\n" + "="*60)
        print("🗄️  MILEAGE TRACKER PRO - DATABASE INSPECTION REPORT")
        print("="*60)
        
        # Get all tables
        tables = self.get_all_tables()
        print(f"\n📊 Found {len(tables)} tables in database")
        
        # Connection metrics
        print("\n🔌 Connection Metrics:")
        metrics = self.manager.get_metrics()
        print(f"  • Environment: {metrics.get('environment', 'unknown')}")
        print(f"  • Total Queries: {metrics.get('total_queries', 0)}")
        print(f"  • Success Rate: {metrics.get('success_rate', 0):.1f}%")
        print(f"  • Connection Status: {metrics.get('connection_status', {}).get('status', 'unknown')}")
        
        # Inspect each table
        for table in tables:
            print(f"\n\n📋 TABLE: {table.upper()}")
            print("-" * 40)
            
            info = self.inspect_table(table)
            
            if info['error']:
                print(f"  ❌ Error: {info['error']}")
                continue
            
            print(f"  • Rows: {info['row_count']:,}")
            print(f"  • Columns: {len(info['columns'])}")
            
            # Display columns
            print("\n  Column Information:")
            col_data = []
            for col_name, col_info in info['columns'].items():
                col_data.append([
                    col_name,
                    col_info['type'],
                    '✓' if col_info['nullable'] else '✗',
                    ', '.join(str(v)[:20] for v in col_info['sample_values'][:2])
                ])
            
            if col_data:
                table_str = tabulate(col_data, headers=['Column', 'Type', 'Nullable', 'Sample Values'], 
                                   tablefmt='simple')
                # Add indentation manually
                for line in table_str.split('\n'):
                    print(f"    {line}")
            
            # Display statistics
            stats = self.get_statistics(table)
            if stats and 'error' not in stats:
                print(f"\n  Statistics:")
                for stat_name, stat_value in stats.items():
                    if isinstance(stat_value, dict):
                        print(f"    • {stat_name}:")
                        for k, v in stat_value.items():
                            if isinstance(v, float):
                                print(f"      - {k}: {v:.2f}")
                            else:
                                print(f"      - {k}: {v}")
                    else:
                        print(f"    • {stat_name}: {stat_value}")
            
            # Show sample data
            if info['sample_data'] and len(info['sample_data']) > 0:
                print(f"\n  Sample Record:")
                sample = info['sample_data'][0]
                for key, value in list(sample.items())[:5]:  # Show first 5 fields
                    if value is not None:
                        value_str = str(value)[:50] + '...' if len(str(value)) > 50 else str(value)
                        print(f"    • {key}: {value_str}")
        
        # Show relationships
        print("\n\n🔗 TABLE RELATIONSHIPS")
        print("-" * 40)
        relationships = self.analyze_relationships(tables)
        for table, rels in relationships.items():
            if rels:
                print(f"  • {table}:")
                for rel in rels:
                    print(f"    → {rel}")
        
        # Generate SQL helper
        print("\n\n💡 USEFUL SQL QUERIES")
        print("-" * 40)
        
        if 'trips' in tables and 'profiles' in tables:
            print("\n-- Top 5 users by mileage:")
            print("""SELECT p.full_name, 
       COUNT(t.id) as trip_count,
       SUM(COALESCE(t.actual_distance, t.mileage)) as total_miles
FROM profiles p
JOIN trips t ON p.id = t.user_id
GROUP BY p.id, p.full_name
ORDER BY total_miles DESC
LIMIT 5;""")
            
            print("\n-- Recent activity summary:")
            print("""SELECT 
    DATE(t.created_at) as trip_date,
    COUNT(DISTINCT t.user_id) as active_users,
    COUNT(t.id) as trips,
    SUM(COALESCE(t.actual_distance, t.mileage)) as total_miles
FROM trips t
WHERE t.created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(t.created_at)
ORDER BY trip_date DESC;""")
        
        print("\n" + "="*60)
        print("📊 Report generated at:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("="*60)
        
        # Save report to file
        self.save_report_to_file(tables)
        
    def save_report_to_file(self, tables: List[str]):
        """Save detailed report to JSON file"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'environment': self.manager.get_metrics().get('environment', 'unknown'),
            'tables': {}
        }
        
        for table in tables:
            info = self.inspect_table(table)
            stats = self.get_statistics(table)
            report['tables'][table] = {
                'info': info,
                'statistics': stats
            }
        
        # Save to file
        filename = f"database_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n💾 Detailed report saved to: {filename}")


def main():
    """Main function"""
    print("🚀 Starting Database Inspector...")
    
    try:
        inspector = DatabaseInspector()
        inspector.generate_report()
        
        print("\n\n✅ Inspection complete!")
        print("\n📝 This report helps you understand:")
        print("  • What tables exist in your database")
        print("  • The structure of each table")
        print("  • Data statistics and patterns")
        print("  • Relationships between tables")
        print("\n💡 Use this information to:")
        print("  • Debug dashboard issues")
        print("  • Understand data availability")
        print("  • Plan new features")
        print("  • Optimize queries")
        
    except Exception as e:
        print(f"\n❌ Error during inspection: {e}")
        print("\nPlease check:")
        print("  1. Your .env file has correct credentials")
        print("  2. Your Supabase service is running")
        print("  3. You have proper permissions")


if __name__ == "__main__":
    main()
