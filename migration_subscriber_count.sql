-- Migration: Add subscriber_count column to telegram_channels table
-- Run this in Railway's PostgreSQL console or via psql

-- Check if column exists (PostgreSQL will skip if it does)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='telegram_channels' 
        AND column_name='subscriber_count'
    ) THEN
        ALTER TABLE telegram_channels 
        ADD COLUMN subscriber_count INTEGER DEFAULT NULL;
        
        RAISE NOTICE 'Column subscriber_count added successfully';
    ELSE
        RAISE NOTICE 'Column subscriber_count already exists, skipping';
    END IF;
END $$;

-- Verify the column was added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'telegram_channels' 
AND column_name = 'subscriber_count';

