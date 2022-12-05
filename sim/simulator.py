# processor operator
from sim.config import *
from sim.cache import MESICache,Bus
from sim.utils import Statistics
from typing import List
import click


OP=dict(
    READ='R',
    WRITE='W',
)



class Simulator:
    def __init__(self) -> None:
        self.stats = Statistics()
        self.caches:List[MESICache]=[]
        self.bus = Bus(self.caches,self.stats)
        for i in range(PROCESSORS):
            self.caches.append(
                MESICache(i,self.bus,self.stats)
            )
    
    def push_request(self,op,address,id):
        if op == OP['READ']:
            self.caches[id].read_request(address)
        if op == OP['WRITE']:
            self.caches[id].write_request(address)
    
    def print_stats(self):
        logger.info(
            f"Total flushes: {self.stats.flushes}\t"
            f"Total hits: {self.stats.hits}\t"
            f"Total misses: {self.stats.misses}\t"
            f"Total evictions: {self.stats.evivts}\t"
            f"Total shares: {self.stats.shares}\t"
            f"Total bus requests: {self.stats.bus_requests}\t"
        )






@click.command(help="Cache Coherence Simulator")
@click.option("--input_file",type=str)
def main(
    input_file:str,
):

    simulator=Simulator()
    with open(input_file,"r") as file:
        lines = file.readlines()
    
    for i,line in enumerate(lines):
        inst=line.strip('\n').strip('\t').split(' ')
        op,address,processor = inst[0],int(inst[1],base=16),int(inst[2])
        logger.info(f"Instruction {i}:")
        logger.info(f"Op:{op},address:{hex(address)},Processor:{processor}")
        simulator.push_request(op,address,processor)
        
    
    simulator.print_stats()

    

if __name__ == "__main__":
    main()
