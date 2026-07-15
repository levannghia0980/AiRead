import urllib.request
import json

def try_request(url):
    payload = {"url": "https://www.69shuba.com/txt/83216/39104252"}
    headers = {"Content-Type": "application/json"}
    
    print(f"Trying url: {url} ...")
    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode("utf-8"), 
        headers=headers, 
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            body = response.read().decode("utf-8")
            print(f"Success! Status Code: {status}")
            print("Response:")
            print(body)
            return True
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code}")
        print("Response:")
        print(e.read().decode("utf-8"))
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

def main():
    hosts = ["host.docker.internal", "10.0.2.2", "172.17.0.1"]
    for host in hosts:
        url = f"http://{host}:8000/api/novels/analyze"
        if try_request(url):
            print("Successfully contacted the host backend server!")
            break

if __name__ == "__main__":
    main()
