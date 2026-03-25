import csv
import random

def generate_traffic(filename, num_packets):
    flows = [1, 2, 3]
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['arrival_time', 'flow_id', 'packet_size'])
        
        curr = 0.0
        for _ in range(num_packets):
            curr += random.expovariate(2.0)
            fid = random.choices(flows, weights=[50, 30, 20])[0]
            if fid == 1:
                sz = random.randint(64, 256)
            elif fid == 2:
                sz = random.randint(512, 1024)
            else:
                sz = random.randint(1000, 1500)
            
            writer.writerow([round(curr, 4), fid, sz])

if __name__ == "__main__":
    generate_traffic("traffic.csv", 20)
