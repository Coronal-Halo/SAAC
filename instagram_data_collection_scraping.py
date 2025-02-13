import os
import subprocess
import json
import pandas as pd
import requests
import re
from tqdm import tqdm
import html
import os
from dotenv import load_dotenv

# Load the .env file. By default, load_dotenv() looks for a .env file in the current working directory.
load_dotenv()

class InstagramScraper:
    def __init__(self, conda_env, output_dir, hashtags, archive_file="archive.sqlite3"):
        self.conda_env = conda_env
        self.output_dir = output_dir
        self.hashtags = hashtags
        self.archive_file = archive_file

        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"📁 Created directory: {self.output_dir}")

    def scrape_hashtag(self, hashtag, post_limit=250):
        """Runs gallery-dl to scrape Instagram posts for a given hashtag."""
        cmd = f"source ~/.bashrc conda activate {self.conda_env} && \
                gallery-dl --write-metadata --range 1-{post_limit} --filter \"extension in ('jpg', 'png', 'webp')\" -o {self.output_dir} -d {self.output_dir} \
                --download-archive {self.archive_file} https://www.instagram.com/explore/tags/{hashtag}/"
        subprocess.run(cmd, shell=True, executable="/bin/bash")
        print(f"✅ Download complete for #{hashtag}")

    def scrape_all(self, post_limit=250):
        """Scrapes all hashtags in the list."""
        for hashtag in self.hashtags:
            self.scrape_hashtag(hashtag, post_limit)

class InstagramDataProcessor:
    def __init__(self, base_directory):
        self.base_directory = base_directory
        self.posts_data = []

    def find_json_files(self):
        """Recursively find all JSON files in nested directories."""
        json_files = []
        for root, _, files in os.walk(self.base_directory):
            for file in files:
                if file.endswith(".json"):
                    json_files.append(os.path.join(root, file))
        return json_files

    def load_metadata(self):
        """Loads metadata from all found JSON files and includes the hashtag."""
        json_files = self.find_json_files()
        for file_path in json_files:
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    post_data = json.load(f)
                    # Extract hashtag from directory structure
                    hashtag = os.path.basename(os.path.dirname(file_path))
                    post_data["hashtag"] = hashtag

                    # Exclude entries where file type is mp4
                    if post_data.get("extension", "") != "mp4":
                        self.posts_data.append(post_data)
                except json.JSONDecodeError:
                    print(f"❌ Error decoding JSON in file: {file_path}")
    
    def save_to_csv(self, output_file):
        """Saves collected metadata to a CSV file."""
        df = pd.DataFrame(self.posts_data)
        df.to_csv(output_file, mode="w", index=False)
        print(f"✅ Data saved to {output_file}")

    def save_to_excel(self, output_file):
        """Saves collected metadata to an Excel file with two sheets."""
        df = pd.DataFrame(self.posts_data)
        
        # Split data into two sheets
        df_traditional = df[df["hashtag"] == "traditionalchinesearchitecture"]
        df_other = df[df["hashtag"] != "traditionalchinesearchitecture"]
        
        with pd.ExcelWriter(output_file, engine="xlsxwriter", mode="w") as writer:
            df_traditional.to_excel(writer, sheet_name="Traditional", index=False)
            df_other.to_excel(writer, sheet_name="Modern", index=False)
        
        print(f"✅ Data saved to {output_file}")


class ModashClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url_mediainfo = "https://api.modash.io/v1/raw/ig/media-info"
        self.base_url_mediacomments = "https://api.modash.io/v1/raw/ig/media-comments"

    def extract_shortcode(self, post_url):
        """Extracts the shortcode from the post URL."""
        match = re.search(r"instagram.com/p/([a-zA-Z0-9_-]+)/", post_url)
        return match.group(1) if match else None

    def get_post_engagement(self, csv_file):
        """Reads from the CSV file and fetches comment count, view count, share count, and actual comments for each post."""
        df = pd.read_csv(csv_file)
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }
        
        mediainfo_data_list = []
        mediacomment_data_list = []
        comment_count_list = []
        comments_list = []

        num_posts_obtained = 0
        for _, row in tqdm(df.iterrows(), total=df.shape[0], desc="Fetching engagement data"):
            post_url = row.get("post_url")
            shortcode = self.extract_shortcode(post_url) if post_url else None
            if shortcode:
                url_mediainfo = f"{self.base_url_mediainfo}?code={shortcode}"
                url_mediacomments = f"{self.base_url_mediacomments}?code={shortcode}"
                response_mediainfo = requests.get(url_mediainfo, headers=headers)
                response_mediacomments = requests.get(url_mediacomments, headers=headers)

                if response_mediainfo.status_code == 200:
                    data_mediainfo_json = response_mediainfo.json()
                    # data_mediainfo_json["shortcode"] = shortcode
                    # mediainfo_data_list.append(data_mediainfo_json)
                    comment_count_list.append(data_mediainfo_json['items'][0].get("comment_count", 0))
                    print(f"media info for post_url {post_url} has been collected.")
                else:
                    print(f"❌ Error fetching media info data for post {shortcode}: {response_mediainfo.status_code}")

                if response_mediacomments.status_code == 200:
                    data_mediacomments_json = response_mediacomments.json()
                    # data_mediacomments_json["shortcode"] = shortcode
                    # mediacomment_data_list.append(data_mediacomments_json)
                    comments_obj_list = data_mediacomments_json.get("comments", [{'text':''}])
                    comments_text_list = []
                    for comment_obj in comments_obj_list:
                        comments_text_list.append(html.unescape(comment_obj['text']))
                    comments_list.append(comments_text_list)
                    print(f"media comments for post_url {post_url} has been collected.")
                else:
                    comments_list.append([])
                    print(f"❌ Error fetching media comments data for post {shortcode}: {response_mediacomments.status_code}")

            else:
                comment_count_list.append(None)
                comments_list.append(None)
            
            num_posts_obtained += 1
            if num_posts_obtained % 10 == 0:
                df.loc[df.index[:num_posts_obtained], "comment_count"] = comment_count_list
                df.loc[df.index[:num_posts_obtained], "comments"] = [json.dumps(comments, ensure_ascii=False) for comments in comments_list]  # Convert list of lists into JSON strings
                df.to_csv(csv_file, index=False, encoding="utf-8-sig")
                
        # Update dataframe with new columns
        # Assign new data to the top_n rows in the original DataFrame
        # df.loc[df.index[:10], "comment_count"] = comment_count_list
        # df.loc[df.index[:10], "comments"] = [json.dumps(comments, ensure_ascii=False) for comments in comments_list]  # Convert list of lists into JSON strings
        df["comment_count"] = comment_count_list
        df["comments"] = [json.dumps(comments, ensure_ascii=False) for comments in comments_list]
        # Save updated CSV
        df.to_csv(csv_file, index=False, encoding="utf-8-sig")  # use "utf-8-sig" encoding to make excel display the text correctly
        print(f"media info and comments data saved to {csv_file}")



if __name__ == "__main__":
    # Configuration
    CONDA_ENV_NAME = "saac"
    OUTPUT_DIR = "posts"
    # HASHTAGS = [
        # "traditionalchinesearchitecture", "modernchinesearchitecture",
        # "contemporarychinesearchitecture", "chineseskyscrapers", "shanghaiskyscraper", 
        # "shenzhenskyscraper", "beijingskyscraper", "hangzhouskyscraper", "guangzhouskyscraper"
        # "chongqingskyscraper", "nanjingskyscraper", "chengduskyscraper", "hongkongskyscrapers"
    # ]
    CSV_OUTPUT_PATH = "./results/instagram_posts_data.csv"
    EXCEL_OUTPUT_PATH = "./results/instagram_posts_data.xlsx"
    MODASH_API_KEY = os.getenv("MODASH_API_KEY")

    # Scrape Instagram posts
    # scraper = InstagramScraper(CONDA_ENV_NAME, OUTPUT_DIR, ["chengduskyscrapers"])
    # scraper.scrape_all(post_limit=200)

    # Process and save metadata
    # processor = InstagramDataProcessor(OUTPUT_DIR)
    # processor.load_metadata()
    # processor.save_to_csv(CSV_OUTPUT_PATH)
    # processor.save_to_excel(EXCEL_OUTPUT_PATH)

    # Fetch engagement data using Modash API
    modash = ModashClient(MODASH_API_KEY)
    modash.get_post_engagement(CSV_OUTPUT_PATH)
