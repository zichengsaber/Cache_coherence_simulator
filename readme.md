# Cache Coherence Simulator

> XJTU 研究生课程 《并行计算》

## Introduction

* `sim/` 文件夹为python 代码
* `input/` 文件夹为测试文件
* `logs`/ 下为测试输出文件

## Requirmets

* python3
* click
  ```bash
  pip install click
  ```

## Design

### Setting

这一部分主要介绍Cache Simulator的基础设定：

* 地址长度为32 bits, 内存设置为4 GB
* Cache的大小为32 KB
* Cache mapping的策略为 Set Associative Mapping

  * Cache Line长度为64B
  * 每8个Cache Line构成一个Set,一共有64个SET
* 物理地址规划

  | Tag Index | Set Index | Line offset |
  | --------- | --------- | ----------- |
  | 20 bits   | 6 bits    | 6 bits      |
* Cache的换入策略：FIFO(先进先出法)
* Cache 一致性所用的协议MESI

  * Modified: 唯一正确的数据在Cache中
    * 本地读（Rl）和本地写（Wl）不影响状态
    * 远程读（Rr）Modified状态-> Share状态
    * 远程写（Wr）Modified状态->Invalid状态
  * Exclusive: 仅一个Cache和share memory一致
    * 本地读 （RI）不影响状态
    * 远程读 （Rr）exclusive状态-> share 状态
    * 本地写 （WI）exclusive状态-> Modified状态
    * 远程写（Wr）exclusive状态-> Invalid状态
  * Invalid: 在Cache中找不到，或Cache中的block和share memory不一致
    * 远程读（Rr）和 远程写（Wr）状态不变
    * 本地读（Rl）产生Read-miss，如果有E/M状态的cache则掉入本地，否则直接从共享存储器读入数据块，对于第一种情况进入shared状态，对于第二种情况进入Exclusive状态
    * 本地写（WI）产生Write-miss，首先需要将正确的数据块掉入cache，然后写Cahe，将本地Cache状态设置为Exclusive
  * Shared: 多个Cache和内存一致
    * 本地读（RI）和 远程读（Rr）不影响share状态
    * 本地写  (Wl) 使得share状态 -> exclusive 状态
    * 远程写 (WR) BUS发送invalidate 信号，使得 share状态 -> invalid状态

### Abstract （Class design）

**Cache Line：** 地址+行状态

**Cache Set：** Cache Line 构成的queue

* add_line() 用于加入一行Cache Line
* get_line() 用于根据物理地址获取对应的Cache Line

**Bus:** 所有Cache的引用

* push_request() 向所有Cache广播发送请求

**Cache:** Cache Set 构成的List，Bus 的引用

* get_set_id() 根据物理地址address获取其所在的Cache set
* get_line() 根据物理地址获取对应的Cache Line
* handle_bus_request() 处理总线发送过来的请求
* read_request() 读操作时向总线发送的信号
* write_request() 写操作时向总线发送的信号

**Simulator** : 从文件中读取指令，发送给processor执行

### Test

**How to run the program**

```bash
python -m sim.simulator --input_file <input_file>
```

测试文件指令构成:

```bash
<R/W> <address> <Processer number> 
```

测试一: read_miss 测试

```bash
R 0x00007c71 0
R 0x00007c71 0
...
R 0x00007c71 1
```

结果

```bash
[2022-11-10 20:04:04 MESICache] (simulator.py 60): INFO Instruction 0:
[2022-11-10 20:04:04 MESICache] (simulator.py 61): INFO Op:R,address:0x7c71,Processor:0
[2022-11-10 20:04:04 MESICache] (cache.py 148): INFO Cache 0: Read request address 0x7c71
[2022-11-10 20:04:04 MESICache] (cache.py 153): INFO Cache 0: Line not present
[2022-11-10 20:04:04 MESICache] (cache.py 159): INFO Cache 0: Sent a read miss on bus
[2022-11-10 20:04:04 MESICache] (cache.py 167): INFO Cache 0: Fetched from main memory, Line State E
[2022-11-10 20:04:04 MESICache] (simulator.py 60): INFO Instruction 1:
[2022-11-10 20:04:04 MESICache] (simulator.py 61): INFO Op:R,address:0x7c71,Processor:0
[2022-11-10 20:04:04 MESICache] (cache.py 148): INFO Cache 0: Read request address 0x7c71
[2022-11-10 20:04:04 MESICache] (cache.py 171): INFO Cache 0: Line in state E
[2022-11-10 20:04:04 MESICache] (cache.py 175): INFO Cache 0: Read data in local cache
...
[2022-11-10 20:04:04 MESICache] (simulator.py 60): INFO Instruction 5:
[2022-11-10 20:04:04 MESICache] (simulator.py 61): INFO Op:R,address:0x7c71,Processor:1
[2022-11-10 20:04:04 MESICache] (cache.py 148): INFO Cache 1: Read request address 0x7c71
[2022-11-10 20:04:04 MESICache] (cache.py 153): INFO Cache 1: Line not present
[2022-11-10 20:04:04 MESICache] (cache.py 159): INFO Cache 1: Sent a read miss on bus
[2022-11-10 20:04:04 MESICache] (cache.py 96): INFO Cache 0: Bus request address 0x7c71 from Cache 1
[2022-11-10 20:04:04 MESICache] (cache.py 106): INFO Cache 0: Remote need to read,Shared cache block
[2022-11-10 20:04:04 MESICache] (cache.py 96): INFO Cache 1: Bus request address 0x7c71 from Cache 0
[2022-11-10 20:04:04 MESICache] (cache.py 131): INFO Cache 1: Received cache block from Cache 0
[2022-11-10 20:04:04 MESICache] (cache.py 109): INFO Cache 0: Changed state to Shared
[2022-11-10 20:04:04 MESICache] (cache.py 169): INFO Cache 1: Snooped from other cache, Line State S
```

* 首先processor 0 read 0x7c71 产生read-miss ，从main memory中获取数据块，此时只有一个副本与main memory保持一致所以line state 为 E
* 再次读，不改变其状态
* 远程processor 1 read 0x7c71 产生read-miss，从cache 0 获取数据块，cache 0 由 E 状态变为 S状态，cache 1 获取数据块之后状态变化为S

测试二：write-miss 测试

```bash
R 0x00007f51 0
...
W 0x00007f51 1
```

结果：

```bash
[2022-11-10 20:20:21 MESICache] (simulator.py 61): INFO Op:R,address:0x7f51,Processor:0
[2022-11-10 20:20:21 MESICache] (cache.py 148): INFO Cache 0: Read request address 0x7f51
[2022-11-10 20:20:21 MESICache] (cache.py 153): INFO Cache 0: Line not present
[2022-11-10 20:20:21 MESICache] (cache.py 159): INFO Cache 0: Sent a read miss on bus
[2022-11-10 20:20:21 MESICache] (cache.py 167): INFO Cache 0: Fetched from main memory, Line State E
...
[2022-11-10 20:22:04 MESICache] (simulator.py 61): INFO Op:W,address:0x7f51,Processor:1
[2022-11-10 20:22:04 MESICache] (cache.py 193): INFO Cache 1: write request address 0x7f51
[2022-11-10 20:22:04 MESICache] (cache.py 198): INFO Cache 1: Line not present
[2022-11-10 20:22:04 MESICache] (cache.py 204): INFO Cache 1: Send write miss on bus
[2022-11-10 20:22:04 MESICache] (cache.py 96): INFO Cache 0: Bus request address 0x7f51 from Cache 1
[2022-11-10 20:22:04 MESICache] (cache.py 121): INFO Cache 0: Remote attempt to write block that is exclusive/modified elsewhere, wrote back the cache block and invalidated cache block
[2022-11-10 20:22:04 MESICache] (cache.py 209): INFO Cache 1: Write data in local cache
```

* 首先processor 0 read address 0x7f51 产生read-miss，从main-memory中载入数据块，Line state变为E
* processor 1 write address 0x7f51 产生write-miss，自身的line state变为E, Cache 0 中的Line state变为invalid

### Rethinking

本次实验加深了我对于MESI协议的理解，特别是学会了如何写模拟器，如何将硬件抽象成为一个一个的抽象类，同时这种基于消息传递式的通信编程，在我大学阶段的计算机网络原理课中已经有过锻炼，因此这次写起来便得心应手。同时我在实现MESI协议时，稍微和上课讲的有点不用就在于，Read-miss的处理上，我将read-miss 分为了两种情况来处理

* 当从别的cache 得到数据块时，为Share状态
* 当从main memory中得到数据块时，为Exclusive状态

私以为这样会更加合理。
