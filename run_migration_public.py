"""
Run migration using public Railway connection.
"""
import asyncio
import asyncpg

async def run_migration():
    """Run the subscriber_count migration."""
    
    # Public Railway connection details
    conn = await asyncpg.connect(
        host='switchback.proxy.rlwy.net',
        port=40957,
        user='postgres',
        password='oxYQctMVzJXoEQKxCHtLDznZIieYkSqD',
        database='railway'
    )
    
    try:
        print("✓ Connected to Railway database")
        
        # Check if column exists
        check_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='telegram_channels' 
            AND column_name='subscriber_count';
        """
        
        result = await conn.fetch(check_query)
        
        if result:
            print("✓ subscriber_count column already exists")
            return True
        
        print("➕ Adding subscriber_count column...")
        
        # Add the column
        alter_query = """
            ALTER TABLE telegram_channels 
            ADD COLUMN subscriber_count INTEGER DEFAULT NULL;
        """
        
        await conn.execute(alter_query)
        print("✅ Migration completed successfully!")
        
        # Verify it was added
        verify = await conn.fetch(check_query)
        if verify:
            print("✓ Verified: subscriber_count column exists")
            return True
        else:
            print("❌ Warning: Column might not have been added")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        await conn.close()
        print("✓ Connection closed")

if __name__ == "__main__":
    print("🚀 Running migration on Railway database...")
    print("=" * 60)
    success = asyncio.run(run_migration())
    print("=" * 60)
    if success:
        print("✅ All done!")
    else:
        print("❌ Migration failed")



