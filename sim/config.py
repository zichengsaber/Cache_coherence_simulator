from sim.utils import create_logger
PROCESSORS:int = 4
SETS: int = 64
LINES_PER_SET: int = 8
BYTES_PER_LINE: int = 64
ADDRESS_BITS: int = 32
MEMORY_SIZE: int = 2**ADDRESS_BITS
OFFSET_BITS: int = 6
INDEX_BITS: int = 6
TAG_BITS: int = 20

logger= create_logger(output_dir="./logs",name='MESICache')