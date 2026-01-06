-- Content Curation Database Schema
-- Run with: sqlite3 curation.db < scripts/init_db.sql

-- ============================================
-- TABLE: sources
-- Stores the content sources we monitor
-- (YouTube channels, podcasts, blogs)
-- ============================================
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                -- "ThePrimeagen"
    type TEXT NOT NULL,                -- "youtube" | "podcast" | "rss"
    url TEXT NOT NULL UNIQUE,          -- Channel/feed URL
    enabled INTEGER DEFAULT 1,         -- 1=active, 0=paused
    last_fetch_at TEXT,                -- ISO timestamp of last fetch
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================
-- TABLE: content_items
-- Stores all fetched content with ratings
-- This is the main table - one row per video/episode/post
-- ============================================
CREATE TABLE IF NOT EXISTS content_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,

    -- Content metadata
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,          -- Unique constraint prevents duplicates
    description TEXT,
    transcript TEXT,                   -- For YouTube videos (from captions)
    published_date TEXT,               -- When the content was published
    duration_minutes INTEGER,          -- Video/episode length

    -- Rating data (filled by Fabric)
    rating TEXT,                       -- NULL | "S" | "A" | "B" | "C" | "D"
    rating_reasoning TEXT,             -- Why Fabric gave this rating
    rated_at TEXT,                     -- When we rated it

    -- Output tracking
    published_to_obsidian INTEGER DEFAULT 0,  -- 1 = included in digest
    digest_id INTEGER,                 -- Which digest included this item

    -- Timestamps
    fetched_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (source_id) REFERENCES sources(id)
);

-- ============================================
-- TABLE: digests
-- Tracks generated weekly digests
-- ============================================
CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start_date TEXT NOT NULL,
    week_end_date TEXT NOT NULL,
    item_count INTEGER,
    s_tier_count INTEGER,
    a_tier_count INTEGER,
    obsidian_path TEXT,                -- Where we saved the digest file
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================
-- TABLE: fetch_logs
-- Audit trail - tracks every fetch attempt
-- Useful for debugging when things go wrong
-- ============================================
CREATE TABLE IF NOT EXISTS fetch_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    items_fetched INTEGER,
    success INTEGER,                   -- 1=success, 0=failure
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,

    FOREIGN KEY (source_id) REFERENCES sources(id)
);

-- ============================================
-- INDEXES
-- Speed up common queries
-- ============================================
CREATE INDEX IF NOT EXISTS idx_content_url ON content_items(url);
CREATE INDEX IF NOT EXISTS idx_content_rating ON content_items(rating);
CREATE INDEX IF NOT EXISTS idx_content_published ON content_items(published_to_obsidian);
CREATE INDEX IF NOT EXISTS idx_content_date ON content_items(published_date);
CREATE INDEX IF NOT EXISTS idx_content_source ON content_items(source_id);

-- ============================================
-- Enable WAL mode for better concurrency
-- (prevents "database is locked" errors)
-- ============================================
PRAGMA journal_mode=WAL;
