"""Configuration base class with JSON/YAML serialization support."""

import json
import logging
from dataclasses import asdict, dataclass, fields, is_dataclass, MISSING
from datetime import datetime
from typing import get_origin, get_args

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Base class for dataclass configuration files.

    This class provides methods to load and save configuration data from/to JSON or YAML files.
    It also provides a method to convert the data class attributes to a dictionary excluding the ones marked with `serialize=False`.

    Attributes:
        key (StrEnum): A string enumeration for the keys in the configuration.
        job_creation (str): The date and time when the job was created.

    Methods:
        from_file(filename: str) -> Config:
            Create an instance of the class from a JSON or YAML file.
        export(filename: str):
            Convert the data class to either a JSON or YAML string and export it to a file.
        __post_init__():
            Set the job creation date and time. Dynamically initialize the key attribute.

    """

    def __str__(self):
        msg = "{}\n\r".format(type(self))
        for attrname in vars(self):
            value = getattr(self, attrname)
            msg += "  {}: {}\n".format(attrname, value)
        return msg

    @classmethod
    def from_file(cls, filename: str):
        """
        Create an instance of the class from a JSON or YAML file.
        The type of file is determined by the file extension.

        If the file extension is not .yaml, .yml, or .json, a ValueError is raised.

        Parameters
        ----------
        filename : str
            Name of the file path to read the data from.

        Returns
        -------
        Config
            An instance of the class with the data loaded from the file.

        """
        # Create an instance of the class from a YAML file
        if (
            not filename.endswith(".yaml")
            and not filename.endswith(".yml")
            and not filename.endswith(".json")
        ):
            raise ValueError("Filename must end with .yaml, .yml, or .json")
        if filename.endswith(".json"):
            with open(filename, "r") as file:
                data = json.load(file)
        elif filename.endswith(".yaml") or filename.endswith(".yml"):
            with open(filename, "r") as file:
                data = yaml.safe_load(file)

        # Recursively convert nested dictionaries to their respective dataclass types
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict):
        """
        Recursively convert a dictionary to a dataclass instance,
        handling nested dataclasses and lists of dataclasses.

        Parameters
        ----------
        data : dict
            Dictionary containing the configuration data.

        Returns
        -------
        Config
            An instance of the class with nested dataclasses properly instantiated.
        """
        if not isinstance(data, dict):
            return data

        field_values = {}
        for field_info in fields(cls):
            field_name = field_info.name
            field_type = field_info.type

            # Handle missing fields
            if field_name not in data:
                # Use default if available
                if field_info.default is not MISSING:
                    field_values[field_name] = field_info.default
                    logger.info(
                        f"Field '{field_name}' not present in config file, using default value: {field_info.default}"
                    )
                elif field_info.default_factory is not MISSING:
                    field_values[field_name] = field_info.default_factory()
                    logger.info(
                        f"Field '{field_name}' not present in config file, using default factory value"
                    )
                else:
                    raise ValueError(f"Missing required field: {field_name}")
                continue

            field_value = data[field_name]

            # Handle nested dataclasses
            if is_dataclass(field_type):
                if isinstance(field_value, dict):
                    field_values[field_name] = field_type._from_dict(field_value)
                else:
                    field_values[field_name] = field_value
            # Handle lists of dataclasses
            elif get_origin(field_type) is list:
                args = get_args(field_type)
                if args and is_dataclass(args[0]):
                    item_type = args[0]
                    if isinstance(field_value, list):
                        field_values[field_name] = [
                            (
                                item_type._from_dict(item)
                                if isinstance(item, dict)
                                else item
                            )
                            for item in field_value
                        ]
                    else:
                        field_values[field_name] = field_value
                else:
                    field_values[field_name] = field_value
            else:
                field_values[field_name] = field_value

        return cls(**field_values)

    def export(self, filename):
        """
        Convert the data class to either a JSON or YAML string and export it to a file.
        The type of file is determined by the file extension.
        If the file extension is not .yaml, .yml, or .json, a ValueError is raised.

        Parameters
        ----------
        filename : str
            Name of the file path to save the either JSON or YAML data.

        """
        if (
            not filename.endswith(".yaml")
            and not filename.endswith(".yml")
            and not filename.endswith(".json")
        ):
            raise ValueError("Filename must end with .yaml, .yml, or .json")
        try:
            with open(filename, "w") as file:
                if filename.endswith(".json"):
                    json.dump(asdict(self), file, indent=4)
                elif filename.endswith(".yaml") or filename.endswith(".yml"):
                    yaml.dump(asdict(self), file, default_flow_style=False)
        except (IOError, OSError) as e:
            raise RuntimeError(f"Failed to write to {filename}: {e}")

    def __post_init__(self):
        self.job_creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        """
        Convert the data class to a dictionary excluding the ones marked with `serialize=False`.

        Returns
        -------
        dict
            A dictionary representation of the data class.

        """
        return {k: v for k, v in asdict(self).items()}
