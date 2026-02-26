#!/usr/bin/env python3
"""
Stats Tracker for mimofr Media Kit
Fetches social stats and tracks changes over time.

Usage:
  python3 stats-tracker.py          # Fetch stats and update history
  python3 stats-tracker.py --update # Update the HTML with current stats
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Config
STATS_FILE = Path(__file__).parent / "stats-history.json"
HTML_FILE = Path(__file__).parent / "mediakit-final.html"

PROFILES = {
    "instagram": "mimofrl",
    "tiktok": "mimofrl", 
    "youtube": "mimofrl",
    "facebook": "mimofrl"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def load_stats():
    """Load stats history from JSON file."""
    if STATS_FILE.exists():
        with open(STATS_FILE) as f:
            return json.load(f)
    return {"history": [], "current": {}, "changes": {}}


def save_stats(data):
    """Save stats to JSON file."""
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✓ Saved stats to {STATS_FILE}")


def fetch_url(url):
    """Fetch URL content."""
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8")
    except (URLError, HTTPError) as e:
        print(f"  ✗ Failed to fetch {url}: {e}")
        return None


def parse_count(text):
    """Parse follower count strings like '247K', '1.3M', etc."""
    if not text:
        return None
    text = text.strip().upper().replace(",", "")
    
    multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}
    
    for suffix, mult in multipliers.items():
        if suffix in text:
            try:
                num = float(text.replace(suffix, ""))
                return int(num * mult)
            except ValueError:
                pass
    
    try:
        return int(float(text))
    except ValueError:
        return None


def fetch_tiktok_stats(username):
    """Fetch TikTok stats from public profile."""
    print(f"  Fetching TikTok @{username}...")
    url = f"https://www.tiktok.com/@{username}"
    html = fetch_url(url)
    
    if not html:
        return None
    
    stats = {}
    
    # Try to find follower count in page
    # TikTok stores data in JSON in the page
    patterns = [
        r'"followerCount":(\d+)',
        r'"fans":(\d+)',
        r'followers["\s:]+(\d+(?:\.\d+)?[KMB]?)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            count = parse_count(match.group(1))
            if count:
                stats["followers"] = count
                break
    
    # Try to find likes
    like_patterns = [r'"heartCount":(\d+)', r'"heart":(\d+)']
    for pattern in like_patterns:
        match = re.search(pattern, html)
        if match:
            stats["total_likes"] = int(match.group(1))
            break
    
    return stats if stats else None


def fetch_youtube_stats(username):
    """Fetch YouTube stats from public profile."""
    print(f"  Fetching YouTube @{username}...")
    url = f"https://www.youtube.com/@{username}"
    html = fetch_url(url)
    
    if not html:
        return None
    
    stats = {}
    
    # Try to find subscriber count
    patterns = [
        r'"subscriberCountText":\{"simpleText":"([\d.]+[KMB]?) subscribers"\}',
        r'(\d+(?:\.\d+)?[KMB]?) subscribers',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            count = parse_count(match.group(1))
            if count:
                stats["subscribers"] = count
                break
    
    return stats if stats else None


def fetch_instagram_stats(username):
    """Fetch Instagram stats - requires login so we skip for now."""
    print(f"  Fetching Instagram @{username}... (limited - needs API)")
    # Instagram blocks scraping, would need official API
    # For now, return None and use manual input
    return None


def fetch_facebook_stats(username):
    """Fetch Facebook stats from public page."""
    print(f"  Fetching Facebook @{username}... (limited)")
    # Facebook also restricts scraping
    return None


def calculate_changes(current, previous):
    """Calculate percentage changes between two stat snapshots."""
    changes = {}
    
    if not previous:
        return changes
    
    for platform, stats in current.items():
        if platform not in previous:
            continue
        
        changes[platform] = {}
        prev_stats = previous[platform]
        
        for key, value in stats.items():
            if key in prev_stats and prev_stats[key] and value:
                old_val = prev_stats[key]
                pct_change = ((value - old_val) / old_val) * 100
                changes[platform][key] = round(pct_change, 1)
    
    return changes


def fetch_all_stats():
    """Fetch stats from all platforms."""
    print("\n📊 Fetching social stats...")
    
    stats = {}
    
    # TikTok
    tiktok = fetch_tiktok_stats(PROFILES["tiktok"])
    if tiktok:
        stats["tiktok"] = tiktok
        print(f"    ✓ TikTok: {tiktok}")
    
    # YouTube  
    youtube = fetch_youtube_stats(PROFILES["youtube"])
    if youtube:
        stats["youtube"] = youtube
        print(f"    ✓ YouTube: {youtube}")
    
    # Instagram (limited)
    instagram = fetch_instagram_stats(PROFILES["instagram"])
    if instagram:
        stats["instagram"] = instagram
    
    # Facebook (limited)
    facebook = fetch_facebook_stats(PROFILES["facebook"])
    if facebook:
        stats["facebook"] = facebook
    
    return stats


def update_stats():
    """Main function to fetch and update stats."""
    data = load_stats()
    
    # Save current to history before updating
    if data.get("current") and data.get("last_updated"):
        history_entry = {
            "date": data["last_updated"],
            "stats": data["current"].copy()
        }
        data["history"].append(history_entry)
        
        # Keep only last 30 entries
        data["history"] = data["history"][-30:]
    
    # Fetch new stats
    new_stats = fetch_all_stats()
    
    # Merge with existing (don't overwrite what we couldn't fetch)
    for platform, stats in new_stats.items():
        if platform not in data["current"]:
            data["current"][platform] = {}
        data["current"][platform].update(stats)
    
    # Calculate changes from 30 days ago if available
    if data["history"]:
        # Find entry from ~30 days ago
        thirty_days_ago = datetime.now() - timedelta(days=30)
        old_entry = None
        
        for entry in data["history"]:
            try:
                entry_date = datetime.fromisoformat(entry["date"])
                if entry_date <= thirty_days_ago:
                    old_entry = entry
            except (ValueError, TypeError):
                continue
        
        if old_entry:
            data["changes"] = calculate_changes(data["current"], old_entry["stats"])
            print(f"\n📈 Changes since {old_entry['date'][:10]}:")
            for platform, changes in data["changes"].items():
                for key, pct in changes.items():
                    sign = "+" if pct > 0 else ""
                    print(f"    {platform}.{key}: {sign}{pct}%")
    
    # Update timestamp
    data["last_updated"] = datetime.now().isoformat()
    
    save_stats(data)
    print(f"\n✅ Stats updated at {data['last_updated']}")
    
    return data


def format_number(n):
    """Format number as K/M string."""
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    elif n >= 1000:
        return f"{n/1000:.0f}K"
    return str(n)


def update_html(data):
    """Update the media kit HTML with current stats."""
    if not HTML_FILE.exists():
        print(f"✗ HTML file not found: {HTML_FILE}")
        return
    
    html = HTML_FILE.read_text()
    
    # This would update specific values in the HTML
    # For now, just print what would be updated
    print("\n📝 Would update HTML with:")
    for platform, stats in data["current"].items():
        print(f"  {platform}:")
        for key, value in stats.items():
            print(f"    {key}: {format_number(value) if isinstance(value, int) else value}")
    
    print("\n💡 HTML auto-update coming soon!")
    print("   For now, manually update the numbers in mediakit-final.html")


def main():
    if "--update" in sys.argv:
        data = load_stats()
        update_html(data)
    else:
        data = update_stats()
        
        print("\n" + "="*50)
        print("📋 CURRENT STATS SUMMARY")
        print("="*50)
        
        for platform, stats in data["current"].items():
            print(f"\n{platform.upper()}:")
            for key, value in stats.items():
                formatted = format_number(value) if isinstance(value, int) else value
                
                # Add change indicator if available
                change = data.get("changes", {}).get(platform, {}).get(key)
                if change:
                    sign = "+" if change > 0 else ""
                    print(f"  {key}: {formatted} ({sign}{change}% last 30d)")
                else:
                    print(f"  {key}: {formatted}")


if __name__ == "__main__":
    main()
