import csv

class Flow:
    def __init__(self, flow_id, weight):
        self.flow_id = flow_id
        self.weight = weight
        self.finish_time = 0.0

class WFQScheduler:
    def __init__(self, weights):
        self.flows = {fid: Flow(fid, w) for fid, w in weights.items()}
        self.scheduled = []

    def schedule(self, arrival_time, flow_id, size):
        flow = self.flows[flow_id]
        start_time = max(flow.finish_time, arrival_time)
        finish = start_time + (size / flow.weight)
        flow.finish_time = finish
        self.scheduled.append((finish, arrival_time, flow_id, size))

    def process_file(self, filename):
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                a_time, f_id, sz = float(row[0]), int(row[1]), int(row[2])
                self.schedule(a_time, f_id, sz)
        self.scheduled.sort(key=lambda x: x[0])
        return self.scheduled

if __name__ == "__main__":
    weights = {1: 5, 2: 3, 3: 2}
    scheduler = WFQScheduler(weights)
    res = scheduler.process_file("traffic.csv")
    
    print(f"{'Finish Time':<15} | {'Arrival':<10} | {'Flow':<5} | {'Size':<5}")
    print("-" * 50)
    for p in res:
        print(f"{p[0]:<15.2f} | {p[1]:<10.2f} | {p[2]:<5} | {p[3]:<5}")
