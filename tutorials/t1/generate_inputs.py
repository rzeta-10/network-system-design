import random

def generate_ip(cls):
    if cls == 'A':
        o1 = random.randint(1, 126)
    elif cls == 'B':
        o1 = random.randint(128, 191)
    elif cls == 'C':
        o1 = random.randint(192, 223)
    elif cls == 'D':
        o1 = random.randint(224, 239)
    else: # E
        o1 = random.randint(240, 255)
    
    o2 = random.randint(0, 255)
    o3 = random.randint(0, 255)
    o4 = random.randint(0, 255)
    return f"{o1}.{o2}.{o3}.{o4}"

def main():
    count = 100
    classes = ['A', 'B', 'C', 'D', 'E']
    for _ in range(count):
        cls = random.choice(classes)
        print(generate_ip(cls))

if __name__ == "__main__":
    main()
