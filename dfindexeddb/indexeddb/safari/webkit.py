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
"""Parsers for WebKit encoded JavaScript values."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import io
import plistlib
from typing import Any, Dict, List, Tuple, Union

from dfindexeddb import errors
from dfindexeddb import utils
from dfindexeddb.indexeddb import types
from dfindexeddb.indexeddb.safari import definitions


@dataclass
class ArrayBufferView:
  """A parsed JavaScript ArrayBufferView.

  Attributes:
    array_buffer_view_subtag: the sub tag.
    buffer: the buffer.
    offset: the offset of the view.
    length: the length of the view.
  """
  array_buffer_view_subtag: definitions.ArrayBufferViewSubtag
  buffer: bytes
  offset: int
  length: int


@dataclass
class ResizableArrayBuffer:
  """A parsed Resizable Array Buffer.

  Attributes:
    buffer: the buffer.
    max_length: the maximum length of the buffer (for resizing).
  """
  buffer: bytes
  max_length: int


@dataclass
class FileData:
  """A parsed FileData.

  Attributes:
    path: the path.
    url: the URL.
    type: the type.
    name: the file name.
    last_modified: the last modified timestamp.
  """
  path: str
  url: str
  type: str
  name: str
  last_modified: float


@dataclass
class FileList:
  """A parsed FileList.

  Attributes:
    files: the list of files.
  """
  files: List[FileData]


@dataclass
class IDBKeyData(utils.FromDecoderMixin):
  """An IDBKeyData.

  Attributes:
    offset: the offset at which the IDBKeyData was parsed.
    key_type: the IDB Key Type.
    data: the key data.
  """
  offset: int
  key_type: definitions.SIDBKeyType
  data: Union[float, datetime, str, bytes, list]

  @classmethod
  def FromDecoder(
      cls,
      decoder: utils.StreamDecoder,
      base_offset: int = 0
  ) -> IDBKeyData:
    """Decodes an IDBKeyData from the current position of decoder.

    Refer to IDBSerialization.cpp for the encoding scheme.

    Args:
      decoder: the decoder

    Returns:
      the IDBKeyData.

    Raises:
      ParserError: when the key version is not found or an unknown key type is
          encountered or an old-style PropertyList key type is found.
    """
    def _DecodeKeyBuffer(key_type):
      if key_type == definitions.SIDBKeyType.MIN:
        data = None
      if key_type == definitions.SIDBKeyType.NUMBER:
        _, data = decoder.DecodeDouble()
      elif key_type == definitions.SIDBKeyType.DATE:
        _, timestamp = decoder.DecodeDouble()
        data = datetime.utcfromtimestamp(timestamp/1000)
      elif key_type == definitions.SIDBKeyType.STRING:
        _, length = decoder.DecodeUint32()
        _, raw_data = decoder.ReadBytes(length*2)
        data = raw_data.decode('utf-16-le')
      elif key_type == definitions.SIDBKeyType.BINARY:
        _, length = decoder.DecodeUint32()
        _, data = decoder.ReadBytes(length)
      elif key_type == definitions.SIDBKeyType.ARRAY:
        _, length = decoder.DecodeUint64()
        data = []
        for _ in range(length):
          _, key_type = decoder.DecodeUint8()
          element = _DecodeKeyBuffer(key_type)
          data.append(element)
      else:
        raise errors.ParserError('Unknown definitions.SIDBKeyType found.')
      return data

    offset, version_header = decoder.DecodeUint8()
    if version_header != definitions.SIDB_KEY_VERSION:
      raise errors.ParserError('SIDBKeyVersion not found.')

    _, raw_key_type = decoder.DecodeUint8()
    key_type = definitions.SIDBKeyType(raw_key_type)

    # "Old-style key is characterized by this magic character that
    # begins serialized PropertyLists
    if key_type == b'b':
      raise errors.ParserError('Old-style PropertyList key type found.')
    data = _DecodeKeyBuffer(key_type)

    return cls(
        offset=offset+base_offset,
        key_type=key_type,
        data=data)


class SerializedScriptValueDecoder():
  """Decodes a Serialized Script Value from a stream of bytes.

  Attributes:
    decoder: the stream decoder for the given byte stream.
    version: the parsed serialized script version.
    constant_pool: the constant pool.
    object_pool: the object pool.
  """
  def __init__(self, stream: io.BytesIO):
    self.decoder = utils.StreamDecoder(stream)
    self.version = None
    self.constant_pool = []
    self.object_pool = []

  def PeekTag(self) -> int:
    """Peeks a tag from the current position."""
    _, peeked_bytes = self.decoder.PeekBytes(4)
    return int.from_bytes(peeked_bytes, byteorder='little')

  def PeekSerializationTag(self) -> definitions.SerializationTag:
    """Peeks a SerializationTag from the current position.

    Raises:
      ParserError if an invalid SerializationTag was parsed.
    """
    offset, terminal_byte = self.decoder.PeekBytes(1)
    try:
      return definitions.SerializationTag(terminal_byte[0])
    except ValueError as error:
      raise errors.ParserError(
          f'Invalid SerializationTag {terminal_byte} at offset {offset}'
      ) from error

  def DecodeSerializationTag(self) -> Tuple[int, definitions.SerializationTag]:
    """Decodes a SerializationTag.

    Returns:
      a tuple of the offset and the serialization tag.

    Raises:
      ParserError if an invalid terminal value was encountered.
    """
    offset, terminal_byte = self.decoder.DecodeUint8()
    try:
      return offset, definitions.SerializationTag(terminal_byte)
    except ValueError as error:
      raise errors.ParserError(
          f'Invalid terminal {terminal_byte} at offset {offset}') from error

  def DecodeArray(self) -> types.JSArray:
    """Decodes an Array value.

    Returns:
      the JavaScript array.

    Raises:
      ParserError if an invalid Terminator tag was found.
    """
    _, length = self.decoder.DecodeUint32()
    array = types.JSArray()
    self.object_pool.append(array)
    for _ in range(length):
      _, _ = self.decoder.DecodeUint32()
      _, value = self.DecodeValue()
      array.values.append(value)

    offset, terminator_tag = self.decoder.DecodeUint32()
    if terminator_tag != definitions.TERMINATOR_TAG:
      raise errors.ParserError(f'Terminator tag not found at offset {offset}.')

    offset, tag = self.decoder.DecodeUint32()
    if tag == definitions.NON_INDEX_PROPERTIES_TAG:
      while tag != definitions.TERMINATOR_TAG:
        name = self.DecodeStringData()
        _, value = self.DecodeValue()
        _, tag = self.decoder.DecodeUint32()
        array.properties[name] = value
    elif tag != definitions.TERMINATOR_TAG:
      raise errors.ParserError(f'Terminator tag not found at offset {offset}.')
    return array

  def DecodeObject(self) -> Dict[str, Any]:
    """Decodes an Object value."""
    tag = self.PeekTag()
    js_object = {}
    self.object_pool.append(js_object)
    while tag != definitions.TERMINATOR_TAG:
      name = self.DecodeStringData()
      _, value = self.DecodeValue()
      js_object[name] = value
      tag = self.PeekTag()
    _ = self.decoder.DecodeUint32()
    return js_object

  def DecodeStringData(self) -> str:
    """Decodes a StringData value.

    Returns:
      A JavaScript array.

    Raises:
      ParserError if an:
          * unexpected TerminatorTag is found
          * unexpected constant pool size value is found
          * disallowed string length is found.
          * unable to to decode a buffer as utf-16-le.
    """
    peeked_tag = self.PeekTag()
    if peeked_tag == definitions.TERMINATOR_TAG:
      raise errors.ParserError('Unexpected TerminatorTag found')

    if peeked_tag == definitions.STRING_POOL_TAG:
      _ = self.decoder.DecodeUint32()
      if len(self.constant_pool) <= 0xff:
        _, cp_index = self.decoder.DecodeUint8()
      elif len(self.constant_pool) <= 0xffff:
        _, cp_index = self.decoder.DecodeUint16()
      elif len(self.constant_pool) <= 0xffffffff:
        _, cp_index = self.decoder.DecodeUint32()
      else:
        raise errors.ParserError('Unexpected constant pool size value.')
      return self.constant_pool[cp_index]

    _, length_with_8bit_flag = self.decoder.DecodeUint32()
    if length_with_8bit_flag == definitions.TERMINATOR_TAG:
      raise errors.ParserError('Disallowed string length found.')

    length = length_with_8bit_flag & 0x7FFFFFFF
    is_8bit = length_with_8bit_flag & definitions.STRING_DATA_IS_8BIT_FLAG

    if is_8bit:
      _, characters = self.decoder.ReadBytes(length)
      value = characters.decode('latin-1')
    else:
      _, characters = self.decoder.ReadBytes(2*length)
      try:
        value = characters.decode('utf-16-le')
      except UnicodeDecodeError as exc:
        raise errors.ParserError(
            f'Unable to decode {len(characters)} characters as utf-16-le'
        ) from exc
    self.constant_pool.append(value)
    return value

  def DecodeDate(self) -> datetime:
    """Decodes a Date value."""
    _, timestamp = self.decoder.DecodeDouble()
    value = datetime.utcfromtimestamp(timestamp/1000)
    return value

  def DecodeFileData(self) -> FileData:
    """Decodes a FileData value."""
    path = self.DecodeStringData()
    url = self.DecodeStringData()
    file_type = self.DecodeStringData()
    name = self.DecodeStringData()
    _, last_modified = self.decoder.DecodeDouble()

    return FileData(
        path=path,
        url=url,
        type=file_type,
        name=name,
        last_modified=last_modified)

  def DecodeFileList(self) -> FileList:
    """Decodes a FileList value."""
    _, length = self.decoder.DecodeUint32()
    file_list = []
    for _ in range(length):
      file_list.append(self.DecodeFileData())
    return FileList(files=file_list)

  def DecodeImageData(self) -> Dict[str, Any]:
    """Decodes an ImageData value."""
    _, width = self.decoder.DecodeUint32()
    _, height = self.decoder.DecodeUint32()
    _, length = self.decoder.DecodeUint32()
    data = self.decoder.ReadBytes(length)

    if self.version > 7:
      _, color_space = self.decoder.DecodeUint8()
    else:
      color_space = None

    # TODO: make this a dataclass?
    return {
      'width': width,
      'height': height,
      'length': length,
      'data': data,
      'color_space': color_space
    }

  def DecodeBlob(self) -> Dict[str, Any]:
    """Decodes a Blob value."""
    url = self.DecodeStringData()
    blob_type = self.DecodeStringData()
    size = self.decoder.DecodeUint64()
    if self.version >= 11:
      _, memory_cost = self.decoder.DecodeUint64()
    else:
      memory_cost = None

    # TODO: make this a dataclass?
    return {
      'url': url,
      'blob_type': blob_type,
      'size': size,
      'memory_cost': memory_cost
    }

  def DecodeRegExp(self) -> types.RegExp:
    """Decodes a RegExp value."""
    pattern = self.DecodeStringData()
    flags = self.DecodeStringData()
    return types.RegExp(pattern=pattern, flags=flags)

  def DecodeMapData(self) -> dict:
    """Decodes a Map value."""
    tag = self.PeekSerializationTag()
    js_map = {}   # TODO: make this into a JSMap (like JSArray/JSSet)
    self.object_pool.append(js_map)

    while tag != definitions.SerializationTag.NON_MAP_PROPERTIES:
      _, key = self.DecodeValue()
      _, value = self.DecodeValue()
      js_map[key] = value
      tag = self.PeekSerializationTag()

    # consume the NonMapPropertiesTag
    _, tag = self.DecodeSerializationTag()

    pool_tag = self.PeekTag()
    while pool_tag != definitions.TERMINATOR_TAG:
      name = self.DecodeStringData()
      value = self.DecodeValue()
      js_map[name] = value
      pool_tag = self.PeekTag()

    _, tag = self.decoder.DecodeUint32()
    return js_map

  def DecodeSetData(self) -> types.JSSet:
    """Decodes a SetData value."""
    tag = self.PeekSerializationTag()
    js_set = types.JSSet()
    self.object_pool.append(js_set)

    while tag != definitions.SerializationTag.NON_SET_PROPERTIES:
      _, key = self.DecodeValue()
      js_set.values.add(key)
      tag = self.PeekSerializationTag()

    # consume the NonSetPropertiesTag
    _, tag = self.DecodeSerializationTag()

    pool_tag = self.PeekTag()
    while pool_tag != definitions.TERMINATOR_TAG:
      name = self.DecodeStringData()
      value = self.DecodeValue()
      js_set.properties[name] = value
      pool_tag = self.decoder.PeekBytes(4)

    # consume the TerminatorTag
    _, tag = self.decoder.DecodeUint32()
    return js_set

  def DecodeCryptoKey(self) -> bytes:
    """Decodes a CryptoKey value."""
    _, wrapped_key_length = self.decoder.DecodeUint32()
    _, wrapped_key = self.decoder.ReadBytes(wrapped_key_length)
    key = plistlib.loads(wrapped_key)  # TODO: unwrap the wrapped key.
    return key

  def DecodeBigIntData(self) -> int:
    """Decodes a BigIntData value."""
    _, sign = self.decoder.DecodeUint8()
    _, number_of_elements = self.decoder.DecodeUint32()
    contents = []
    for _ in range(number_of_elements):
      _, element = self.decoder.ReadBytes(8)
      contents.extend(element)
    value = int.from_bytes(contents, byteorder='little', signed=bool(sign))
    return value

  def DecodeArrayBuffer(self) -> bytes:
    """Decodes an ArrayBuffer value."""
    _, byte_length = self.decoder.DecodeUint64()
    _, buffer = self.decoder.ReadBytes(byte_length)
    self.object_pool.append(buffer)
    return buffer

  def DecodeResizableArrayBuffer(self) -> ResizableArrayBuffer:
    """Decodes an ArrayBuffer value."""
    _, byte_length = self.decoder.DecodeUint64()
    _, max_length = self.decoder.DecodeUint64()
    _, buffer = self.decoder.ReadBytes(byte_length)
    self.object_pool.append(buffer)
    return ResizableArrayBuffer(buffer=buffer, max_length=max_length)

  def DecodeArrayBufferTransfer(self) -> int:
    """Decodes an ArrayBufferTransfer value."""
    _, value = self.decoder.DecodeUint32()
    return value

  def DecodeSharedArrayBuffer(self) -> int:
    """Decodes an SharedArrayBuffer value."""
    _, value = self.decoder.DecodeUint32()
    return value

  def DecodeObjectReference(self) -> Any:
    """Decodes an ObjectReference value."""
    if len(self.object_pool) < 0xFF:
      _, object_ref = self.decoder.DecodeUint8()
    elif len(self.object_pool) < 0xFFFF:
      _, object_ref = self.decoder.DecodeUint16()
    else:  # if len(self.object_pool) < 0xFFFFFFFF:
      _, object_ref = self.decoder.DecodeUint32()
    return self.object_pool[object_ref]

  def DecodeArrayBufferView(self) -> ArrayBufferView:
    """Decodes an ArrayBufferView value.

    Returns:
      an ArrayBufferView.

    Raises:
      ParserError if an unexpected serialization tag is found.
    """
    _, array_buffer_view_subtag = self.decoder.DecodeUint8()
    array_buffer_view_subtag = definitions.ArrayBufferViewSubtag(
        array_buffer_view_subtag)
    _, byte_offset = self.decoder.DecodeUint64()
    _, byte_length = self.decoder.DecodeUint64()
    _, next_serialization_tag = self.DecodeSerializationTag()

    if next_serialization_tag == definitions.SerializationTag.ARRAY_BUFFER:
      value = self.DecodeArrayBuffer()
    elif (next_serialization_tag ==
          definitions.SerializationTag.OBJECT_REFERENCE):
      value = self.DecodeObjectReference()
    else:
      raise errors.ParserError(
          f'Unexpected serialization tag {next_serialization_tag}.')
    return ArrayBufferView(
        array_buffer_view_subtag=array_buffer_view_subtag,
        buffer=value,
        offset=byte_offset,
        length=byte_length)

  def DecodeSerializedValue(self) -> Any:
    """Decodes a serialized value.

    Returns:
      the serialized value.

    Raises:
      ParserError when CurrentVersion is not found.
    """
    _, current_version = self.decoder.DecodeUint32()
    if current_version != definitions.CURRENT_VERSION:
      raise errors.ParserError(
          f'{current_version} is not the expected CurrentVersion')
    _, value = self.DecodeValue()
    return value

  def DecodeValue(self) -> Tuple[int, Any]:
    """Decodes a value.

    Returns:
      the offset and parsed value.

    Raises:
      ParserError when an unhandled SerializationTag is found.
    """
    offset, tag = self.DecodeSerializationTag()
    if tag == definitions.SerializationTag.ARRAY:
      value = self.DecodeArray()
    elif tag == definitions.SerializationTag.OBJECT:
      value = self.DecodeObject()
    elif tag == definitions.SerializationTag.UNDEFINED:
      value = types.Undefined()
    elif tag == definitions.SerializationTag.NULL:
      value = types.Null()
    elif tag == definitions.SerializationTag.INT:
      _, value = self.decoder.DecodeInt32()
    elif tag == definitions.SerializationTag.ZERO:
      value = 0
    elif tag == definitions.SerializationTag.ONE:
      value = 1
    elif tag == definitions.SerializationTag.FALSE:
      value = False
    elif tag == definitions.SerializationTag.TRUE:
      value = True
    elif tag == definitions.SerializationTag.DOUBLE:
      _, value = self.decoder.DecodeDouble()
    elif tag == definitions.SerializationTag.DATE:
      value = self.DecodeDate()
    elif tag == definitions.SerializationTag.FILE:
      value = self.DecodeFileData()
    elif tag == definitions.SerializationTag.FILE_LIST:
      value = self.DecodeFileList()
    elif tag == definitions.SerializationTag.IMAGE_DATA:
      value = self.DecodeImageData()
    elif tag == definitions.SerializationTag.BLOB:
      value = self.DecodeBlob()
    elif tag == definitions.SerializationTag.STRING:
      value = self.DecodeStringData()
    elif tag == definitions.SerializationTag.EMPTY_STRING:
      value = ''
    elif tag == definitions.SerializationTag.REG_EXP:
      value = self.DecodeRegExp()
    elif tag == definitions.SerializationTag.OBJECT_REFERENCE:
      value = self.DecodeObjectReference()
    elif tag == definitions.SerializationTag.ARRAY_BUFFER:
      value = self.DecodeArrayBuffer()
    elif tag == definitions.SerializationTag.ARRAY_BUFFER_VIEW:
      value = self.DecodeArrayBufferView()
      self.object_pool.append(value)
    elif tag == definitions.SerializationTag.ARRAY_BUFFER_TRANSFER:
      value = self.DecodeArrayBufferTransfer()
    elif tag == definitions.SerializationTag.TRUE_OBJECT:
      self.object_pool.append(True)
      value = True
    elif tag == definitions.SerializationTag.FALSE_OBJECT:
      self.object_pool.append(False)
      value = False
    elif tag == definitions.SerializationTag.STRING_OBJECT:
      value = self.DecodeStringData()
      self.object_pool.append(value)
    elif tag == definitions.SerializationTag.EMPTY_STRING_OBJECT:
      value = ''
      self.object_pool.append(value)
    elif tag == definitions.SerializationTag.NUMBER_OBJECT:
      _, value = self.decoder.DecodeDouble()
      self.object_pool.append(value)
    elif tag == definitions.SerializationTag.SET_OBJECT:
      value = self.DecodeSetData()
    elif tag == definitions.SerializationTag.MAP_OBJECT:
      value = self.DecodeMapData()
    elif tag == definitions.SerializationTag.CRYPTO_KEY:
      value = self.DecodeCryptoKey()
    elif tag == definitions.SerializationTag.SHARED_ARRAY_BUFFER:
      value = self.DecodeSharedArrayBuffer()
    elif tag == definitions.SerializationTag.BIGINT:
      value = self.DecodeBigIntData()
    elif tag == definitions.SerializationTag.BIGINT_OBJECT:
      value = self.DecodeBigIntData()
      self.object_pool.append(value)
    else:
      raise errors.ParserError(f'Unhandled Serialization Tag {tag.name} found.')
    return offset, value

  @classmethod
  def FromBytes(cls, data: bytes) -> Any:
    """Returns a deserialized JavaScript object from the data.

    Args:
      data: the data to deserialize/parse.

    Returns:
      A python representation of the parsed JavaScript object.

    Raises:
      errors.ParserError: if there is an invalid V8 JavaScript header.
    """
    stream = io.BytesIO(data)
    deserializer = cls(stream)
    return deserializer.DecodeSerializedValue()
