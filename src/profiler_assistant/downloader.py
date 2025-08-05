# src/profiler_assistant/downloader.py

import requests
from urllib.parse import urlparse
import tempfile
import os

def get_profile_from_url(short_url: str) -> str:
    """
    Resolves a share.firefox.dev short URL to find the profile token
    and downloads the corresponding raw JSON profile to a temporary file.

    Args:
        short_url (str): The short URL (e.g., "https://share.firefox.dev/3HkKTjj").

    Returns:
        str: The file path to the downloaded temporary profile JSON.
    """
    print(f"[*] Step 1: Resolving short URL: {short_url}")
    
    try:
        response = requests.get(short_url, allow_redirects=True, timeout=15)
        response.raise_for_status()
        full_url = response.url
        print(f"    -> Resolved to: {full_url}")

    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Could not resolve the short URL: {e}")

    print("[*] Step 2: Extracting profile token from the full URL.")
    try:
        path_parts = urlparse(full_url).path.split('/')
        if len(path_parts) > 2 and path_parts[1] == 'public':
            token = path_parts[2]
            print(f"    -> Found token: {token}")
        else:
            # FIX: Raise a ValueError instead of returning None
            raise ValueError(f"Could not find a valid token in the URL path: {full_url}")
    except Exception as e:
        raise ValueError(f"Failed to parse the full URL: {e}")

    download_url = f"https://storage.googleapis.com/profile-store/{token}"
    print(f"[*] Step 3: Downloading from the final storage URL: {download_url}")

    temp_dir = tempfile.gettempdir()
    output_filename = os.path.join(temp_dir, f"profile_{token}.json")

    try:
        with requests.get(download_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            print(f"    -> Downloading profile to '{output_filename}' ({total_size / 1024 / 1024:.2f} MB)...")
            
            with open(output_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        print(f"[+] Success! Profile temporarily saved as '{output_filename}'")
        return output_filename

    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Failed to download the profile JSON: {e}")