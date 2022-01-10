# Contributor Metrics

Backend infrastructure to monitor Issues, Pull Requests, and Issue Events.


## Deployment

The deployment of the backend scheduled Lambda functions is managed by [AWS Chalice](https://aws.github.io/chalice/index.html).

```
chalice deploy
```


## Development

### Lambda environment

The Lambdas make use of Python, SQlAlchemy, and the GitHub API.

To develop locally, create a Python virtual enviroment using `requirements.txt`.

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

### Database

Postgres

### Secrets

Create parameters in parameter store to coincide with the pattern as specified in `app.py`. For example -

```
token = get_parameter("/contributor-metrics/{env-name}/{var-name}", True)
db_url = get_parameter("/contributor-metrics/{env-name}/{var-name", True)
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


## Backfilling data






