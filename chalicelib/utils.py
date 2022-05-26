import logging

import boto3
from botocore.exceptions import ClientError


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
    print(get_parameter("", True))
