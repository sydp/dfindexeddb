# -*- coding: utf-8 -*-
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""A Chromium LevelDB-backed IndexedDB parser.

This module defines the IndexedDatabase class, which provides methods to parse
and manage IndexedDB data stored in LevelDB format.
"""

import os
import pathlib
import sys
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional, Iterator

from dfindexeddb.indexeddb.chromium import definitions, record


class RecordHistory:
  """A history of IndexedDB records.

  This class is used to keep track of IndexedDB records and their sequence
  numbers. It allows for updating records based on their sequence numbers.
  """

  def __init__(self, idb_record: record.IndexedDBRecord):
    """Initializes the record history.

    Args:
      idb_record: the initial record.
    """
    self._key = idb_record.key
    self._records = OrderedDict[int, record.IndexedDBRecord]()

  def AddRecord(self, idb_record: record.IndexedDBRecord) -> None:
    """Adds a record to the history.

    Args:
      idb_record: the record to add.

    Raises:
      ValueError: if the record is not the same, if the record already exists,
        or the sequence number is None or negative.
    """
    if idb_record.key != self._key:
      raise ValueError("Key does not match")
    if (
        idb_record.sequence_number is not None
        and idb_record.sequence_number in self._records
    ):
      raise ValueError(
          f"Record with sequence number {idb_record.sequence_number} "
          "already exists in history: "
          f"{self._records[idb_record.sequence_number]}"
      )
    if idb_record.sequence_number is None or idb_record.sequence_number < 0:
      raise ValueError(
          f"Record with sequence number {idb_record.sequence_number} "
          "cannot be negative"
      )
    # TODO; check key value is the same...
    self._records[idb_record.sequence_number] = idb_record

  def GetLatestSequenceNumber(self) -> Optional[int]:
    """Gets the latest sequence number from the history."""
    if not self._records:
      return None
    return max(self._records.keys())

  def GetLatestRecord(self) -> Optional[record.IndexedDBRecord]:
    """Gets a record from the history."""
    sequence_number = self.GetLatestSequenceNumber()
    if sequence_number is None:
      return None
    return self._records.get(sequence_number)


@dataclass
class GlobalMetadata:
  """Global metadata for IndexedDB.

  Attributes:
    active_blob: the active blob journal record.
    data_version: the data version record.
    free_list: the free list record.
    earliest_compaction_time: the earliest compaction time record.
    earliest_sweep: the earliest sweep record.
    max_database_id: the maximum database ID record.
    recovery_blob_journal: the recovery blob journal record.
    scopes_prefix: the scopes prefix record.
    schema_version: the schema version record.
  """

  active_blob: Optional[record.IndexedDBRecord]
  data_version: Optional[record.IndexedDBRecord]
  free_list: Optional[record.IndexedDBRecord]
  earliest_compaction_time: Optional[record.IndexedDBRecord]
  earliest_sweep: Optional[record.IndexedDBRecord]
  max_database_id: Optional[record.IndexedDBRecord]
  recovery_blob_journal: Optional[record.IndexedDBRecord]
  scopes_prefix: Optional[record.IndexedDBRecord]
  schema_version: Optional[record.IndexedDBRecord]


@dataclass
class DatabaseMetadata:
  """Metadata for an IndexedDB database.

  Attributes:
    origin_name: the origin name record.
    database_name: the database name record.
    idb_string_version_data: the IDB string version data record.
    max_allocated_object_store_id: the maximum allocated object store ID record.
    idb_integer_version: the IDB integer version record.
    blob_number_generator_current_number: the blob number generator current
        number record.
  """

  origin_name: Optional[record.IndexedDBRecord]
  database_name: Optional[record.IndexedDBRecord]
  idb_string_version_data: Optional[record.IndexedDBRecord]
  max_allocated_object_store_id: Optional[record.IndexedDBRecord]
  idb_integer_version: Optional[record.IndexedDBRecord]
  blob_number_generator_current_number: Optional[record.IndexedDBRecord]


@dataclass
class ObjectStoreMetadata:
  """Metadata for an IndexedDB object store.

  Args:
    object_store_name: the object store name record.
    key_path: the key path record.
    auto_increment_flag: the auto-increment flag record.
    is_evictable: the is-evictable flag record.
    last_version_number: the last version number record.
    maximum_allocated_index_id: the maximum allocated index ID record.
    has_key_path: the has-key-path flag record.
    key_generator_current_number: the key generator current number record.
  """

  object_store_name: Optional[record.IndexedDBRecord]
  key_path: Optional[record.IndexedDBRecord]
  auto_increment_flag: Optional[record.IndexedDBRecord]
  is_evictable: Optional[record.IndexedDBRecord]
  last_version_number: Optional[record.IndexedDBRecord]
  maximum_allocated_index_id: Optional[record.IndexedDBRecord]
  has_key_path: Optional[record.IndexedDBRecord]
  key_generator_current_number: Optional[record.IndexedDBRecord]


@dataclass
class ObjectStore:
  """An IndexedDB object store.

  Attributes:
    object_store_id: the ID of the object store.
    metadata: the metadata for the object store.
    records: a list of IndexedDB records in the object store.
    blobs: a dictionary of blob records keyed by their blob index.
  """

  object_store_id: int
  metadata: ObjectStoreMetadata
  records: list[record.IndexedDBRecord]
  blobs: dict[int, Any]

  def __init__(self, object_store_id: int):
    """Initializes the ObjectStore.

    Args:
      object_store_id: the ID of the object store.
    """
    self.object_store_id = object_store_id
    self.metadata = ObjectStoreMetadata(
        object_store_name=None,
        key_path=None,
        auto_increment_flag=None,
        is_evictable=None,
        last_version_number=None,
        maximum_allocated_index_id=None,
        has_key_path=None,
        key_generator_current_number=None,
    )
    self.records = []
    self.blobs = {}

  def Name(self) -> Optional[str]:
    """Returns the object store name."""
    if self.metadata.object_store_name:
      return str(self.metadata.object_store_name.value)
    return None

  def AddRecord(self, idb_record: record.IndexedDBRecord) -> None:
    """Adds a record to the object store.

    Args:
      record: the IndexedDB record to add.

    Raises:
      ValueError: if the record is not an ObjectStoreDataKey or if the object
          store ID of the record does not match the metadata object store ID.
    """
    if not isinstance(idb_record.key, record.ObjectStoreDataKey):
      raise ValueError(
          "Record is not an ObjectStoreDataKey, cannot add to store"
      )
    if idb_record.object_store_id != self.object_store_id:
      raise ValueError(
          f"Record {idb_record} object store ID {idb_record.key} "
          f"does not match metadata object store ID {self.object_store_id}"
      )
    self.records.append(idb_record)

  def GetRecords(self) -> Iterator[tuple[record.ObjectStoreDataKey, Any]]:
    """Returns the records in the object store."""
    for object_store_record in self.records:
      if not isinstance(object_store_record.key, record.ObjectStoreDataKey):
        print(f"Skipping non-data record: {record}", file=sys.stderr)
        continue
      if object_store_record.value.value is None:
        blob = self.blobs.get(  # type: ignore[call-overload]
            object_store_record.key.encoded_user_key.value
        )
        value = blob.value if blob else None
        print(f"Using blob value: {value}", file=sys.stderr)
      else:
        value = object_store_record.value.value
      yield object_store_record.key, value


@dataclass
class Database:
  """A database in IndexedDB.

  Attributes:
    database_id: the database ID
    metadata: the metadata for the database.
    object_stores: a dictionary of object stores keyed by the object ID.
  """

  database_id: int
  metadata: DatabaseMetadata
  object_stores: dict[int, ObjectStore]

  def Name(self) -> Optional[str]:
    """Returns the database name."""
    if self.metadata.database_name:
      return str(self.metadata.database_name.key.database_name)
    return None

  def GetOrCreateObjectStore(self, object_store_id: int) -> ObjectStore:
    """Gets or creates an ObjectStoreMetadata instance for the object store id."""  # pylint: disable=line-too-long
    if object_store_id not in self.object_stores:
      self.object_stores[object_store_id] = ObjectStore(object_store_id)
    return self.object_stores[object_store_id]


def _UpdateKey(
    target_record: Optional[record.IndexedDBRecord],
    new_record: record.IndexedDBRecord,
) -> record.IndexedDBRecord:
  """Updates the target record with the new record if applicable.

  This function checks if the target record is None or if the new record has a
  higher sequence number than the target record. If either condition is true,
  the target record is updated to the new record.

  Args:
    target_record: the target record.
    new_record: the new record.
  """
  if not target_record:
    return new_record
  elif (
      target_record.sequence_number
      and new_record.sequence_number
      and target_record.sequence_number < new_record.sequence_number
  ):
    return new_record
  return target_record


class IndexedDatabase:
  """An IndexedDB backed by LevelDB folder.

  An IndexedDatabase can contain multiple databases, each with its own
  metadata and object stores.

  Attributes:
    metadata: the global metadata for the IndexedDB.
    databases: a dictionary of databases keyed by their KeyPrefix.
    folder_path: the IndexedDB folder path.
    blob_path: the path to the blob folder, if it exists.
  """

  metadata: GlobalMetadata
  databases: dict[int, Database]
  folder_path: pathlib.Path
  blob_path: Optional[pathlib.Path] = None
  blob_files: dict[int, pathlib.Path]

  def __init__(self, folder_path: pathlib.Path):
    """Initializes the FolderReader.

    Args:
      folder_path: the IndexedDB folder path.

    Raises:
      ValueError: if the folder path does not end with .leveldb or is not a
          directory.
      FileNotFoundError: if the blob path does not exist or is not a directory.
    """
    self.folder_path = folder_path

    if not folder_path.name.endswith(".leveldb"):
      raise ValueError("Folder path must end with .leveldb")

    if not os.path.isdir(folder_path):
      raise ValueError(f"Folder path {folder_path} is not a directory")

    blob_name = folder_path.name[: -len(".leveldb")] + ".blob"
    blob_path = folder_path.parent / blob_name
    if not os.path.exists(blob_path):
      raise FileNotFoundError(f"Blob path {blob_path} does not exist")
    else:
      self.blob_path = pathlib.Path(blob_path)
      if not self.blob_path.is_dir():
        raise ValueError(f"Blob path {blob_path} is not a directory")
      self.blob_files = {
          int(path.name, base=16): path
          for path in self.blob_path.rglob("*")
          if path.is_file()
      }

    self._leveldb_reader = record.FolderReader(folder_path)
    self.metadata = GlobalMetadata(
        active_blob=None,
        data_version=None,
        free_list=None,
        earliest_compaction_time=None,
        earliest_sweep=None,
        max_database_id=None,
        recovery_blob_journal=None,
        scopes_prefix=None,
        schema_version=None,
    )
    self.databases = {}
    self._ParseMetadata()

  def ListDatabases(self) -> None:
    """Lists the databases in the IndexedDB."""
    for database_id, database in self.databases.items():
      print(f"Database ID: {database_id}, Name: {database.Name()}")

  def ListObjectStores(self, database_id: int) -> None:
    """Lists the object stores in the given database.

    Args:
      database_id: the ID of the database to list object stores for.
    """
    if database_id not in self.databases:
      print(f"Database ID {database_id} does not exist.")
      return
    database = self.databases[database_id]
    for object_store_id, object_store in database.object_stores.items():
      print(f"Object Store ID: {object_store_id}, Name: {object_store.Name()}")

  def ListDatabaseAndObjectStores(self) -> None:
    """Lists all databases and their object stores."""
    print(
        f'{"Database ID": <10}  {"Database Name": <5} '
        f'{"Object Store ID": <20}  {"Object Store Name": <5}'
    )
    for database_id, database in self.databases.items():
      for object_store_id, object_store in database.object_stores.items():
        print(
            f"{database_id: <10}  {database.Name(): <5} "
            f"{object_store_id: <20}  {object_store.Name(): <5}"
        )

  def _GetOrCreateDatabase(self, database_id: int) -> Database:
    """Gets or creates a Database instance for the given database id.

    Args:
      database_id: the ID of the database to get or create.

    Returns:
      A Database instance corresponding to the given database_id.
    """
    if database_id not in self.databases:
      self.databases[database_id] = Database(
          database_id=database_id,
          metadata=DatabaseMetadata(
              origin_name=None,
              database_name=None,
              idb_string_version_data=None,
              max_allocated_object_store_id=None,
              idb_integer_version=None,
              blob_number_generator_current_number=None,
          ),
          object_stores={},
      )
    return self.databases[database_id]

  def _HandleGlobalMetadataKey(
      self, idb_record: record.IndexedDBRecord
  ) -> None:
    """Handles global metadata keys.

    Args:
      idb_record: the IndexedDB record to handle.
    """
    if isinstance(idb_record.key, record.ActiveBlobJournalKey):
      self.metadata.active_blob = _UpdateKey(
          self.metadata.active_blob, idb_record
      )
    elif isinstance(idb_record.key, record.DataVersionKey):
      self.metadata.data_version = _UpdateKey(
          self.metadata.data_version, idb_record
      )
    elif isinstance(idb_record.key, record.DatabaseFreeListKey):
      self.metadata.data_version = _UpdateKey(
          self.metadata.data_version, idb_record
      )
    elif isinstance(idb_record.key, record.DatabaseNameKey):
      database = self._GetOrCreateDatabase(idb_record.value)
      database.metadata.database_name = _UpdateKey(
          database.metadata.database_name, idb_record
      )
    elif isinstance(idb_record.key, record.EarliestSweepKey):
      self.metadata.earliest_sweep = _UpdateKey(
          self.metadata.earliest_sweep, idb_record
      )
    elif isinstance(idb_record.key, record.EarliestCompactionTimeKey):
      self.metadata.earliest_compaction_time = _UpdateKey(
          self.metadata.earliest_compaction_time, idb_record
      )
    elif isinstance(idb_record.key, record.MaxDatabaseIdKey):
      self.metadata.max_database_id = _UpdateKey(
          self.metadata.max_database_id, idb_record
      )
    elif isinstance(idb_record.key, record.RecoveryBlobJournalKey):
      self.metadata.recovery_blob_journal = _UpdateKey(
          self.metadata.recovery_blob_journal, idb_record
      )
    elif isinstance(idb_record.key, record.SchemaVersionKey):
      self.metadata.schema_version = _UpdateKey(
          self.metadata.schema_version, idb_record
      )
    elif isinstance(idb_record.key, record.ScopesPrefixKey):
      self.metadata.scopes_prefix = _UpdateKey(
          self.metadata.scopes_prefix, idb_record
      )

  def _HandleDatabaseMetadataKey(
      self, idb_record: record.IndexedDBRecord
  ) -> None:
    """Handles database metadata keys.

    This method updates the database metadata based on the type of the
    IndexedDB record provided. It checks the key prefix of the record to
    determine which metadata field to update. If the database does not exist
    in the `databases` dictionary, it creates a new `Database` instance.

    Args:
      idb_record: the IndexedDB record to handle.
    """
    database = self._GetOrCreateDatabase(idb_record.key.key_prefix.database_id)

    if isinstance(idb_record.key, record.DatabaseMetaDataKey):
      if (
          idb_record.key.metadata_type
          == definitions.DatabaseMetaDataKeyType.ORIGIN_NAME
      ):
        database.metadata.origin_name = _UpdateKey(
            database.metadata.origin_name, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.DatabaseMetaDataKeyType.DATABASE_NAME
      ):
        database.metadata.database_name = _UpdateKey(
            database.metadata.database_name, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.DatabaseMetaDataKeyType.IDB_STRING_VERSION_DATA
      ):
        database.metadata.idb_string_version_data = _UpdateKey(
            database.metadata.idb_string_version_data, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.DatabaseMetaDataKeyType.MAX_ALLOCATED_OBJECT_STORE_ID
      ):
        database.metadata.max_allocated_object_store_id = _UpdateKey(
            database.metadata.max_allocated_object_store_id, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.DatabaseMetaDataKeyType.IDB_INTEGER_VERSION
      ):
        database.metadata.idb_integer_version = _UpdateKey(
            database.metadata.idb_integer_version, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.DatabaseMetaDataKeyType.BLOB_NUMBER_GENERATOR_CURRENT_NUMBER  # pylint: disable=line-too-long
      ):
        database.metadata.blob_number_generator_current_number = _UpdateKey(
            database.metadata.blob_number_generator_current_number, idb_record
        )
    elif isinstance(idb_record.key, record.ObjectStoreMetaDataKey):
      object_store = database.GetOrCreateObjectStore(
          idb_record.key.object_store_id
      )
      if (
          idb_record.key.metadata_type
          == definitions.ObjectStoreMetaDataKeyType.OBJECT_STORE_NAME
      ):
        object_store.metadata.object_store_name = _UpdateKey(
            object_store.metadata.object_store_name, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.ObjectStoreMetaDataKeyType.KEY_PATH
      ):
        object_store.metadata.key_path = _UpdateKey(
            object_store.metadata.key_path, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.ObjectStoreMetaDataKeyType.AUTO_INCREMENT_FLAG
      ):
        object_store.metadata.auto_increment_flag = _UpdateKey(
            object_store.metadata.auto_increment_flag, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.ObjectStoreMetaDataKeyType.IS_EVICTABLE
      ):
        object_store.metadata.is_evictable = _UpdateKey(
            object_store.metadata.is_evictable, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.ObjectStoreMetaDataKeyType.LAST_VERSION_NUMBER
      ):
        object_store.metadata.last_version_number = _UpdateKey(
            object_store.metadata.last_version_number, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.ObjectStoreMetaDataKeyType.MAXIMUM_ALLOCATED_INDEX_ID
      ):
        object_store.metadata.maximum_allocated_index_id = _UpdateKey(
            object_store.metadata.maximum_allocated_index_id, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.ObjectStoreMetaDataKeyType.HAS_KEY_PATH
      ):
        object_store.metadata.has_key_path = _UpdateKey(
            object_store.metadata.has_key_path, idb_record
        )
      elif (
          idb_record.key.metadata_type
          == definitions.ObjectStoreMetaDataKeyType.KEY_GENERATOR_CURRENT_NUMBER
      ):
        object_store.metadata.key_generator_current_number = _UpdateKey(
            object_store.metadata.key_generator_current_number, idb_record
        )

  def _HandleObjectStoreDataKey(
      self, idb_record: record.IndexedDBRecord
  ) -> None:
    """Handles object store data keys.

    This method adds the IndexedDB record to the appropriate object store based
    on the key prefix of the record. It retrieves or creates an `ObjectStore`
    instance for the given object store ID and adds the record to it.

    Args:
      idb_record: the IndexedDB record to handle.
    """
    if not isinstance(idb_record.key, record.ObjectStoreDataKey):
      raise ValueError(
          "Record is not an ObjectStoreDataKey, cannot add to store"
      )

    database = self._GetOrCreateDatabase(idb_record.database_id)
    object_store = database.GetOrCreateObjectStore(idb_record.object_store_id)
    object_store.AddRecord(idb_record)

  def _HandleBlobEntryKey(self, idb_record: record.IndexedDBRecord) -> None:
    """Handles blob entry keys.

    This method adds the IndexedDB record to the blob store if it is a blob
    entry key. It retrieves or creates an `ObjectStore` instance for the blob
    store and adds the record to it.

    Args:
      idb_record: the IndexedDB record to handle.
    """
    if not isinstance(idb_record.key, record.BlobEntryKey):
      raise ValueError(
          f"Record {idb_record} is not a BlobEntryKey, "
          "cannot add to blob store"
      )

    database = self._GetOrCreateDatabase(idb_record.database_id)
    object_store = database.GetOrCreateObjectStore(idb_record.object_store_id)

    blob_key = idb_record.key.user_key.value
    assert isinstance(blob_key, int)
    if blob_key in object_store.blobs:
      print(
          f"Blob key {blob_key} already exists in object store "
          f"{object_store.Name()}"
      )
      return
    object_store.blobs[blob_key] = idb_record

  def _ParseMetadata(self) -> None:
    """Parses the metadata from the IndexedDB records."""
    for idb_record in self._leveldb_reader.GetRecords():
      if idb_record.recovered is True:
        print(f"Skipping recovered record: {idb_record}", file=sys.stderr)
        continue
      elif idb_record.type == 0:  # type 0 is deleted
        print(f"Skipping deleted record: {idb_record}", file=sys.stderr)
        continue
      key_prefix_type = idb_record.key.key_prefix.GetKeyPrefixType()

      if key_prefix_type == definitions.KeyPrefixType.GLOBAL_METADATA:
        self._HandleGlobalMetadataKey(idb_record)
      elif key_prefix_type == definitions.KeyPrefixType.DATABASE_METADATA:
        self._HandleDatabaseMetadataKey(idb_record)
      elif key_prefix_type == definitions.KeyPrefixType.OBJECT_STORE_DATA:
        self._HandleObjectStoreDataKey(idb_record)
      elif key_prefix_type == definitions.KeyPrefixType.BLOB_ENTRY:
        self._HandleBlobEntryKey(idb_record)
      else:
        print(f"Skipping record {key_prefix_type}", file=sys.stderr)

  def GetRecords(self) -> Iterator[record.IndexedDBRecord]:
    """Yields IndexedDB records from the databases."""
    for database_id, database in self.databases.items():
      for object_store in database.object_stores.values():
        for key, value in object_store.GetRecords():
          blob = None
          if isinstance(value, record.IndexedDBExternalObject):
            blob = b""
            blob_file = None
            for entry in value.entries:
              if entry.blob_number:
                blob_file = self.blob_files.get(entry.blob_number)
              if not blob_file:
                print(
                    f"Blob file for index {entry.blob_number} not found",
                    file=sys.stderr,
                )
                continue
              with open(blob_file, "rb") as f:
                blob += f.read()
          yield record.IndexedDBRecord(
              path=str(self.folder_path.resolve()),
              offset=0,  # Offset is not applicable here.
              key=key,
              value=value,
              type=0,
              sequence_number=None,  # Sequence number is not applicable here.
              level=None,  # Level is not applicable here.
              recovered=False,
              database_id=database_id,
              object_store_id=object_store.object_store_id,
              database_name=database.Name(),
              object_store_name=object_store.Name(),
              blob=blob,
          )
