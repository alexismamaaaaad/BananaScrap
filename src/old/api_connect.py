import json
import sys
import urllib.parse

try:
    import requests
    from requests import RequestException
    from requests.exceptions import HTTPError
except ImportError:
    requests = None
    RequestException = Exception
    HTTPError = Exception

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def fetch_json(url: str, params: dict[str, str] | None = None) -> dict:
    url = normalize_url(url)

    if requests:
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            raise RuntimeError(f"HTTP error: {exc.response.status_code} {exc.response.reason}") from exc
        except RequestException as exc:
            raise RuntimeError(f"Request failed: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError("Received invalid JSON") from exc

    import urllib.request
    import urllib.error

    if params:
        query_string = urllib.parse.urlencode(params)
        url = f"{url}?{query_string}"

    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read().decode(response.headers.get_content_charset("utf-8"))
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP error: {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc
    except ValueError as exc:
        raise RuntimeError("Received invalid JSON") from exc


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python api_connect.py <url> [param1=value1 param2=value2 ...]")
        sys.exit(1)

    url = sys.argv[1]
    params = {}
    for pair in sys.argv[2:]:
        if "=" in pair:
            key, value = pair.split("=", 1)
            params[key] = value

    try:
        result = fetch_json(url, params or None)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
