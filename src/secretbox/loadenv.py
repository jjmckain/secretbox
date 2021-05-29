"""
Loads local environment vars and .env file to an accessible object

Author  : Preocts <preocts@preocts.com>
Discord : Preocts#8196
Git Repo: https://github.com/Preocts/secretbox
"""
import json
import logging
import os
from typing import Dict
from typing import Optional

# Optional dependency to supprt AWS Secrets Server
try:
    import boto3
    from botocore.exceptions import ClientError
    from botocore.exceptions import InvalidRegionError
    from botocore.exceptions import NoCredentialsError
    from botocore.exceptions import NoRegionError
    from mypy_boto3_secretsmanager.client import SecretsManagerClient
except ImportError:
    boto3 = None


class LoadEnv:
    """Loads local environment vars and .env file to an accessible object"""

    logger = logging.getLogger(__name__)
    aws_client: Optional[SecretsManagerClient] = None

    def __init__(
        self,
        filename: str = ".env",
        aws_sstore_name: Optional[str] = None,
        aws_region: Optional[str] = None,
        auto_load: bool = False,
    ) -> None:
        """Provide full path and name to .env if not located in working directory"""
        self.filename: str = filename
        self.loaded_values: Dict[str, str] = {}
        self.region = aws_region
        self.sstore = aws_sstore_name
        if auto_load:
            self.load()

    def get(self, key: str) -> str:
        """Get a value by key, will return empty string if not found"""
        return self.loaded_values.get(key, "")

    def load(self) -> None:
        """Loads environment vars, then .env (or provided) file"""
        # TODO: What order do we want to load these?
        self.load_env_vars()
        self.load_env_file()
        if boto3 is not None:
            self.load_aws_store()
        self.push_to_environment()

    def load_env_vars(self) -> None:
        """Loads all visible environmental variables"""
        for key, value in os.environ.items():
            self.loaded_values[key] = value

    def load_env_file(self) -> bool:
        """Loads local .env or from path if provided"""
        try:
            with open(self.filename, "r", encoding="utf-8") as input_file:
                self.__parse_env_file(input_file.read())
        except FileNotFoundError:
            return False
        return True

    def push_to_environment(self) -> None:
        """Pushes loaded values to local environment vars, will overwrite existing"""
        for key, value in self.loaded_values.items():
            os.environ[key] = value

    def __parse_env_file(self, input_file: str) -> None:
        """Parses env file into key-pair values"""
        for line in input_file.split("\n"):
            if not line or line.strip().startswith("#") or len(line.split("=", 1)) != 2:
                continue
            key, value = line.split("=", 1)
            self.loaded_values[key.strip()] = value.strip()

    def __connect_aws_client(self) -> None:
        """Make connection"""
        if self.aws_client is not None or self.region is None:
            return

        if boto3 is not None:
            session = boto3.session.Session()
        else:
            raise NotImplementedError(
                "Need to install 'boto3' to use 'load_aws_store()'"
            )

        try:
            client = session.client(
                service_name="secretsmanager",
                region_name=self.region,
            )
            self.aws_client = client
        except (ValueError, InvalidRegionError, NoRegionError) as err:
            self.logger.error("Error creating AWS Secrets client: %s", err)

    def load_aws_store(self) -> None:
        """Load all secrets from AWS secret store"""
        self.__connect_aws_client()
        if self.aws_client is None or self.sstore is None:
            self.logger.warning("Cannot load AWS secrets, no valid client.")
            return

        secrets = {}

        try:
            response = self.aws_client.get_secret_value(SecretId=self.sstore)
        except NoCredentialsError as err:
            self.logger.error("Error routing message! %s", err)
        except ClientError as err:
            code = err.response["Error"]["Code"]
            self.logger.error("ClientError: %s, (%s)", err, code)
        else:
            secrets = json.loads(response.get("SecretString", "{}"))
        self.loaded_values.update(secrets)
