# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, annotations

from dataclasses import dataclass
from typing import Any, Dict

import ruamel
import ruamel.yaml
from dbt_helper.utils import get_ruamel_yaml
from ruamel.yaml.comments import CommentedSeq, CommentedMap

from google.cloud import bigquery

from dbt_helper.parser.bigquery import extract_schema_info


@dataclass
class SourceTableUpdaterV2:
    data: Any  # expected ruamel.tools.comments.CommentedMap
    yaml: ruamel.yaml.YAML

    @classmethod
    def load(cls, path: str, yaml=get_ruamel_yaml()) -> SourceTableUpdaterV2:
        """Load data from a YAML file.

        Args:
            path: path to a YAML file
            yaml: an object of ruamel.yaml.YAML

        Returns:
            SourceTableUpdaterV2: SourceTableUpdaterV2 object
        """
        with open(path, "r") as read_stream:
            data = yaml.load(read_stream)
        return SourceTableUpdaterV2.loads(data)

    @classmethod
    def loads(cls, data: Any, yaml=get_ruamel_yaml()) -> SourceTableUpdaterV2:
        """Load from data

        Args:
            data: data generated by ruamel.yaml
            yaml: ruamel.yaml.YAML

        Returns:
            SourceTableUpdaterV2: SourceTableUpdaterV2 object
        """
        SourceTableUpdaterV2.validate_sources(data)
        source_yaml = SourceTableUpdaterV2(data=data, yaml=yaml)
        return source_yaml

    @classmethod
    def validate_sources(cls, data: Any):
        """Validate a loaded YAML data."""
        if "sources" not in data:
            raise ValueError("not a dbt source YAML")
        if len(data["sources"]) > 1:
            raise ValueError("contains multiple datasets")
        if "tables" not in data["sources"][0]:
            raise ValueError("no tables")
        if len(data["sources"][0]["tables"]) > 1:
            raise ValueError("contains multiple tables")
        return True

    def dump(self, path: str) -> None:
        """Dump YAML data to a YAML file.

        Args:
            path (str): path to a stored YAML file.
        """
        with open(path, "w") as writer:
            self.yaml.dump(self.data, writer)

    def update_with_bq_table(self, table: bigquery.Table) -> SourceTableUpdaterV2:
        """Update table metadata with a BigQuery table.

        Args:
            table (bigquery.Table): BigQuery table or view

        Returns:
            self
        """
        # Update the table description.
        self.table_description = table.description
        # Update the table labels
        self.table_labels = table.labels
        # Update the column schema.
        self.update_columns(table.schema)
        return self

    def update_columns(self, schema: bigquery.SchemaField) -> SourceTableUpdaterV2:
        """Update 'sources[].tables[].columns'

        Args:
            schema (bigquery.SchemaField): BigQuery schema fields

        Returns:
            self
        """
        # Convert BigQuery schema to dbt format.
        new_schema_info_list = extract_schema_info(schema)
        # Update columns with new schema.
        cursor_index = 0
        for schema_info in new_schema_info_list:
            has_column = False  # flag to check if a target column exists in old schema.
            # Add an existing column.
            for index, existing_column in enumerate(self.columns):
                # Update description with new one
                if existing_column["name"] == schema_info.name:
                    if isinstance(schema_info.description, str):
                        existing_column["description"] = schema_info.description
                    has_column = True
                    cursor_index = index
            # Add a new column.
            if has_column is False:
                new_column = CommentedMap()
                new_column["name"] = schema_info.name
                if isinstance(schema_info.description, str):
                    new_column["description"] = schema_info.description
                self.columns.insert(cursor_index + 1, new_column)
        # Remove columns which don't exist in new schema.
        for existing_column in self.columns:
            if existing_column["name"] not in [c.name for c in new_schema_info_list]:
                self.columns.remove(existing_column)
        return self

    @property
    def table_description(self):
        """Get a table description."""
        return self.data["sources"][0]["tables"][0]["description"]

    @table_description.setter
    def table_description(self, description: str):
        """Set table_description

        Args:
            description (str): table description
        """
        if isinstance(description, str):
            self.data["sources"][0]["tables"][0]["description"] = description

    @property
    def table_labels(self):
        """Get table labels."""
        return self.data["sources"][0]["tables"][0]["meta"]

    @table_labels.setter
    def table_labels(self, labels: Dict[str, str]):
        """Set table labels.

        Args:
            labels (dict): labels
        """
        if isinstance(labels, dict) and len(labels) > 0:
            self.data["sources"][0]["tables"][0]["meta"] = labels

    @property
    def columns(self) -> CommentedSeq:
        """Get a table description."""
        return self.data["sources"][0]["tables"][0]["columns"]