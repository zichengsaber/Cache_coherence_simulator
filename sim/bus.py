from typing import List
from sim.cache import Statistics


BUS_OP=dict(
    read_miss = 0,
    write_miss = 1,
    invalidate = 2,
    share_data = 3,
)

class BusRequest:
    def __init__(
        self,
        cache_id: int,
        bus_operation:int,
        address: int=None,
        data=None,
    ) -> None:
        self.cache_id = cache_id
        self.operation= bus_operation
        self.address = address
        self.data = data
    
class Bus:
    def __init__(self,caches,stats:Statistics) -> None:
        self.caches = caches
        self.stats = stats
    
    def push_request(self,request:BusRequest)->None:
        self.stats.bus_requests+=1
        if request.operation == BUS_OP['share_data']:
            self.stats.shares+=1
        for cache in self.caches:
            if (cache.push_bus_request(request)):
                break