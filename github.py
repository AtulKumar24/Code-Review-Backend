import base64
import requests
import os
import dotenv
from LLM import code_review
from typing import Optional


HEADERS = {
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
    "Accept": "application/vnd.github+json"
}


def parseUrl(url : str) : 
    parts = url.replace("https://github.com/", "").split("/")
    return parts[0], parts[1]

def get_repo_tree(owner: str, repo: str):
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
    
    res = requests.get(url , headers=HEADERS)
    if res.status_code != 200:
        raise Exception(f"Failed to fetch repo tree: {res.status_code} - {res.text}")
    return res.json()["tree"]


def get_file_content(owner, repo, path):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    data = res.json()
    return base64.b64decode(data["content"]).decode("utf-8")







def get_github_file(url: str):
    owner, repo = parseUrl(url)
    tree = get_repo_tree(owner, repo)
    
    files = {}
    for item in tree:
        if item["type"] == "blob":
            file_path = item["path"]
            try:
                content = get_file_content(owner, repo, file_path)
                files[file_path] = content
            except Exception as e:
                print(f"Failed to fetch content for {file_path}: {e}")
    return files

def get_latest_commit_sha(owner: str, repo: str, path: Optional[str] = None):
    """
    Fetches the latest commit SHA for a repository or a specific file.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"path": path, "per_page": 1} if path else {"per_page": 1}
    
    res = requests.get(url, headers=HEADERS, params=params)
    if res.status_code != 200:
        raise Exception(f"Failed to fetch commits: {res.status_code} - {res.text}")
    
    commits = res.json()
    if not commits:
        raise Exception(f"No commits found for path: {path}")
        
    return commits[0]["sha"]