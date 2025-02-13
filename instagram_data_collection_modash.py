import requests
import os
import pandas as pd
import time
import os
from dotenv import load_dotenv

# Load the .env file. By default, load_dotenv() looks for a .env file in the current working directory.
load_dotenv()

# ---- CONFIG ----
API_KEY = os.getenv("MODASH_API_KEY")  # Replace with your Modash API Key
HASHTAG = "chinesearchitecture"
SAVE_FOLDER = "instagram_images"
CSV_FILE = "instagram_data.csv"
POSTS_LIMIT = 3000  # Number of posts to fetch
POSTS_PER_PAGE = 100  # Modash API limit per request

# Ensure save directory exists
os.makedirs(SAVE_FOLDER, exist_ok=True)

class InstagramScraper:
    def __init__(self, api_key, hashtag, post_limit=3000, posts_per_page=100):
        self.api_key = api_key
        self.hashtag = hashtag
        self.post_limit = post_limit
        self.posts_per_page = posts_per_page
        self.modash_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {API_KEY}',
        }
        self.posts_data = []

    def fetch_posts(self):
        """Fetch Instagram posts under a specific hashtag"""
        next_page_token = None
        total_fetched = 0

        while total_fetched < self.post_limit:
            params = {
                "hashtag": self.hashtag,
                "limit": self.posts_per_page,
                "after": next_page_token  # Pagination token
            }

            print(f"Fetching posts {total_fetched + 1} - {total_fetched + self.posts_per_page}...")

            BASE_URL_SEARCH = "https://api.modash.io/v1/raw/ig/search"              # keyword # this is to search for both users and posts under certain hashtag
            BASE_URL_HASHTAG_FEED = "https://api.modash.io/v1/raw/ig/hashtag-feed"  # after (optional), hashtag, type # this is to search for posts under certain hashtag
            BASE_URL_LIST_HASHTAG = "https://api.modash.io/v1/instagram/hashtags"   # limit, query # this is to search for similar hashtags themselves
            url_search = f"{BASE_URL_SEARCH}?keyword=architecture"
            url_hashtag_feed = f"{BASE_URL_HASHTAG_FEED}?hashtag=architecture?type=recent"
            url_list_hashtag = f"{BASE_URL_LIST_HASHTAG}?query=architecture"

            response_search = requests.get(url_search, headers=self.modash_headers)
            response_hashtag_feed = requests.get(url_hashtag_feed, headers=self.modash_headers)
            response_list_hashtag = requests.get(url_list_hashtag, headers=self.modash_headers)

            if response_search.status_code == 200:
                data = response_search.json()
                posts = data.get("data", [])

                for post in posts:
                    if total_fetched >= self.post_limit:
                        break
                    
                    # Only process image posts (not videos)
                    if post.get("media_type") != "IMAGE":
                        continue

                    post_obj = InstagramPost(post, self.headers)
                    post_obj.fetch_comments()
                    post_obj.download_image()
                    
                    self.posts_data.append(post_obj.to_dict())
                    total_fetched += 1

                # Get next page token (pagination)
                next_page_token = data.get("page", {}).get("next")
                if not next_page_token:
                    break  # No more pages

                time.sleep(1)  # Avoid hitting rate limits

            else:
                print(f"Error {response_search.status_code}: {response_search.text}")
                break

    def save_to_csv(self):
        """Save collected Instagram data to a CSV file"""
        if self.posts_data:
            df = pd.DataFrame(self.posts_data)
            df.to_csv(CSV_FILE, index=False, encoding="utf-8")
            print(f"✅ Successfully saved {len(self.posts_data)} posts to {CSV_FILE}")
        else:
            print("❌ No posts found or API request failed.")


class InstagramPost:
    def __init__(self, post_data, headers):
        """Initialize an Instagram post object"""
        self.post_id = post_data.get("id")
        self.url = post_data.get("permalink")
        self.image_url = post_data.get("media_url")
        self.caption = post_data.get("caption")
        self.likes = post_data.get("like_count")
        self.comments_count = post_data.get("comments_count")
        self.shares = post_data.get("shares_count", "N/A")
        self.timestamp = post_data.get("timestamp")
        self.owner_username = post_data.get("owner", {}).get("username")
        self.headers = headers
        self.comments = ""

    def fetch_comments(self):
        """Fetch comments for the Instagram post"""
        COMMENTS_URL = f"https://api.modash.io/v1/instagram/raw/posts/{self.post_id}/comments"
        
        try:
            response = requests.get(COMMENTS_URL, headers=self.headers)
            if response.status_code == 200:
                comments_data = response.json().get("data", [])
                self.comments = "; ".join([comment["text"] for comment in comments_data])  # Store as a string
            else:
                self.comments = "Error fetching comments"
        except Exception as e:
            self.comments = f"Error: {e}"

    def download_image(self):
        """Download image of the Instagram post"""
        try:
            img_data = requests.get(self.image_url).content
            with open(os.path.join(SAVE_FOLDER, f"{self.post_id}.jpg"), "wb") as img_file:
                img_file.write(img_data)
            print(f"Downloaded image: {self.post_id}.jpg")
        except Exception as e:
            print(f"Error downloading image: {e}")

    def to_dict(self):
        """Convert Instagram post object to dictionary format"""
        return {
            "Post ID": self.post_id,
            "Post URL": self.url,
            "Image URL": self.image_url,
            "Caption": self.caption,
            "Likes": self.likes,
            "Comments Count": self.comments_count,
            "Shares": self.shares,
            "Timestamp": self.timestamp,
            "Owner Username": self.owner_username,
            "Comments": self.comments
        }

# ---- MAIN SCRIPT ----
if __name__ == "__main__":
    print("Starting Instagram Scraper...")

    scraper = InstagramScraper(api_key=API_KEY, hashtag=HASHTAG, post_limit=POSTS_LIMIT, posts_per_page=POSTS_PER_PAGE)
    scraper.fetch_posts()
    scraper.save_to_csv()





