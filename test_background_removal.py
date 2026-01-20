"""
Test script to try different approaches for removing avatar background
when using video backgrounds. Saves result to generated_videos/test.mp4
"""
import sys
sys.path.insert(0, '.')

from video_generator import VideoGenerator
from youtube_uploader import YouTubeUploader
import json
import os
import requests

# HeyGen API base URL (from video_generator.py)
HEYGEN_API_BASE_URL = "https://api.heygen.com"

# Ensure output directory exists
os.makedirs('generated_videos', exist_ok=True)

print('='*70)
print('TESTING BACKGROUND REMOVAL FOR AVATAR')
print('='*70)

vg = VideoGenerator()

# Step 1: Check avatar metadata
print('\n1. Checking avatar metadata...')
avatars = vg._get_avatars()
if avatars:
    print(f"Found {len(avatars)} avatars")
    sample_avatar = avatars[0]
    print("\nSample avatar keys:")
    print(json.dumps(list(sample_avatar.keys()), indent=2))
    
    # Check for background removal related fields
    bg_fields = [k for k in sample_avatar.keys() if 'background' in k.lower() or 'remove' in k.lower() or 'bg' in k.lower()]
    if bg_fields:
        print(f"\nFound background-related fields: {bg_fields}")
        print(f"Values: {[(k, sample_avatar.get(k)) for k in bg_fields]}")
    else:
        print("\nNo obvious background removal fields found")
    
    # Get a random avatar
    import random
    test_avatar = random.choice(avatars)
    test_avatar_id = test_avatar.get("avatar_id") or test_avatar.get("id")
    print(f"\nUsing test avatar: {test_avatar.get('name', 'Unknown')} (ID: {test_avatar_id})")
else:
    print("No avatars found!")
    sys.exit(1)

# Step 2: Get a Roblox gameplay video asset
print('\n2. Getting Roblox gameplay video background...')
youtube_uploader = YouTubeUploader()
vg.youtube_service = youtube_uploader.youtube_service

test_topic = "Roblox gameplay"
test_keywords = ["roblox", "gameplay"]
video_asset_id = vg._get_roblox_gameplay_video_asset_id(test_topic, test_keywords)

if not video_asset_id:
    print("Failed to get video background, exiting")
    sys.exit(1)

print(f"Got video asset ID: {video_asset_id}")

# Step 3: Try different approaches
test_script = "This is a test video to check if the avatar background is removed when using a video background."

print('\n3. Testing Approach 1: Add remove_background parameter to character...')
print('   Trying: character.remove_background = True')

url = f"{HEYGEN_API_BASE_URL}/v2/video/generate"

# Approach 1: Add remove_background to character
video_input_1 = {
    "character": {
        "type": "avatar",
        "avatar_id": test_avatar_id,
        "avatar_style": "normal",
        "remove_background": True  # Try this parameter
    },
    "voice": {
        "type": "text",
        "input_text": test_script,
        "voice_id": vg._get_random_avatar_and_voice()[1],  # Get a voice
        "speed": 1.0
    },
    "background": {
        "type": "video",
        "video_asset_id": video_asset_id,
        "play_style": "loop"
    }
}

payload_1 = {
    "video_inputs": [video_input_1],
    "dimension": {
        "width": 720,
        "height": 1280
    }
}

print("   Sending request...")
response_1 = requests.post(url, json=payload_1, headers=vg.headers, timeout=30)

if response_1.status_code == 200:
    result_1 = response_1.json()
    video_id_1 = result_1.get("data", {}).get("video_id") or result_1.get("video_id") or result_1.get("data", {}).get("id") or result_1.get("id")
    if video_id_1:
        print(f"   ✓ Approach 1 SUCCESS! Video ID: {video_id_1}")
        print("   Waiting for video to complete...")
        video_url_1 = vg.wait_for_video(video_id_1, timeout=600)
        if video_url_1:
            print(f"   ✓ Video ready! Downloading to test.mp4...")
            if vg.download_video(video_url_1, 'generated_videos/test.mp4'):
                print(f"   ✓ Saved to generated_videos/test.mp4")
                print("\n" + "="*70)
                print("SUCCESS! Check generated_videos/test.mp4 to see if background is removed")
                print("="*70)
                sys.exit(0)
    else:
        print(f"   ✗ Unexpected response: {result_1}")
elif response_1.status_code == 400:
    error_data = response_1.json()
    error_msg = error_data.get("message", "")
    print(f"   ✗ Approach 1 failed: {error_msg}")
    if "remove_background" in error_msg.lower():
        print("   Parameter 'remove_background' not recognized")
else:
    print(f"   ✗ Approach 1 failed: HTTP {response_1.status_code}")

# Approach 2: Try background_removal at payload level
print('\n4. Testing Approach 2: Add background_removal to payload...')
print('   Trying: payload.background_removal = True')

video_input_2 = {
    "character": {
        "type": "avatar",
        "avatar_id": test_avatar_id,
        "avatar_style": "normal"
    },
    "voice": {
        "type": "text",
        "input_text": test_script,
        "voice_id": vg._get_random_avatar_and_voice()[1],
        "speed": 1.0
    },
    "background": {
        "type": "video",
        "video_asset_id": video_asset_id,
        "play_style": "loop"
    }
}

payload_2 = {
    "video_inputs": [video_input_2],
    "dimension": {
        "width": 720,
        "height": 1280
    },
    "background_removal": True  # Try at payload level
}

print("   Sending request...")
response_2 = requests.post(url, json=payload_2, headers=vg.headers, timeout=30)

if response_2.status_code == 200:
    result_2 = response_2.json()
    video_id_2 = result_2.get("data", {}).get("video_id") or result_2.get("video_id") or result_2.get("data", {}).get("id") or result_2.get("id")
    if video_id_2:
        print(f"   ✓ Approach 2 SUCCESS! Video ID: {video_id_2}")
        print("   Waiting for video to complete...")
        video_url_2 = vg.wait_for_video(video_id_2, timeout=600)
        if video_url_2:
            print(f"   ✓ Video ready! Downloading to test.mp4...")
            if vg.download_video(video_url_2, 'generated_videos/test.mp4'):
                print(f"   ✓ Saved to generated_videos/test.mp4")
                print("\n" + "="*70)
                print("SUCCESS! Check generated_videos/test.mp4 to see if background is removed")
                print("="*70)
                sys.exit(0)
    else:
        print(f"   ✗ Unexpected response: {result_2}")
elif response_2.status_code == 400:
    error_data = response_2.json()
    error_msg = error_data.get("message", "")
    print(f"   ✗ Approach 2 failed: {error_msg}")
else:
    print(f"   ✗ Approach 2 failed: HTTP {response_2.status_code}")

# Approach 3: Try without any special parameter (maybe HeyGen does it automatically?)
print('\n5. Testing Approach 3: Standard approach (no special params)...')
print('   Maybe HeyGen removes background automatically when video background is set?')

video_input_3 = {
    "character": {
        "type": "avatar",
        "avatar_id": test_avatar_id,
        "avatar_style": "normal"
    },
    "voice": {
        "type": "text",
        "input_text": test_script,
        "voice_id": vg._get_random_avatar_and_voice()[1],
        "speed": 1.0
    },
    "background": {
        "type": "video",
        "video_asset_id": video_asset_id,
        "play_style": "loop"
    }
}

payload_3 = {
    "video_inputs": [video_input_3],
    "dimension": {
        "width": 720,
        "height": 1280
    }
}

print("   Sending request...")
response_3 = requests.post(url, json=payload_3, headers=vg.headers, timeout=30)

if response_3.status_code == 200:
    result_3 = response_3.json()
    video_id_3 = result_3.get("data", {}).get("video_id") or result_3.get("video_id") or result_3.get("data", {}).get("id") or result_3.get("id")
    if video_id_3:
        print(f"   ✓ Approach 3 SUCCESS! Video ID: {video_id_3}")
        print("   Waiting for video to complete...")
        video_url_3 = vg.wait_for_video(video_id_3, timeout=600)
        if video_url_3:
            print(f"   ✓ Video ready! Downloading to test.mp4...")
            if vg.download_video(video_url_3, 'generated_videos/test.mp4'):
                print(f"   ✓ Saved to generated_videos/test.mp4")
                print("\n" + "="*70)
                print("Video created. Check generated_videos/test.mp4")
                print("Note: This is the current behavior - may still have double background")
                print("="*70)
                sys.exit(0)
    else:
        print(f"   ✗ Unexpected response: {result_3}")
else:
    print(f"   ✗ Approach 3 failed: HTTP {response_3.status_code}")
    print(f"   Response: {response_3.text[:500]}")

print("\n" + "="*70)
print("All approaches tested. Check generated_videos/test.mp4 if any succeeded.")
print("="*70)

