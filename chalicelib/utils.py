import logging
import os
import boto3
from botocore.exceptions import ClientError


def send_plain_email(msg):
    ses_client = boto3.client("ses", region_name="us-east-1")
    CHARSET = "UTF-8"

    send_to = os.getenv("SEND_TO_EMAIL")
    send_from = os.getenv("SEND_FROM_EMAIL")

    response = ses_client.send_email(
        Destination={
            "ToAddresses": [
                send_to,
            ],
        },
        Message={
            "Body": {
                "Text": {
                    "Charset": CHARSET,
                    "Data": f"This is an automated email. {msg}",
                }
            },
            "Subject": {
                "Charset": CHARSET,
                "Data": "Contributor Metrics Ops Disruption",
            },
        },
        Source=send_from,
    )


def put_parameter(parameter_name, parameter_value, parameter_type):
    ssm_client = boto3.client("ssm")
    try:
        result = ssm_client.put_parameter(
            Name=parameter_name, Value=parameter_value, Type=parameter_type
        )
    except ClientError as e:
        logging.error(e)
        return None
    return result["Version"]


def get_parameter(parameter_name, with_decryption):
    ssm_client = boto3.client("ssm")
    try:
        result = ssm_client.get_parameter(
            Name=parameter_name, WithDecryption=with_decryption
        )
    except ClientError as e:
        logging.error(e)
        return None
    return result["Parameter"]["Value"]


if __name__ == "__main__":
    # print(get_parameter("", True))
    from dotenv import load_dotenv

    load_dotenv()

    send_plain_email("auto msg")
