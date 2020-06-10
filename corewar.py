class CyclicStack:
    def __init__(self, size):
        self.size = size
        self.cycle = [0]*size
        self.top = 0

    def __len__(self):
        return self.size
    
    def pop(self):
        self.top = (self.top - 1) % self.size
        return self.cycle[self.top]

    def push(self, n):
        self.cycle[self.top] = n
        self.top = (self.top + 1) % self.size

def extract(w, m, n):
    return (w >> m) % (0b1 << n)

def to_signed(w, n):
    if w < (2**(n-1)):
        return w
    return w - (2**n)

def of_signed(w, n):
    if w >= 0:
        return w
    return (2**n) + w

def idecode(w):
    opcode = extract(w, 0, 4)
    modeA = extract(w, 4, 2)
    operandA = extract(w, 8, 12)
    modeB = extract(w, 6, 2)
    operandB = extract(w, 20, 12)

    return (opcode, (modeA, operandA), (modeB, operandB))

def bit_set(w, i):
    return w | (0b1 << i)

def bit_clear(w, i):
    return w & (~ (0b1 << i))

def bit_toggle(w, i):
    return w ^ (0b1 << i)

def resolve_writes(base, xs):
    for i in range(32):
        zeroes = 0
        ones = 0
        for x in xs:
            if extract(x, i, 1) == 0:
                zeroes += 1
            else:
                ones += 1

        if zeroes > ones:
            base = bit_clear(base, i)
        elif zeroes < ones:
            base = bit_set(base, i)

    return base

class Memory:
    def __init__(self, size):
        self.size = size
        self.memory = [0]*size
        self.pending = dict()

    def __len__(self):
        return self.size

    def __getitem__(self, idx):
        return self.memory[idx%self.size]

    def __setitem__(self, idx, value):
        idx = idx % self.size
        if idx not in self.pending:
            self.pending[idx] = [value]
        else:
            self.pending[idx].append(value)

    def writes(self):
        return self.pending.copy()

    def commit(self):
        for idx in self.pending:
            self.memory[idx] = resolve_writes(self.memory[idx], self.pending[idx])

        self.pending = dict()

    def load(self, data, offset):
        idx = offset%self.size
        for i in range(len(data)):
            self.memory[idx] = data[i]
            idx = (idx + 1)%self.size

class Process:
    def __init__(self):
        self.registers = [0]*16
        self.stack = CyclicStack(16)
        self.PC = 0
        self.Z = False

def eval_ADD(w1, w2):
    return (w1 + w2)%(0b1<<32)

def eval_SUB(w1, w2):
    return of_signed(w1 - w2, 32)

def eval_NOT(w):
    return of_signed(~w, 32)

def eval_AND(w1, w2):
    return w1 & w2

def eval_OR(w1, w2):
    return w1 | w2

def eval_LS(a, w):
    a = to_signed(a, 32)
    if a >= 0:
        return (w >> a) % (0b1 << 32)
    else:
        return (w << abs(a)) % (0b1 << 32)

def eval_AS(a, w):
    a = to_signed(a, 32)
    sign = extract(w, 31, 1)
    if a >= 0:
        for _ in range(a):
            w = (w >> 1) + (sign*(0b1 << 31))
        return w % (0b1 << 32)
    else:
        return (w << abs(a)) % (0b1 << 32)

def eval_CMP(w1, w2):
    return w1 == w2

def eval_LT(w1, w2):
    return to_signed(w1, 32) < to_signed(w2, 32)

class InvalidOperation(Exception):
    pass

class AbstractOperand:
    def __init__(self, value):
        self.value = value

    def read(self, memory, process):
        raise InvalidOperation
        
    def write(self, memory, process, value):
        raise InvalidOperation

    @staticmethod
    def create(opmode, opvalue):
        if opmode == 0:
            return ImmediateOperand(opvalue)
        elif opmode == 1:
            return RelativeOperand(opvalue)
        elif opmode == 2:
            return ComputedOperand(opvalue)
        elif opmode == 3:
            return RegisterOperand(opvalue)


class ImmediateOperand(AbstractOperand):
    def __init__(self, value):
        super().__init__(value)

    def read(self, memory, process):
        return of_signed(to_signed(self.value, 12), 32)

class RelativeOperand(AbstractOperand):
    def __init__(self, value):
        super().__init__(value)

    def read(self, memory, process):
        return memory[process.PC + to_signed(self.value, 12)]

    def write(self, memory, process, value):
        idx = process.PC + to_signed(self.value, 12)
        memory[idx] = value

class ComputedOperand(AbstractOperand):
    def __init__(self, value):
        super().__init__(value)

    def read(self, memory, process):
        mem_w = process.PC + to_signed(self.value, 12)
        l = process.PC + to_signed(extract(memory[mem_w], 0, 12), 12)
        return memory[l]

    def write(self, memory, process, value):
        mem_w = process.PC + to_signed(self.value, 12)
        l = process.PC + to_signed(extract(memory[mem_w], 0, 12), 12)
        memory[l] = value

class RegisterOperand(AbstractOperand):
    def __init__(self, value):
        super().__init__(value)

    def read(self, memory, process):
        return process.registers[extract(self.value, 0, 4)]

    def write(self, memory, process, value):
        process.registers[extract(self.value, 0, 4)] = value

class AbstractInstruction:
    def __init__(self, operandA, operandB):
        self.operandA = operandA
        self.operandB = operandB

    def exec(self, memory, process):
        raise NotImplementedError

    @staticmethod
    def create(opcode, operandA, operandB):
        if opcode == 0:
            return FORK(operandA, operandB)
        elif opcode == 1:
            return MOV(operandA, operandB)
        elif opcode == 2:
            return NOT(operandA, operandB)
        elif opcode == 3:
            return AND(operandA, operandB)
        elif opcode == 4:
            return OR(operandA, operandB)
        elif opcode == 5:
            return LS(operandA, operandB)
        elif opcode == 6:
            return AS(operandA, operandB)
        elif opcode == 7:
            return ADD(operandA, operandB)
        elif opcode == 8:
            return SUB(operandA, operandB)
        elif opcode == 9:
            return CMP(operandA, operandB)
        elif opcode == 10:
            return LT(operandA, operandB)
        elif opcode == 11:
            return POP(operandA, operandB)
        elif opcode == 12:
            return PUSH(operandA, operandB)
        elif opcode == 13:
            return JMP(operandA, operandB)
        elif opcode == 14:
            return BZ(operandA, operandB)
        elif opcode == 15:
            return DIE(operandA, operandB)

class FORK(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        process.Z = 0
        process.PC = (process.PC + 1) % len(memory)

        fork = Process()
        fork.registers = process.registers.copy()
        fork.stack.cycle = process.stack.cycle.copy()
        fork.stack.top = process.stack.top
        fork.Z = True
        fork.PC = process.PC

        return [fork]

class MOV(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        self.operandB.write(memory, process, self.operandA.read(memory, process))
        process.PC = (process.PC + 1) % len(memory)
        return list()

class ADD(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        res = eval_ADD(self.operandA.read(memory, process), self.operandB.read(memory, process))
        self.operandB.write(memory, process, res)
        process.PC = (process.PC + 1) % len(memory)
        process.Z = True if res == 0 else False
        return list()

class SUB(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        res = eval_SUB(self.operandA.read(memory, process), self.operandB.read(memory, process))
        self.operandB.write(memory, process, res)
        process.PC = (process.PC + 1) % len(memory)
        process.Z = True if res == 0 else False
        return list()

class NOT(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)
    
    def exec(self, memory, process):
        res = eval_NOT(self.operandA.read(memory, process))
        self.operandB.write(memory, process, res)
        process.PC = (process.PC + 1) % len(memory)
        process.Z = True if res == 0 else False
        return list()

class AND(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        res = eval_AND(self.operandA.read(memory, process), self.operandB.read(memory, process))
        self.operandB.write(memory, process, res)
        process.PC = (process.PC + 1) % len(memory)
        process.Z = True if res == 0 else False
        return list()

class OR(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        res = eval_OR(self.operandA.read(memory, process), self.operandB.read(memory, process))
        self.operandB.write(memory, process, res)
        process.PC = (process.PC + 1) % len(memory)
        process.Z = True if res == 0 else False
        return list()

class LS(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        res = eval_LS(self.operandA.read(memory, process), self.operandB.read(memory, process))
        self.operandB.write(memory, process, res)
        process.PC = (process.PC + 1) % len(memory)
        process.Z = True if res == 0 else False
        return list()

class AS(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        res = eval_AS(self.operandA.read(memory, process), self.operandB.read(memory, process))
        self.operandB.write(memory, process, res)
        process.PC = (process.PC + 1) % len(memory)
        process.Z = True if res == 0 else False
        return list()

class CMP(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        process.Z = eval_CMP(self.operandA.read(memory, process), self.operandB.read(memory, process))
        process.PC = (process.PC + 1) % len(memory)
        return list()

class LT(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        process.Z = eval_LT(self.operandA.read(memory, process), self.operandB.read(memory, process))
        process.PC = (process.PC + 1) % len(memory)
        return list()

class POP(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        self.operandA.write(memory, process, process.stack.pop())
        process.PC = (process.PC + 1) % len(memory)
        return list()

class PUSH(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        process.stack.push(self.operandA.read(memory, process))
        process.PC = (process.PC + 1) % len(memory)
        return list()

class JMP(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        process.PC = (process.PC + to_signed(self.operandA.read(memory, process), 32)) % len(memory)
        return list()

class BZ(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        if process.Z:
            process.PC = (process.PC + to_signed(self.operandA.read(memory, process), 32)) % (2**12)
        else:
            process.PC = (process.PC + 1) % len(memory)
        return list()

class DIE(AbstractInstruction):
    def __init__(self, operandA, operandB):
        super().__init__(operandA, operandB)

    def exec(self, memory, process):
        raise InvalidOperation

from collections import deque

class Machine:
    def __init__(self, program1, program2):
        if len(program1 > 2048) or len(program2 > 2048):
            raise ValueError

        self.__memory = Memory(4096)
        self.__memory.load(program1, 0)
        self.__memory.load(program2, 2048)

        process1 = Process()
        process2 = Process()
        process2.PC = 2048

        self.__player1 = deque([process1])
        self.__player2 = deque([process2])

    @property
    def memory(self):
        return self.__memory.memory.copy()

    @property
    def player1(self):
        return self.__player1.copy()

    @property
    def player2(self):
        return self.__player2.copy()

    def status(self):
        first = len(self.__player1)
        second = len(self.__player2)

        if first > 0 and second > 0:
            return None
        if first == second:
            return 0
        if first > second:
            return 1
        return 2

    def step(self):
        process1 = self.__player1.popleft()
        process2 = self.__player2.popleft()

        opcode1, opA1, opB1 = idecode(self.memory[process1.PC])
        opcode2, opA2, opB2 = idecode(self.memory[process2.PC])

        operandA1, operandB1 = AbstractOperand.create(opA1[0], opA1[1]), AbstractOperand.create(opB1[0], opB1[1])
        operandA2, operandB2 = AbstractOperand.create(opA2[0], opA2[1]), AbstractOperand.create(opB2[0], opB2[1])

        instruction1 = AbstractInstruction.create(opcode1, operandA1, operandB1)
        instruction2 = AbstractInstruction.create(opcode2, operandA2, operandB2)

        first_dead = False
        second_dead = False
        new1, new2 = list(), list()
        try:
            new1 = instruction1.exec(self.__memory, process1)
        except InvalidOperation:
            first_dead = True

        try:
            new2 = instruction2.exec(self.__memory, process2)
        except InvalidOperation:
            second_dead = True

        for new in new1:
            self.__player1.append(new)
        for new in new2:
            self.__player2.append(new)

        if not first_dead:
            self.__player1.append(process1)
        if not second_dead:
            self.__player2.append(process2)

        self.__memory.commit()

    def run(self):
        while self.status() is None:
            self.step()

import sys
def main():
    if len(sys.argv) >= 2:
        file1, file2 = sys.argv[0], sys.argv[1]

        with open(file1, 'rb') as stream:
            contents1 = stream.read()
        if len(contents1) % 4 != 0:
            raise ValueError
        contents1 = [
            int.from_bytes(contents1[i:i+4], 'little')
                for i in range(0, len(contents1), 4)
        ]

        with open(file2, 'rb') as stream:
            contents2 = stream.read()
        if len(contents2) % 4 != 0:
            raise ValueError
        contents2 = [
            int.from_bytes(contents2[i:i+4], 'little')
                for i in range(0, len(contents2), 4)
        ]

        mac = Machine(contents1, contents2)
        mac.run()
        print("And the winner is... ", mac.status())

if __name__ == "__main__":
    main()