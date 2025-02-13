import pandas as pd
import ast
from tqdm import tqdm
from collections import Counter
from langchain_community.llms import Ollama
from langchain.schema import HumanMessage
import ace_tools_open as tools  # Corrected tools import
from langdetect import detect
from deep_translator import GoogleTranslator  # For translation
import matplotlib.pyplot as plt


class InstagramSentimentAnalyzer:
    def __init__(self, file_path, model_name="qwen2.5:7b-instruct", temperature=0):
        self.file_path = file_path
        self.df = pd.read_csv(file_path)
        self.model = Ollama(model=model_name, temperature=temperature)

    def preprocess_comments(self):
        """Convert comments column from string to list if needed."""
        if "comments" in self.df.columns:
            self.df["comments"] = self.df["comments"].apply(
                # convert the string representation of a comment list in the .csv file to a list
                lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith("[") else []
            )
        else:
            print("Warning: 'comments' column is missing in the CSV.")

    def detect_and_translate(self, comment):
        """Detects the language and translates the comment to English if needed."""
        try:
            detected_lang = detect(comment)
            if detected_lang == "en":
                return comment  # Already in English
            translated_comment = GoogleTranslator(source="auto", target="en").translate(comment)
            return translated_comment
        except Exception as e:
            print(f"Error in language detection/translation: {e}")
            return comment  # Return original if detection/translation fails

    def analyze_sentiment(self, comment):
        """Classifies sentiment as positive, neutral, or negative using Ollama."""
        if not comment.strip():
            return "neutral"

        # Detect and translate if needed
        comment = self.detect_and_translate(comment)

        prompt = f"Classify the sentiment of this comment as 'positive', 'neutral', or 'negative':\n\n\"{comment}. Give your answer in just ONE SINGLE WORD.\""

        try:
            response = self.model.invoke([HumanMessage(content=prompt)]).strip().lower()
            keywords = ["positive", "neutral", "negative"]
            for keyword in keywords:
                if keyword in response:
                    return keyword
            else:
                print(f"Warning: Unexpected sentiment response '{response}', defaulting to 'neutral'.")
                return "neutral"
        except Exception as e:
            print(f"Error in sentiment analysis: {e}")
            return "neutral"


    def apply_sentiment_analysis(self):
        """Applies sentiment analysis to all comments in the dataset with a progress bar."""
        comment_sentiments = []  # Store results temporarily
        
        # Wrap tqdm around iterrows() for tracking progress
        for _, row in tqdm(self.df.iterrows(), total=len(self.df), desc="Analyzing Sentiments"):
            comments = row["comments"]
            if isinstance(comments, list):
                sentiment_list = [self.analyze_sentiment(comment) for comment in comments]
            else:
                sentiment_list = []
            comment_sentiments.append(sentiment_list)

        # Assign processed sentiments back to the dataframe
        self.df["comment_sentiments"] = comment_sentiments


    def summarize_sentiment(self, sentiments):
        """Computes an average sentiment score for a post based on individual comment sentiments."""
        if not sentiments:
            return 0  # Return 0 for neutral if there are no sentiments
        # Assign numerical values to sentiment labels
        sentiment_values = {"positive": 1, "neutral": 0, "negative": -1}
        # Calculate the total score
        total_score = sum(sentiment_values.get(sentiment, 0) for sentiment in sentiments)
        # Compute the average score
        average_score = total_score / len(sentiments)
        return average_score


    def compute_overall_sentiment(self):
        """Computes overall sentiment for each post."""
        self.df["overall_sentiment"] = self.df["comment_sentiments"].apply(self.summarize_sentiment)

    def compute_category_metrics(self):
        """
        Computes the following metrics for two categories of Instagram posts:
        
        Category 1: Posts that include the hashtag "traditionalchinesearchitecture".
        Category 2: Posts with other hashtags (modern Chinese architecture).
        
        For each category, it computes:
        - Average overall sentiment for all posts.
        - Average overall sentiment for posts with comments (comment_count > 0).
        - Average number of likes.
        - Average number of comments.
        """
        if "hashtag" not in self.df.columns:
            print("Warning: 'hashtags' column not found. Cannot compute category metrics.")
            return

        # Create a boolean column 'is_traditional' that is True if the post includes the hashtag.
        self.df["is_traditional"] = self.df["hashtag"].str.contains("traditionalchinesearchitecture", case=False, na=False)

        # Split the DataFrame into two categories.
        df_traditional = self.df[self.df["is_traditional"]]
        df_modern = self.df[~self.df["is_traditional"]]

        def compute_metrics(df_subset):
            # Average overall sentiment for all posts.
            avg_sentiment_all = df_subset["overall_sentiment"].mean()

            # Average overall sentiment for posts with at least one comment.
            if "comment_count" in df_subset.columns:
                df_with_comments = df_subset[df_subset["comment_count"] > 0]
                avg_sentiment_comments = df_with_comments["overall_sentiment"].mean() if not df_with_comments.empty else None
            else:
                avg_sentiment_comments = None

            # Average likes and comments.
            avg_likes = df_subset["likes"].mean() if "likes" in df_subset.columns else None
            avg_comments = df_subset["comment_count"].mean() if "comment_count" in df_subset.columns else None

            return {
                "avg_overall_sentiment_all": avg_sentiment_all,
                "avg_overall_sentiment_with_comments": avg_sentiment_comments,
                "avg_likes": avg_likes,
                "avg_comments": avg_comments
            }

        metrics_traditional = compute_metrics(df_traditional)
        metrics_modern = compute_metrics(df_modern)

        # Create a new DataFrame to hold the metrics as rows
        metrics_data = [
            ["traditional", metrics_traditional['avg_overall_sentiment_all'], metrics_traditional['avg_overall_sentiment_with_comments'], metrics_traditional['avg_likes'], metrics_traditional['avg_comments']],
            ["modern", metrics_modern['avg_overall_sentiment_all'], metrics_modern['avg_overall_sentiment_with_comments'], metrics_modern['avg_likes'], metrics_modern['avg_comments']]
        ]
        metrics_df = pd.DataFrame(metrics_data, columns=["Category", "avg_overall_sentiment_all", "avg_overall_sentiment_with_comments", "avg_likes", "avg_comments"])

        # Save the metrics to a new CSV file
        metrics_df.to_csv("instagram_post_metrics.csv", index=False, encoding="utf-8-sig")
        def plot_metrics(metrics_df):
            categories = ['traditional', 'modern']
            metrics = ['avg_overall_sentiment_all', 'avg_overall_sentiment_with_comments', 'avg_likes', 'avg_comments']
            metrics_labels = ['Avg Overall Sentiment (All)', 'Avg Overall Sentiment (With Comments)', 'Avg Likes', 'Avg Comments']

            # Extract data for plotting
            data = {category: [metrics_df[metrics_df['Category'] == category][metric].values[0] for metric in metrics] for category in categories}

            x = range(len(metrics))

            fig, ax1 = plt.subplots(figsize=(12, 6))
            bar_width = 0.35

            ax2 = ax1.twinx()  # Create a secondary y-axis

            # Plot bars for each category
            for i, category in enumerate(categories):
                ax1.bar([p + i * bar_width for p in x[:2]], data[category][:2], width=bar_width, label=f'{category} (Sentiment)', color='blue' if category == 'traditional' else 'orange')
                ax2.bar([p + i * bar_width for p in x[2:]], data[category][2:], width=bar_width, label=f'{category} (Likes/Comments)', color='blue' if category == 'traditional' else 'orange', alpha=0.5)

            ax1.set_xlabel('Metrics')
            ax1.set_ylabel('Sentiment Scores')
            ax2.set_ylabel('Likes/Comments')

            ax1.set_title('Instagram Post Metrics by Category')
            ax1.set_xticks([p + bar_width for p in x])
            ax1.set_xticklabels(metrics_labels)
            fig.tight_layout()
            fig.legend(loc='upper right', bbox_to_anchor=(1, 1), fontsize='small')
            plt.savefig("instagram_post_metrics.png", format='png', bbox_inches='tight')
            plt.show()

        # Save the results
        self.save_results("instagram_posts_sentiment_analysis_results.csv")
        plot_metrics(metrics_df)


    def save_results(self, updated_file_path):
        """Saves results and displays DataFrame if not empty."""
        if not self.df.empty:
            self.df.to_csv(updated_file_path, index=False, encoding="utf-8-sig")
            tools.display_dataframe_to_user(name="Instagram Sentiment Analysis", dataframe=self.df)
        else:
            print("Warning: DataFrame is empty. No results saved.")

    def run_analysis(self, updated_file_path):
        """Runs the full sentiment analysis pipeline."""
        # self.df = self.df.head(20)  # Limit to first 20 rows for testing
        # self.preprocess_comments()  # for testing
        # self.apply_sentiment_analysis()
        # self.compute_overall_sentiment()
        self.compute_category_metrics()
        self.save_results(updated_file_path)


# Usage
input_file_path = "instagram_posts_data.csv"
results_file_path = "instagram_posts_sentiment_analysis_results.csv"

analyzer = InstagramSentimentAnalyzer(results_file_path)
analyzer.run_analysis(results_file_path)
