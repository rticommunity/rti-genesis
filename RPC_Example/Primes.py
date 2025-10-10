
# WARNING: THIS FILE IS AUTO-GENERATED. DO NOT MODIFY.

# This file was generated from Primes.idl
# using RTI Code Generator (rtiddsgen) version 4.3.0.
# The rtiddsgen tool is part of the RTI Connext DDS distribution.
# For more information, type 'rtiddsgen -help' at a command shell
# or consult the Code Generator User's Manual.

from dataclasses import field
from typing import Union, Sequence, Optional
import rti.idl as idl
from enum import IntEnum
import sys
import os


@idl.struct(
    member_annotations = {
        'replier_w_guid': [idl.bound(255)],
    }
)
class PrimeNumberRequest:
    n: idl.int32 = 0
    primes_per_reply: idl.int32 = 0
    replier_w_guid: str = ""

@idl.enum
class PrimeNumberCalculationStatus(IntEnum):
    REPLY_IN_PROGRESS = 0
    REPLY_COMPLETED = 1
    REPLY_ERROR = 2

@idl.struct(
    member_annotations = {
        'primes': [idl.bound(100)],
    }
)
class PrimeNumberReply:
    primes: Sequence[idl.int32] = field(default_factory = idl.array_factory(idl.int32))
    status: PrimeNumberCalculationStatus = PrimeNumberCalculationStatus.REPLY_IN_PROGRESS
