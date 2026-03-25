#!/usr/bin/env python3

# CS22B1093 Rohan G

import time
from typing import Optional, List


class BufferBlock:
    def __init__(self, block_size: int):
        self.block_size = block_size
        self.data = bytearray(block_size)
        self.bytes_used = 0
        self.next: Optional['BufferBlock'] = None
    
    def available_space(self) -> int:
        return self.block_size - self.bytes_used
    
    def write_data(self, source: bytes, offset: int, length: int) -> int:
        available = self.available_space()
        bytes_to_write = min(length, available)
        
        if bytes_to_write > 0:
            self.data[self.bytes_used:self.bytes_used + bytes_to_write] = \
                source[offset:offset + bytes_to_write]
            self.bytes_used += bytes_to_write
        
        return bytes_to_write
    
    def reset(self):
        self.bytes_used = 0
        self.next = None


class MemoryPool:
    def __init__(self, block_size: int, initial_blocks: int = 100):
        self.block_size = block_size
        self.free_blocks: List[BufferBlock] = []
        self.allocated_blocks: List[BufferBlock] = []
        
        for _ in range(initial_blocks):
            self.free_blocks.append(BufferBlock(block_size))
        
        self.total_allocations = 0
        self.total_deallocations = 0
        self.peak_usage = 0
    
    def allocate_block(self) -> Optional[BufferBlock]:
        if not self.free_blocks:
            block = BufferBlock(self.block_size)
        else:
            block = self.free_blocks.pop()
            block.reset()
        
        self.allocated_blocks.append(block)
        self.total_allocations += 1
        self.peak_usage = max(self.peak_usage, len(self.allocated_blocks))
        
        return block
    
    def deallocate_block(self, block: BufferBlock):
        if block in self.allocated_blocks:
            self.allocated_blocks.remove(block)
            block.reset()
            self.free_blocks.append(block)
            self.total_deallocations += 1
    
    def get_stats(self) -> dict:
        return {
            'block_size': self.block_size,
            'free_blocks': len(self.free_blocks),
            'allocated_blocks': len(self.allocated_blocks),
            'total_allocations': self.total_allocations,
            'total_deallocations': self.total_deallocations,
            'peak_usage': self.peak_usage
        }


class PacketBufferManager:
    def __init__(self, block_size: int = 512, pool_size: int = 100):
        self.block_size = block_size
        self.pool = MemoryPool(block_size, pool_size)
        self.packets_written = 0
        self.packets_read = 0
        self.total_bytes_written = 0
        self.total_bytes_read = 0
    
    def write_packet(self, packet_data: bytes) -> Optional[BufferBlock]:
        if not packet_data:
            return None
        
        packet_size = len(packet_data)
        offset = 0
        head = None
        current = None
        
        while offset < packet_size:
            block = self.pool.allocate_block()
            if block is None:
                if head:
                    self.free_packet(head)
                return None
            
            remaining = packet_size - offset
            written = block.write_data(packet_data, offset, remaining)
            offset += written
            
            if head is None:
                head = block
                current = block
            else:
                current.next = block
                current = block
        
        self.packets_written += 1
        self.total_bytes_written += packet_size
        
        return head
    
    def read_packet(self, head: BufferBlock) -> bytes:
        if head is None:
            return b''
        
        current = head
        total_size = 0
        while current is not None:
            total_size += current.bytes_used
            current = current.next
        
        result = bytearray(total_size)
        offset = 0
        
        current = head
        while current is not None:
            result[offset:offset + current.bytes_used] = \
                current.data[:current.bytes_used]
            offset += current.bytes_used
            current = current.next
        
        self.packets_read += 1
        self.total_bytes_read += total_size
        
        return bytes(result)
    
    def free_packet(self, head: BufferBlock):
        current = head
        while current is not None:
            next_block = current.next
            self.pool.deallocate_block(current)
            current = next_block
    
    def get_chain_info(self, head: BufferBlock) -> List[dict]:
        chain_info = []
        current = head
        block_num = 1
        
        while current is not None:
            chain_info.append({
                'block_num': block_num,
                'bytes_used': current.bytes_used,
                'block_size': current.block_size,
                'utilization': f"{(current.bytes_used / current.block_size) * 100:.1f}%",
                'has_next': current.next is not None
            })
            current = current.next
            block_num += 1
        
        return chain_info
    
    def get_stats(self) -> dict:
        pool_stats = self.pool.get_stats()
        return {
            'packets_written': self.packets_written,
            'packets_read': self.packets_read,
            'total_bytes_written': self.total_bytes_written,
            'total_bytes_read': self.total_bytes_read,
            'pool_stats': pool_stats
        }


class OperationChainer:
    @staticmethod
    def compute_crc32(head: BufferBlock) -> int:
        import zlib
        crc = 0
        current = head
        
        while current is not None:
            crc = zlib.crc32(current.data[:current.bytes_used], crc)
            current = current.next
        
        return crc & 0xFFFFFFFF
    
    @staticmethod
    def parse_protocol_header(head: BufferBlock, header_size: int) -> dict:
        if head is None or header_size <= 0:
            return {}
        
        header_bytes = bytearray()
        current = head
        remaining = header_size
        
        while current is not None and remaining > 0:
            bytes_to_read = min(remaining, current.bytes_used)
            header_bytes.extend(current.data[:bytes_to_read])
            remaining -= bytes_to_read
            current = current.next
        
        if len(header_bytes) >= 4:
            return {
                'version': header_bytes[0],
                'packet_type': header_bytes[1],
                'payload_length': header_bytes[2],
                'flags': header_bytes[3]
            }
        
        return {}
    
    @staticmethod
    def chain_operations(manager: PacketBufferManager, packet_data: bytes) -> dict:
        start_time = time.perf_counter()
        
        write_start = time.perf_counter()
        head = manager.write_packet(packet_data)
        write_time = time.perf_counter() - write_start
        
        if head is None:
            return {'error': 'Failed to allocate buffers'}
        
        crc_start = time.perf_counter()
        crc = OperationChainer.compute_crc32(head)
        crc_time = time.perf_counter() - crc_start
        
        parse_start = time.perf_counter()
        header = OperationChainer.parse_protocol_header(head, 16)
        parse_time = time.perf_counter() - parse_start
        
        read_start = time.perf_counter()
        reassembled = manager.read_packet(head)
        read_time = time.perf_counter() - read_start
        
        manager.free_packet(head)
        
        total_time = time.perf_counter() - start_time
        
        return {
            'packet_size': len(packet_data),
            'crc': crc,
            'header': header,
            'verified': reassembled == packet_data,
            'timing': {
                'write_us': write_time * 1_000_000,
                'crc_us': crc_time * 1_000_000,
                'parse_us': parse_time * 1_000_000,
                'read_us': read_time * 1_000_000,
                'total_us': total_time * 1_000_000
            }
        }
