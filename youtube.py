import requests

def get_youtube_links(api_key, search_query):
    """
    Fetches 5 YouTube video links for a given search query using the YouTube Data API v3.

    Parameters:
        api_key (str): Your YouTube Data API v3 key.
        search_query (str): The search query.

    Returns:
        list: A list of 5 YouTube video links.
    """
    base_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": search_query,
        "type": "video",
        "maxResults": 5,  # Limit to 5 results
        "key": api_key
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()
        video_links = [
            f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            for item in data.get("items", [])
            if item["id"]["kind"] == "youtube#video"
        ]
        return video_links
    else:
        print(f"Error: {response.status_code}, {response.json()}")
        return []


