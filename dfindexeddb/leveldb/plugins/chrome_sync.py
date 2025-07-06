"""Parser plugin for Chrome Sync."""
from __future__ import annotations

import dataclasses
import logging
import sys
from typing import Any, Optional

from google.protobuf.json_format import MessageToDict

from dfindexeddb.leveldb.ldb import KeyValueRecord
from dfindexeddb.leveldb.log import ParsedInternalKey


try:
  # pytype: disable=import-error
  from dfindexeddb.leveldb.plugins.proto.chrome_sync import sync_pb2
  # pytype: enable=import-error
  _has_import_dependencies = True
except ImportError as err:
  _has_import_dependencies = False
  logging.warning(
      'Could not import dependencies for leveldb.plugins.chrome_sync: %s',
      err)

from dfindexeddb.leveldb.plugins import interface
from dfindexeddb.leveldb.plugins import manager


@dataclasses.dataclass
class ChromeSyncRecord(interface.LeveldbPlugin):
  """Chrome Sync record."""
  #src_file: Optional[str] = None
  offset: Optional[int] = None
  key: Optional[bytes] = None
  sequence_number: Optional[int] = None
  type: Optional[int] = None
  value: Any = None

  @classmethod
  def FromKeyValueRecord(
      cls, ldb_record: KeyValueRecord | ParsedInternalKey) -> ChromeSyncRecord:
    """Creates a ChromeSyncRecord from a KeyValueRecord or ParsedInternalKey."""
    record = cls()
    record.offset = ldb_record.offset
    record.key = ldb_record.key
    record.sequence_number = ldb_record.sequence_number
    record.type = ldb_record.record_type

    sync_proto = sync_pb2.SyncEntity()
    try:
      sync_proto.ParseFromString(ldb_record.value)
    except Exception as e:
      logging.error(
          'Failed to parse Chrome Sync record at offset %d: %s',
          ldb_record.offset, e)
      return record

    record.value = MessageToDict(sync_proto)
    return record

if _has_import_dependencies:
  manager.PluginManager.RegisterPlugin(ChromeSyncRecord)
