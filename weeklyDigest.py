import requests

def test(api_key, server_url="http://localhost:8096"):
    # Triggers an incremental library update so the movie shows up instantly
    url = f"{server_url}/Users"
    headers = {"X-MediaBrowser-Token": api_key}
    try:
        response = requests.get(url, headers=headers)
        print(response.json())
        if response.status_code == 200:
            print("Jellyfin request successfull!")
    except Exception as e:
        print(f"Failed to alert Jellyfin: {e}")

def main():
    api_key = '055c826723a6469a95cd5fb05596d166'
    test(api_key)
        
        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as e:
        print( "ok, bye!")
