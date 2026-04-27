import requests
from datetime import datetime, timedelta
import os
from typing import List, Dict
import json

def get_github_comments(repo_owner: str, repo_name: str, token: str) -> List[Dict]:
    """
    Fetch comments from GitHub issues and pull requests for the last two months.
    """
    # Calculate date two months ago
    two_months_ago = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # GitHub API base URL
    base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    all_comments = []
    
    # Get issues and their comments
    issues_url = f"{base_url}/issues"
    params = {
        "state": "all",
        "since": two_months_ago,
        "per_page": 100
    }
    
    response = requests.get(issues_url, headers=headers, params=params)
    issues = response.json()
    
    for issue in issues:
        # Get comments for each issue
        comments_url = f"{base_url}/issues/{issue['number']}/comments"
        comments_response = requests.get(comments_url, headers=headers)
        comments = comments_response.json()
        
        for comment in comments:
            comment_date = datetime.strptime(comment['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if comment_date >= datetime.strptime(two_months_ago, "%Y-%m-%dT%H:%M:%SZ"):
                all_comments.append({
                    'type': 'issue_comment',
                    'issue_number': issue['number'],
                    'issue_title': issue['title'],
                    'author': comment['user']['login'],
                    'body': comment['body'],
                    'created_at': comment['created_at']
                })
    
    # Get pull requests and their comments
    prs_url = f"{base_url}/pulls"
    prs_response = requests.get(prs_url, headers=headers, params=params)
    prs = prs_response.json()
    
    for pr in prs:
        # Get comments for each PR
        comments_url = f"{base_url}/pulls/{pr['number']}/comments"
        comments_response = requests.get(comments_url, headers=headers)
        comments = comments_response.json()
        
        for comment in comments:
            comment_date = datetime.strptime(comment['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if comment_date >= datetime.strptime(two_months_ago, "%Y-%m-%dT%H:%M:%SZ"):
                all_comments.append({
                    'type': 'pr_comment',
                    'pr_number': pr['number'],
                    'pr_title': pr['title'],
                    'author': comment['user']['login'],
                    'body': comment['body'],
                    'created_at': comment['created_at']
                })
    
    return sorted(all_comments, key=lambda x: x['created_at'], reverse=True)

def generate_comment_history(comments: List[Dict], output_file: str):
    """
    Generate a markdown file with the comment history.
    """
    with open(output_file, 'w') as f:
        f.write("# GitHub Comment History (Last 2 Months)\n\n")
        
        for comment in comments:
            f.write(f"## {comment['type'].upper()} - {comment.get('issue_title', comment.get('pr_title', ''))}\n\n")
            f.write(f"**Author:** {comment['author']}\n")
            f.write(f"**Date:** {comment['created_at']}\n")
            f.write(f"**Issue/PR #:** {comment.get('issue_number', comment.get('pr_number', ''))}\n\n")
            f.write(f"{comment['body']}\n\n")
            f.write("---\n\n")

if __name__ == "__main__":
    # Get GitHub token from environment variable
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Please set the GITHUB_TOKEN environment variable")
        exit(1)
    
    # Replace these with your repository details
    repo_owner = "RTI"  # Replace with actual owner
    repo_name = "Genesis_LIB"  # Replace with actual repo name
    
    comments = get_github_comments(repo_owner, repo_name, token)
    generate_comment_history(comments, "docs/notes/comment_history.md") 
