import rti.connextdds as dds
import rti.types as idl

@idl.struct
class ExpLongLongValueType:
    longlongValue: idl.uint64 = 0  # 64-bit unsigned integer
