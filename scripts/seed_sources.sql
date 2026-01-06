-- Seed initial content sources for MVP
-- Run with: sqlite3 curation.db < scripts/seed_sources.sql

-- YouTube channels (2 for MVP)
INSERT OR IGNORE INTO sources (name, type, url) VALUES
    ('ThePrimeagen', 'youtube', 'https://www.youtube.com/@ThePrimeTimeagen'),
    ('Fireship', 'youtube', 'https://www.youtube.com/@Fireship');

-- Podcasts (2 for MVP)
INSERT OR IGNORE INTO sources (name, type, url) VALUES
    ('Latent Space', 'podcast', 'https://api.substack.com/feed/podcast/1084089.rss'),
    ('AI Daily Brief', 'podcast', 'https://feeds.transistor.fm/ai-daily-brief-formerly-ai-breakdown-artificial-intelligence-news');

-- RSS/Blogs (1 for MVP)
INSERT OR IGNORE INTO sources (name, type, url) VALUES
    ('Simon Willison', 'rss', 'https://simonwillison.net/atom/everything/');

-- Verify
SELECT id, name, type, enabled FROM sources;
