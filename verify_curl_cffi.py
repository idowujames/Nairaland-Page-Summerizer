from curl_cffi import requests

url = "https://www.nairaland.com/390522/solar-energy-complement-fta"

try:
    print(f"Testing curl_cffi with {url}...")
    response = requests.get(url, impersonate="chrome110", timeout=15)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! curl_cffi worked.")
        print(f"Content length: {len(response.text)}")
    else:
        print(f"Failed via curl_cffi with status {response.status_code}.")
except Exception as e:
    print(f"Error: {e}")
