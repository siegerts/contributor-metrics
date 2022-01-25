# Contributor Metrics

Backend infrastructure to monitor Issues, Pull Requests, and Issue Events.

## Deployment

The deployment of the backend scheduled Lambda functions is managed by [AWS Chalice](https://aws.github.io/chalice/index.html).

```
chalice deploy
```

### Secrets

Create secure parameters (_SecureString_) in AWS Systems Manager
Parameter Store to coincide with the pattern as specified in `app.py`. For example -

```
token = get_parameter("/contributor-metrics/{env-name}/{var-name}", True)
db_url = get_parameter("/contributor-metrics/{env-name}/{var-name", True)
```

### Database

Create the database tables using `create_all()`. This will create `PullRequest`, `Member`, `Issue`, `Event`, and `EventPoll` tables. The below example loads the environment variables using `dotenv`. When deployed, these secrets are retrieved from SSM (above).

```python

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from models import Member, PullRequest, Issue, create_all, create_db_session

    load_dotenv()

    token = os.getenv("GH_TOKEN")
    db_url = os.getenv("DB_URL")

    gh = GitHubAPI(token=token)
    db = create_db_session(db_url)

    create_all(db_url)

```

### Backfilling data

There are two utilities,`backfill_org_prs` and `backfill_org_issues`, to backfill data.

```python

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from models import Member, PullRequest, Issue, create_all, create_db_session

    load_dotenv()

    token = os.getenv("GH_TOKEN")
    db_url = os.getenv("DB_URL")

    gh = GitHubAPI(token=token)
    db = create_db_session(db_url)

    create_all(db_url)

    backfill_org_prs(db, gh)
    backfill_org_issues(db, gh)

```

## Development

### Lambda environment

The Lambdas make use of Python, SQlAlchemy, and the GitHub API.

To develop locally, create a Python virtual environment using `requirements.txt`.

```
pyenv virtualenv 3.8.3 contributor-metrics
pyenv activate contributor-metrics
```

```
pip install -r requirements.txt
```

Activate the environment:

```
pyenv contributor-metrics
```

### Custom policy

The `policy.json` provides access from the Lambda functions to the secrets stored in SSM.

```
{
  "Effect": "Allow",
  "Action": [
      "ssm:GetParameter"
  ],
  "Resource": "arn:*:ssm:*:*:parameter/contributor-metrics/*/*"
}
```

This is added in the `config.json`.
