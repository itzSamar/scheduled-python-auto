"""
Analyze YouTube channel performance - identify top performing videos and patterns.
"""
import sys
import json
from datetime import datetime, timedelta
from youtube_uploader import YouTubeUploader
from config import REQUIRED_CHANNEL_NAME

def get_channel_id(youtube_service, channel_name):
    """Get channel ID from channel name."""
    try:
        request = youtube_service.search().list(
            part="snippet",
            q=channel_name,
            type="channel",
            maxResults=1
        )
        response = request.execute()
        
        if response.get("items"):
            channel_id = response["items"][0]["snippet"]["channelId"]
            return channel_id
        return None
    except Exception as e:
        print(f"Error getting channel ID: {e}")
        return None

def get_channel_videos(youtube_service, channel_id, max_results=50):
    """Get all videos from a channel."""
    videos = []
    next_page_token = None
    
    try:
        while len(videos) < max_results:
            request = youtube_service.search().list(
                part="snippet",
                channelId=channel_id,
                type="video",
                maxResults=min(50, max_results - len(videos)),
                order="date",  # Most recent first
                pageToken=next_page_token
            )
            response = request.execute()
            
            video_items = response.get("items", [])
            video_ids = [item["id"]["videoId"] for item in video_items]
            
            if not video_ids:
                break
            
            # Get detailed statistics for each video
            stats_request = youtube_service.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(video_ids)
            )
            stats_response = stats_request.execute()
            
            for video in stats_response.get("items", []):
                video_data = {
                    "video_id": video["id"],
                    "title": video["snippet"]["title"],
                    "description": video["snippet"]["description"][:200] if video["snippet"].get("description") else "",
                    "published_at": video["snippet"]["publishedAt"],
                    "views": int(video["statistics"].get("viewCount", 0)),
                    "likes": int(video["statistics"].get("likeCount", 0)),
                    "comments": int(video["statistics"].get("commentCount", 0)),
                    "duration": video["contentDetails"].get("duration", ""),
                    "tags": video["snippet"].get("tags", []),
                    "hashtags": [tag for tag in video["snippet"].get("tags", []) if tag.startswith("#")],
                }
                
                # Calculate engagement metrics
                if video_data["views"] > 0:
                    video_data["like_rate"] = (video_data["likes"] / video_data["views"]) * 100
                    video_data["comment_rate"] = (video_data["comments"] / video_data["views"]) * 100
                    video_data["engagement_rate"] = ((video_data["likes"] + video_data["comments"]) / video_data["views"]) * 100
                else:
                    video_data["like_rate"] = 0
                    video_data["comment_rate"] = 0
                    video_data["engagement_rate"] = 0
                
                # Calculate age in days
                published = datetime.fromisoformat(video_data["published_at"].replace("Z", "+00:00"))
                age_days = (datetime.now(published.tzinfo) - published).days
                video_data["age_days"] = age_days
                
                # Calculate views per day
                if age_days > 0:
                    video_data["views_per_day"] = video_data["views"] / age_days
                else:
                    video_data["views_per_day"] = video_data["views"]
                
                videos.append(video_data)
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
                
    except Exception as e:
        print(f"Error fetching videos: {e}")
        import traceback
        traceback.print_exc()
    
    return videos

def analyze_performance(videos):
    """Analyze video performance and identify patterns."""
    if not videos:
        print("No videos to analyze")
        return
    
    # Sort by different metrics
    by_views = sorted(videos, key=lambda x: x["views"], reverse=True)
    by_engagement = sorted(videos, key=lambda x: x["engagement_rate"], reverse=True)
    by_views_per_day = sorted(videos, key=lambda x: x["views_per_day"], reverse=True)
    
    print("\n" + "="*80)
    print("CHANNEL PERFORMANCE ANALYSIS")
    print("="*80)
    print(f"\nTotal Videos Analyzed: {len(videos)}")
    
    # Top 10 by views
    print("\n" + "-"*80)
    print("TOP 10 VIDEOS BY TOTAL VIEWS")
    print("-"*80)
    for i, video in enumerate(by_views[:10], 1):
        print(f"\n{i}. {video['title'][:60]}")
        print(f"   Views: {video['views']:,} | Likes: {video['likes']:,} | Comments: {video['comments']:,}")
        print(f"   Engagement Rate: {video['engagement_rate']:.2f}% | Age: {video['age_days']} days")
        print(f"   Views/Day: {video['views_per_day']:.1f} | URL: https://youtube.com/watch?v={video['video_id']}")
    
    # Top 10 by engagement rate
    print("\n" + "-"*80)
    print("TOP 10 VIDEOS BY ENGAGEMENT RATE")
    print("-"*80)
    for i, video in enumerate(by_engagement[:10], 1):
        if video['views'] > 10:  # Only show videos with some views
            print(f"\n{i}. {video['title'][:60]}")
            print(f"   Engagement: {video['engagement_rate']:.2f}% | Views: {video['views']:,}")
            print(f"   Likes: {video['likes']:,} | Comments: {video['comments']:,}")
            print(f"   URL: https://youtube.com/watch?v={video['video_id']}")
    
    # Top 10 by views per day (viral potential)
    print("\n" + "-"*80)
    print("TOP 10 VIDEOS BY VIEWS PER DAY (VIRAL POTENTIAL)")
    print("-"*80)
    for i, video in enumerate(by_views_per_day[:10], 1):
        if video['age_days'] > 0:  # Only show videos older than 1 day
            print(f"\n{i}. {video['title'][:60]}")
            print(f"   Views/Day: {video['views_per_day']:.1f} | Total Views: {video['views']:,}")
            print(f"   Age: {video['age_days']} days | Engagement: {video['engagement_rate']:.2f}%")
            print(f"   URL: https://youtube.com/watch?v={video['video_id']}")
    
    # Pattern analysis
    print("\n" + "-"*80)
    print("PATTERN ANALYSIS")
    print("-"*80)
    
    # Analyze titles
    top_titles = [v['title'] for v in by_views[:10]]
    print("\nCommon words in top-performing titles:")
    word_count = {}
    for title in top_titles:
        words = title.lower().split()
        for word in words:
            # Remove common words and keep meaningful ones
            if len(word) > 3 and word not in ['the', 'this', 'that', 'with', 'from', 'your', 'you', 'are', 'for', 'and', 'but', 'not', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use']:
                word_count[word] = word_count.get(word, 0) + 1
    
    common_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:10]
    for word, count in common_words:
        print(f"  '{word}': appears in {count} top videos")
    
    # Analyze hashtags
    all_hashtags = []
    for video in by_views[:20]:
        all_hashtags.extend(video.get('hashtags', []))
    
    hashtag_count = {}
    for tag in all_hashtags:
        hashtag_count[tag] = hashtag_count.get(tag, 0) + 1
    
    if hashtag_count:
        print("\nMost common hashtags in top videos:")
        for tag, count in sorted(hashtag_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {tag}: {count} times")
    
    # Average metrics
    avg_views = sum(v['views'] for v in videos) / len(videos)
    avg_engagement = sum(v['engagement_rate'] for v in videos) / len(videos)
    avg_views_per_day = sum(v['views_per_day'] for v in videos) / len(videos)
    
    print(f"\nAverage Metrics Across All Videos:")
    print(f"  Average Views: {avg_views:,.0f}")
    print(f"  Average Engagement Rate: {avg_engagement:.2f}%")
    print(f"  Average Views/Day: {avg_views_per_day:.1f}")
    
    # Videos above average
    above_avg = [v for v in videos if v['views'] > avg_views]
    print(f"\nVideos Above Average Views: {len(above_avg)} ({len(above_avg)/len(videos)*100:.1f}%)")
    
    # Recent vs older performance
    recent_videos = [v for v in videos if v['age_days'] <= 7]
    older_videos = [v for v in videos if v['age_days'] > 7]
    
    if recent_videos and older_videos:
        recent_avg_views = sum(v['views'] for v in recent_videos) / len(recent_videos)
        older_avg_views = sum(v['views'] for v in older_videos) / len(older_videos)
        print(f"\nPerformance Comparison:")
        print(f"  Recent videos (last 7 days): {len(recent_videos)} videos, avg {recent_avg_views:,.0f} views")
        print(f"  Older videos (>7 days): {len(older_videos)} videos, avg {older_avg_views:,.0f} views")
    
    # Save detailed data to JSON
    output_file = "channel_analysis.json"
    with open(output_file, 'w') as f:
        json.dump({
            "analysis_date": datetime.now().isoformat(),
            "total_videos": len(videos),
            "top_by_views": by_views[:20],
            "top_by_engagement": by_engagement[:20],
            "top_by_views_per_day": by_views_per_day[:20],
            "average_metrics": {
                "views": avg_views,
                "engagement_rate": avg_engagement,
                "views_per_day": avg_views_per_day
            },
            "all_videos": videos
        }, f, indent=2)
    
    print(f"\n✓ Detailed analysis saved to: {output_file}")

def main():
    """Main analysis function."""
    print("Initializing YouTube API...")
    uploader = YouTubeUploader()
    
    print(f"Finding channel: {REQUIRED_CHANNEL_NAME}")
    channel_id = get_channel_id(uploader.youtube_service, REQUIRED_CHANNEL_NAME)
    
    if not channel_id:
        print(f"Could not find channel: {REQUIRED_CHANNEL_NAME}")
        return
    
    print(f"Channel ID: {channel_id}")
    print("Fetching videos...")
    
    videos = get_channel_videos(uploader.youtube_service, channel_id, max_results=100)
    
    if not videos:
        print("No videos found")
        return
    
    analyze_performance(videos)

if __name__ == "__main__":
    main()

