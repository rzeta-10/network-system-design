import sys

def calculate_fragmentation(mtu1, mtu2):
    header_size = 20
    payload_size = mtu1 - header_size
    max_fragment_payload = mtu2 - header_size
    max_fragment_payload = (max_fragment_payload // 8) * 8
    
    fragments = []
    bytes_sent = 0
    fragment_number = 1
    
    while bytes_sent < payload_size:
        remaining_payload = payload_size - bytes_sent
        if remaining_payload > max_fragment_payload:
            send_data = max_fragment_payload
            mf_flag = 1
        else:
            send_data = remaining_payload
            mf_flag = 0
            
        total_length = send_data + header_size
        offset_field = bytes_sent // 8
        
        fragments.append((fragment_number, total_length, send_data, offset_field, mf_flag))
        
        bytes_sent += send_data
        fragment_number += 1
        
    return fragments

def print_fragments(fragments):
    print(f"{'Fragment #':<12} {'Total Length':<15} {'Data Length':<15} {'Offset Field':<15} {'MF Flag':<10}")
    for frag in fragments:
        print(f"{frag[0]:<12} {frag[1]:<15} {frag[2]:<15} {frag[3]:<15} {frag[4]:<10}")

if __name__ == "__main__":
    if len(sys.argv) == 3:
        mtu1 = int(sys.argv[1])
        mtu2 = int(sys.argv[2])
    else:
        mtu1 = 4020
        mtu2 = 1500
    
    fragments = calculate_fragmentation(mtu1, mtu2)
    print_fragments(fragments)
