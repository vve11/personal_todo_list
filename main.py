import time
def enclosing_scope():
    x = 10
    def local_scope():
        nonlocal x
        x += 1
        print(x)
    local_scope()

if __name__ == "__main__":
    enclosing_scope()
    time.sleep(100)

    
