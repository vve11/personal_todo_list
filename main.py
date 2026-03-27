print("hello world")


def calculator(a, b, op):
    if op == '+':
        return a + b
    elif op == '-':
        return a - b
    elif op == '*':
        return a * b
    elif op == '/':
        if b == 0:
            raise ValueError("除数不能为零")
        return a / b
    else:
        raise ValueError(f"不支持的运算符: {op}")


if __name__ == "__main__":
    print(calculator(10, 3, '+'))   # 13
    print(calculator(10, 3, '-'))   # 7
    print(calculator(10, 3, '*'))   # 30
    print(calculator(10, 3, '/'))   # 3.333...
