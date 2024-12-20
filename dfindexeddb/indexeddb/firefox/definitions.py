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
"""Definitions for Firefox IndexedDB."""
from enum import IntEnum


class IndexedDBKeyType(IntEnum):
  """IndexedDB Key Types."""
  TERMINATOR = 0
  FLOAT = 0x10
  DATE = 0x20
  STRING = 0x30
  BINARY = 0x40
  ARRAY = 0x50


MAX_ARRAY_COLLAPSE = 3
MAX_RECURSION_DEPTH = 64
MAX_LENGTH = (1 << 30) - 2
ONE_BYTE_LIMIT = 0x7E
TWO_BYTE_LIMIT = 0x3FFF + 0x7F
ONE_BYTE_ADJUST = 1
TWO_BYTE_ADJUST = -0x7F
THREE_BYTE_SHIFT = 6


class StructuredDataType(IntEnum):
  """Structured Data Types."""
  FLOAT_MAX = 0xFFF00000
  HEADER = 0xFFF10000
  NULL = 0xFFFF0000
  UNDEFINED = 0xFFFF0001
  BOOLEAN = 0xFFFF0002
  INT32 = 0xFFFF0003
  STRING = 0xFFFF0004
  DATE_OBJECT  = 0xFFFF0005
  REGEXP_OBJECT = 0xFFFF0006
  ARRAY_OBJECT = 0xFFFF0007
  OBJECT_OBJECT = 0xFFFF0008
  ARRAY_BUFFER_OBJECT_V2 = 0xFFFF0009
  BOOLEAN_OBJECT = 0xFFFF000A
  STRING_OBJECT = 0xFFFF000B
  NUMBER_OBJECT = 0xFFFF000C
  BACK_REFERENCE_OBJECT  = 0xFFFF000D
  DO_NOT_USE_1  = 0xFFFF000E
  DO_NOT_USE_2 = 0xFFFF000F
  TYPED_ARRAY_OBJECT_V2 = 0xFFFF0010
  MAP_OBJECT = 0xFFFF0011
  SET_OBJECT = 0xFFFF0012
  END_OF_KEYS = 0xFFFF0013
  DO_NOT_USE_3 = 0xFFFF0014
  DATA_VIEW_OBJECT_V2 = 0xFFFF0015
  SAVED_FRAME_OBJECT = 0xFFFF0016
  JSPRINCIPALS = 0xFFFF0017
  NULL_JSPRINCIPALS = 0xFFFF0018
  RECONSTRUCTED_SAVED_FRAME_PRINCIPALS_IS_SYSTEM = 0xFFFF0019
  RECONSTRUCTED_SAVED_FRAME_PRINCIPALS_IS_NOT_SYSTEM = 0xFFFF001A
  SHARED_ARRAY_BUFFER_OBJECT = 0xFFFF001B
  SHARED_WASM_MEMORY_OBJECT = 0xFFFF001C
  BIGINT = 0xFFFF001D
  BIGINT_OBJECT = 0xFFFF001E
  ARRAY_BUFFER_OBJECT = 0xFFFF001F
  TYPED_ARRAY_OBJECT = 0xFFFF0020
  DATA_VIEW_OBJECT = 0xFFFF0021
  ERROR_OBJECT = 0xFFFF0022
  RESIZABLE_ARRAY_BUFFER_OBJECT = 0xFFFF0023
  GROWABLE_SHARED_ARRAY_BUFFER_OBJECT = 0xFFFF0024
  TYPED_ARRAY_V1_INT8 = 0xFFFF0100
  TYPED_ARRAY_V1_UINT8 = 0xFFFF0101
  TYPED_ARRAY_V1_INT16 = 0xFFFF0102
  TYPED_ARRAY_V1_UINT16 = 0xFFFF0103
  TYPED_ARRAY_V1_INT32 = 0xFFFF0104
  TYPED_ARRAY_V1_UINT32 = 0xFFFF0105
  TYPED_ARRAY_V1_FLOAT32 = 0xFFFF0106
  TYPED_ARRAY_V1_FLOAT64 = 0xFFFF0107
  TYPED_ARRAY_V1_UINT8_CLAMPED = 0xFFFF0108
  TRANSFER_MAP_HEADER = 0xFFFF0200
  TRANSFER_MAP_PENDING_ENTRY = 0xFFFF0201
  TRANSFER_MAP_ARRAY_BUFFER = 0xFFFF0202
  TRANSFER_MAP_STORED_ARRAY_BUFFER = 0xFFFF0203
  TRANSFER_MAP_END_OF_BUILTIN_TYPES = 0xFFFF0204


class StructuredCloneTags(IntEnum):
  """Structured Clone Tags."""
  BLOB = 0xFFFF8001
  FILE_WITHOUT_LASTMODIFIEDDATE = 0xFFFF8002
  FILELIST = 0xFFFF8003
  MUTABLEFILE = 0xFFFF8004
  FILE = 0xFFFF8005
  WASM_MODULE = 0xFFFF8006
  IMAGEDATA = 0xFFFF8007
  DOMPOINT = 0xFFFF8008
  DOMPOINTREADONLY = 0xFFFF8009
  CRYPTOKEY = 0xFFFF800A
  NULL_PRINCIPAL = 0xFFFF800B
  SYSTEM_PRINCIPAL = 0xFFFF800C
  CONTENT_PRINCIPAL = 0xFFFF800D
  DOMQUAD = 0xFFFF800E
  RTCCERTIFICATE = 0xFFFF800F
  DOMRECT = 0xFFFF8010
  DOMRECTREADONLY = 0xFFFF8011
  EXPANDED_PRINCIPAL = 0xFFFF8012
  DOMMATRIX = 0xFFFF8013
  URLSEARCHPARAMS = 0xFFFF8014
  DOMMATRIXREADONLY = 0xFFFF8015
  DOMEXCEPTION = 0xFFFF80016
  EMPTY_SLOT_9 = 0xFFFF8017
  STRUCTUREDCLONETESTER = 0xFFFF8018
  FILESYSTEMHANDLE = 0xFFFF8019
  FILESYSTEMFILEHANDLE = 0xFFFF801A
  FILESYSTEMDIRECTORYHANDLE = 0xFFFF801B
  IMAGEBITMAP = 0xFFFF801C
  MAP_MESSAGEPORT = 0xFFFF801D
  FORMDATA = 0xFFFF801E
  CANVAS = 0xFFFF801F  # This tag is for OffscreenCanvas.
  DIRECTORY = 0xFFFF8020
  INPUTSTREAM = 0xFFFF8021
  STRUCTURED_CLONE_HOLDER = 0xFFFF8022
  BROWSING_CONTEXT = 0xFFFF8023
  CLONED_ERROR_OBJECT = 0xFFFF8024
  READABLESTREAM = 0xFFFF8025
  WRITABLESTREAM = 0xFFFF8026
  TRANSFORMSTREAM = 0xFFFF8027
  VIDEOFRAME = 0xFFFF8028
  ENCODEDVIDEOCHUNK = 0xFFFF8029
  AUDIODATA = 0xFFFF8030
  ENCODEDAUDIOCHUNK = 0xFFFF8031


FRAME_HEADER = b'\xff\x06\x00\x00sNaPpY'
