# Contributor metrics

## create parameters in parameter store

## set lambda timeout

300 seconds / 5 min

```
{
  "version": "2.0",
  "app_name": "contributor-metrics",
  "stages": {
    "dev": {
      "api_gateway_stage": "api",
      "lambda_timeout": 300,
      "automatic_layer": true
    }
  }
}
```

## deployment

```
chalice deploy
```

## permissions to access ssm

policy

deployment

```
chalice deploy
```

lambda config
set min/max dates
org

## db setup

or local config

---

reporting ui

```
pyenv virtualenv 3.8.3 contributor-metrics
pyenv activate contributor-metrics
```

```
pip install -r requirements.txt
```
