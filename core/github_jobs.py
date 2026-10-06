import base64
import json
import urllib.request
import urllib.error


REPO_OWNER = "miang20"
REPO_NAME = "auto-faceless-video-creator"


def create_github_job(token: str, job: dict) -> str:
    job_id = job["job_id"]
    path = f"jobs/{job_id}.json"

    content = json.dumps(job, indent=2).encode("utf-8")
    encoded_content = base64.b64encode(content).decode("utf-8")

    url = (
        f"https://api.github.com/repos/"
        f"{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    )

    payload = json.dumps({
        "message": f"Create job {job_id}",
        "content": encoded_content,
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in (200, 201):
                raise RuntimeError(
                    f"GitHub API returned status {response.status}"
                )

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API error {e.code}: {error_body}"
        ) from e

    return path
