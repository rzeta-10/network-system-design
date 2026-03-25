import random
import json

def generate_test_cases(num_cases=10):
    test_cases = []
    for _ in range(num_cases):
        mtu1 = random.randint(3000, 15000)
        mtu2 = random.randint(500, 1500)
        test_cases.append({"mtu1": mtu1, "mtu2": mtu2})
    return test_cases

if __name__ == "__main__":
    cases = generate_test_cases()
    with open("inputs.json", "w") as f:
        json.dump(cases, f, indent=4)
    for i, case in enumerate(cases):
        print(f"{i+1}: MTU1={case['mtu1']}, MTU2={case['mtu2']}")
