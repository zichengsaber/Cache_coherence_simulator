from typing import List
from sim.utils import Statistics
from sim.bus import Bus,BusRequest,BUS_OP
from sim.config import *

LineState = dict(
    MODIFIED = 'M',
	EXCLUSIVE = 'E',
	SHARED = 'S',
	INVALID = 'I',
)




class CacheLine:
    def __init__(self,address:int,line_state:str) -> None:
        self.address= address
        self.line_state= line_state
    def invalidate(self):
        self.line_state = LineState['INVALID']


class CacheSet:
    def __init__(self,stats:Statistics) -> None:
        self.stats:Statistics = stats
        self.lines:List[CacheLine] = []
    # a queue
    def add_line(self,address:int,line_state:str):
        if len(self.lines) >= LINES_PER_SET:
            self.lines.pop(0)
            self.stats.evicts+=1
        self.lines.append(CacheLine(address,line_state))

    def get_line(self,address:int):
        for line in self.lines:
            if line.address == address:
                return line
        return None

# the base class for cache
class Cache:
    def __init__(self,
        id:int,
        bus:Bus,
        statistics:Statistics,
    ) -> None:
        self.id = id 
        self.sets: List[CacheSet] = []
        self.bus = bus
        self.stats = statistics
        self.require_share_data = False
        self.received_share_data = False

        for _ in range(SETS):
            self.sets.append(
                CacheSet(statistics)
            )
    def get_set_id(self,address:int)-> int:
        return address >> (INDEX_BITS + OFFSET_BITS)
    
    def get_line(self,address:int)-> CacheLine:
        return self.sets[self.get_set_id(address)].get_line(address)
    
    def push_bus_request(self,request):
        if request.cache_id != self.id:
            if self.handle_bus_request(request):
                return True

        return False

    def handle_bus_request(self,request:BusRequest)->bool:
        raise NotImplementedError(f'Module {type(self).__name__} is missing the required handle_bus_request function')
    
    def read_request(self,address:int):
        raise NotImplementedError(f'Module {type(self).__name__} is missing the required read_request function')
    
    def write_request(self,address:int):
        raise NotImplementedError(f'Module {type(self).__name__} is missing the required read_request function')

# implement four state cache
class MESICache(Cache):
    def __init__(self, id: int, bus: Bus, statistics: Statistics) -> None:
        super().__init__(id, bus, statistics)
    
    def handle_bus_request(self, request:BusRequest) -> bool:
        """
        True: receive , deal then re-send
        False: receive, deal
        """
        line = self.get_line(request.address)
        if not line and request.operation != BUS_OP['share_data']:
            return False
        if request.operation== BUS_OP['share_data'] and not self.require_share_data:
            return False
        logger.info(f"Cache {self.id}: Bus request address {hex(request.address)} from Cache {request.cache_id}")
        # deal read miss (remote read)
        if request.operation == BUS_OP['read_miss']:
            if line.line_state == LineState['SHARED'] or line.line_state==LineState['MODIFIED'] or line.line_state==LineState['EXCLUSIVE']:
                re_request = BusRequest(
                    cache_id= self.id,
                    bus_operation=BUS_OP['share_data'],
                    address=request.address,
                    data=line
                )
                logger.info(f"Cache {self.id}: Remote need to read,Shared cache block")
                self.bus.push_request(re_request)
                line.line_state = LineState['SHARED']
                logger.info(f"Cache {self.id}: Changed state to Shared")
                return True
            elif line.line_state==LineState['INVALID']:
                logger.info(f"Cache {self.id}: No change")
        # (remote write) will make all invalid
        elif request.operation == BUS_OP['write_miss']:
            if line.line_state == LineState['SHARED']:
                line.invalidate()
                logger.info(f"Cache {self.id}: Remote attempt to write shared block, Invalidated Cache block")
            elif line.line_state == LineState['MODIFIED'] or line.line_state == LineState['EXCLUSIVE']:
                line.invalidate()
                self.stats.flushes+=1
                logger.info(f"Cache {self.id}: Remote attempt to write block that is exclusive/modified elsewhere, wrote back the cache block and invalidated cache block")
            elif line.line_state == LineState['INVALID']:
                logger.info(f"Cache {self.id}: No change")
        
        elif request.operation == BUS_OP['invalidate']:
            line.invalidate()
            logger.info(f"Cache {self.id}: Remote attempt to write shared block, Invalidate Cache")
        # handle read miss problem
        elif request.operation == BUS_OP['share_data']:
            self.received_share_data = True
            logger.info(f"Cache {self.id}: Received cache block from Cache {request.cache_id}")

            if not line:
                set_id = self.get_set_id(request.address)
                self.sets[set_id].add_line(
                    address=request.address,
                    line_state=LineState['SHARED']
                )
            else:
                line.line_state = LineState['SHARED']

        return False




    def read_request(self, address: int):
        logger.info(f"Cache {self.id}: Read request address {hex(address)}")
        line = self.get_line(address)
       
        if line is None:  # cache failed to hit cause read_miss
            self.stats.misses+=1
            logger.info(f"Cache {self.id}: Line not present")
            bus_request = BusRequest(
                cache_id = self.id,
                bus_operation= BUS_OP['read_miss'],
                address=address, 
            )
            logger.info(f"Cache {self.id}: Sent a read miss on bus")
            self.require_share_data = True
            self.bus.push_request(bus_request) 
            self.received_share_data = False
            line = self.get_line(address)
            if line is None:
                set_id = self.get_set_id(bus_request.address)
                self.sets[set_id].add_line(bus_request.address,LineState['EXCLUSIVE'])
                logger.info(f"Cache {self.id}: Fetched from main memory, Line State {self.get_line(bus_request.address).line_state}")
            else:
                logger.info(f"Cache {self.id}: Snooped from other cache, Line State {line.line_state}")
        else: # cache hits check state
            logger.info(f"Cache {self.id}: Line in state {line.line_state}")
            # read local
            if line.line_state == LineState['SHARED'] or line.line_state ==LineState['MODIFIED'] or line.line_state==LineState['EXCLUSIVE']:
                self.stats.hits +=1
                logger.info(f"Cache {self.id}: Read data in local cache")
            # read local cause read miss
            elif line.line_state == LineState['INVALID']:
                self.stats.misses+=1
                request = BusRequest(
                    cache_id = self.id,
                    bus_operation=BUS_OP['read_miss'],
                    address=address
                )
                logger.info(f"Cache {self.id}: Sent a read miss on bus")
                self.require_share_data =True
                self.bus.push_request(request)
                self.require_share_data = False
                if not self.received_share_data:
                    line.line_state = LineState['EXCLUSIVE']
                    self.received_share_data = False
        
    def write_request(self, address: int):
        logger.info(f"Cache {self.id}: write request address {hex(address)}")
        line = self.get_line(address)
    
        if line is None: # cache failed to hit cause write-miss
            self.stats.misses+=1
            logger.info(f"Cache {self.id}: Line not present")
            request = BusRequest(
                cache_id= self.id,
                bus_operation=BUS_OP['write_miss'],
                address=address,
            )
            logger.info(f"Cache {self.id}: Send write miss on bus")
            self.bus.push_request(request)
            # get from the main memory
            set_id =self.get_set_id(request.address)
            self.sets[set_id].add_line(request.address,LineState['EXCLUSIVE'])
            logger.info(f"Cache {self.id}: Write data in local cache")
        else:
            logger.info(f"Cache {self.id}: Line in state {line.line_state}")
            if line.line_state == LineState['MODIFIED']:
                self.stats.hits+=1
                logger.info(f"Cache {self.id}: Write data in local cache")
            elif line.line_state == LineState['EXCLUSIVE']:
                self.stats.hits +=1
                logger.info(f"Cache {self.id}: Write data in local cache")
                line.line_state = LineState['MODIFIED']
                logger.info(f"Cache {self.id}: Change state to modified")
            elif line.line_state == LineState['SHARED']:
                self.stats.hits +=1
                request= BusRequest(
                    cache_id=self.id,
                    bus_operation=BUS_OP['invalidate'],
                    address=address,
                )
                logger.info(f"Cache {self.id}: Sent invalidate on bus")
                self.bus.push_request(request)
                line.line_state = LineState['EXCLUSIVE']
                logger.info(f"Cache {self.id}: Change state to exclusive")
            elif line.line_state == LineState['INVALID']:
                self.stats.misses +=1
                request = BusRequest(
                    cache_id= self.id,
                    bus_operation=BUS_OP['write_miss'],
                    address=address,
                )
                logger.info(f"Cache {self.id}: Sent write miss on bus")
                self.bus.push_request(request)
                # 第一次写采用WT策略，同时写入main memory
                line.line_state = LineState['EXCLUSIVE']
                logger.info(f"Cache {self.id}: Change state to exclusive")


    
